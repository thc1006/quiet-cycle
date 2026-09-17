"""Predict using a fixed fitted artifact. Never refit during prediction."""
from __future__ import annotations

from ..dates import add_days, day_difference
from ..errors import InputError
from ..models import CycleDataset, Query, Rational
from ..serialization import parse_model
from .contracts import CalibratedInterval, Contribution, FittedModel, Landmark, LearnedPrediction
from .exact import conformal_radius, round_day
from .fitting import model_digest, raw_length, subject_hash
from .landmarks import make_landmark, spec_digest


def predict_landmark(model: FittedModel, landmark: Landmark) -> LearnedPrediction:
    model = parse_model(FittedModel, model)
    landmark = parse_model(Landmark, landmark)
    q = landmark.query
    digest = model_digest(model)

    def stop(reason: str) -> LearnedPrediction:
        return LearnedPrediction(model_sha256=digest, subject_id=q.subject_id, as_of=q.as_of,
                                 cutoff=q.cutoff, status="abstain", reason=reason, issues=landmark.issues)

    if q.context.paused:
        return stop("paused")
    if q.context.mode != "natural-cycle":
        return stop("outside-declared-scope")
    if q.context.changed_since and landmark.anchor_date < q.context.changed_since:
        return stop("context-changed-within-current-cycle")
    if q.cutoff <= model.available_at:
        return stop("model-not-available-at-cutoff")
    if model.split_mode == "new-subject" and subject_hash(q.subject_id) in set(model.train_subject_hashes + model.tune_subject_hashes + model.calibration_subject_hashes):
        return stop("subject-seen-in-model-development")
    if landmark.spec_sha256 != spec_digest(model.spec) or day_difference(q.as_of, landmark.anchor_date) != model.spec.elapsed_day:
        return stop("landmark-spec-mismatch")
    raw, parts, issues = raw_length(model, landmark)
    point = max(model.spec.elapsed_day, round_day(raw))
    try:
        point_date = add_days(landmark.anchor_date, point)
    except (ValueError, OverflowError):
        return stop("date-domain-limit")
    intervals: list[CalibratedInterval] = []
    assumption = "exchangeable-new-subjects-required" if model.split_mode == "new-subject" else "dependent-time-series-no-coverage-guarantee"
    for coverage in (800000, 900000):
        radius = conformal_radius(model.calibration_scores, coverage)
        if radius is None:
            intervals.append(CalibratedInterval(nominal_coverage_ppm=coverage, start=None, end=None, radius_days=None, unbounded=True, assumption=assumption))
        else:
            try:
                lower = add_days(landmark.anchor_date, max(model.spec.elapsed_day, point - radius))
                upper = add_days(landmark.anchor_date, point + radius)
            except (ValueError, OverflowError):
                return stop("date-domain-limit")
            intervals.append(CalibratedInterval(nominal_coverage_ppm=coverage, start=lower, end=upper, radius_days=radius, unbounded=False, assumption=assumption))
    return LearnedPrediction(model_sha256=digest, subject_id=q.subject_id, as_of=q.as_of, cutoff=q.cutoff,
        status="estimate", reason="fitted-landmark-model", point_date=point_date, point_cycle_length=point,
        raw_cycle_length=Rational.from_fraction(raw), baseline_cycle_length=landmark.baseline_length,
        intervals=tuple(intervals), contributions=tuple(Contribution(term=t, days=Rational.from_fraction(v)) for t, v in sorted(parts.items())),
        issues=tuple(sorted(set(landmark.issues + issues))))


class MultiFactorPipeline:
    """Same event inputs as CyclePipeline; returns an interval forecast, not fake probabilities."""
    def __init__(self, model: FittedModel) -> None:
        self.model = parse_model(FittedModel, model)

    def run(self, dataset: CycleDataset, query: Query) -> LearnedPrediction:
        dataset = parse_model(CycleDataset, dataset)
        query = parse_model(Query, query)
        try:
            landmark = make_landmark(dataset, query, self.model.spec)
        except InputError as exc:
            return LearnedPrediction(model_sha256=model_digest(self.model), subject_id=query.subject_id,
                as_of=query.as_of, cutoff=query.cutoff, status="abstain", reason=exc.code)
        return predict_landmark(self.model, landmark)
