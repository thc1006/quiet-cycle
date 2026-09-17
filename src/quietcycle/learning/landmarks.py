"""Build causal features from the existing typed event pipeline.

Labels are selected in a separate, explicit later snapshot. Whole-cycle summaries
and post-onset backfills never enter an earlier feature snapshot.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from hashlib import sha256
from typing import Literal

from ..dates import add_days, day_difference, local_day
from ..errors import InputError
from ..features import DefaultFeatureBuilder
from ..ledger import snapshot
from ..models import CycleDataset, Onset, Query, Rational, Symptom
from ..serialization import canonical_json, parse_model
from .contracts import FeatureValue, LabelledCase, Landmark, LandmarkSpec
from .exact import median


def spec_digest(spec: LandmarkSpec) -> str:
    return sha256(canonical_json(spec).encode()).hexdigest()


def make_landmark(dataset: CycleDataset, query: Query, spec: LandmarkSpec) -> Landmark:
    dataset = parse_model(CycleDataset, dataset)
    query = parse_model(Query, query)
    spec = parse_model(LandmarkSpec, spec)
    if query.context.paused:
        raise InputError("paused")
    if query.context.mode != "natural-cycle":
        raise InputError("outside-declared-scope")
    selected = snapshot(dataset, query)
    features = DefaultFeatureBuilder().build(selected, query)
    if features.conflicting_onsets or not features.onsets:
        raise InputError("missing-or-conflicting-onsets")
    anchor = features.onsets[-1]
    if anchor.certainty != "confirmed" or anchor.exclude_from_history:
        raise InputError("uncertain-or-excluded-anchor")
    if query.context.changed_since and anchor.date < query.context.changed_since:
        raise InputError("context-changed-within-current-cycle")
    if day_difference(query.as_of, anchor.date) != spec.elapsed_day:
        raise InputError("landmark-day-mismatch")
    by_id = {o.id: o for o in features.onsets}
    for report in features.no_onset:
        origin = by_id.get(report.anchor_id)
        if origin is None or origin.certainty != "confirmed" or report.through < origin.date:
            raise InputError("invalid-no-onset-report")
        if any(origin.date < o.date <= report.through for o in features.onsets):
            raise InputError("conflicting-no-onset-report")
    reports = [r.through for r in features.no_onset if r.anchor_id == anchor.id]
    if not reports or max(reports) != add_days(query.as_of, -1):
        raise InputError("onset-status-unconfirmed")
    # A suffix only: never skip an unknown interval and call the remainder contiguous.
    recent = [i for i in features.intervals if not i.changed][-spec.max_history:]
    if len(recent) < spec.min_history or any(not i.known or i.excluded or i.changed for i in recent):
        raise InputError("insufficient-clean-history")
    lengths = [Fraction(i.length) for i in recent]
    center = median(lengths)
    values: dict[str, Fraction | None] = {
        "history.median": center,
        "history.last": lengths[-1],
        "history.mad": median([abs(x - center) for x in lengths]),
        "history.change": lengths[-1] - lengths[-2] if len(lengths) > 1 else Fraction(0),
        "history.count": Fraction(len(lengths)),
    }
    issues: list[str] = []
    # Use completed dates only; partial-day sampling cannot be mistaken for a daily summary.
    end = add_days(query.as_of, -1)
    recent_start = add_days(query.as_of, -spec.recent_days)
    reference_start = add_days(recent_start, -spec.reference_days)
    for metric in spec.metrics:
        selected_m = [m for m in features.measurements if m.metric == metric and reference_start <= m.date <= end and m.state == "measured"]
        streams = {(m.source, m.method, m.body_site) for m in selected_m}
        rvalue = delta = None
        if len(streams) > 1:
            issues.append("mixed-stream." + metric)
        else:
            days: dict[str, list[Fraction]] = {}
            for m in selected_m:
                if m.value is not None:
                    days.setdefault(m.date, []).append(m.value.as_fraction())
            daily = {day: median(vs) for day, vs in days.items()}
            r = [v for day, v in daily.items() if recent_start <= day <= end]
            b = [v for day, v in daily.items() if reference_start <= day < recent_start]
            if len(r) >= spec.minimum_measurement_days:
                rvalue = median(r)
            if rvalue is not None and len(b) >= spec.minimum_measurement_days:
                delta = rvalue - median(b)
        values[f"measurement.{metric}.recent"] = rvalue
        values[f"measurement.{metric}.delta"] = delta
    for symptom in spec.symptoms:
        days_s: dict[str, list[Symptom]] = {}
        for e in selected.events:
            if isinstance(e, Symptom) and e.symptom == symptom and recent_start <= e.date <= end:
                days_s.setdefault(e.date, []).append(e)
        usable: list[int] = []
        impacts: list[Fraction] = []
        for reports_s in days_s.values():
            states = {r.state for r in reports_s}
            if len(states) != 1:
                issues.append("conflicting-symptom." + symptom)
                continue
            state = reports_s[0].state
            if state in ("present", "absent"):
                usable.append(int(state == "present"))
                if state == "absent":
                    impacts.append(Fraction(0))
                elif len({r.impact for r in reports_s}) == 1 and reports_s[0].impact is not None:
                    impacts.append(Fraction(reports_s[0].impact))
        # A denominator is recorded known days, not every day in the window.
        values[f"symptom.{symptom}.rate"] = Fraction(sum(usable), len(usable)) if usable else None
        values[f"symptom.{symptom}.impact"] = sum(impacts, Fraction(0)) / len(impacts) if impacts else None
    return Landmark(subject_id=query.subject_id, anchor_id=anchor.id, anchor_date=anchor.date,
                    query=query, spec_sha256=spec_digest(spec), snapshot_sha256=selected.sha256,
                    baseline_length=Rational.from_fraction(center),
                    values=tuple(FeatureValue(name=n, value=None if v is None else Rational.from_fraction(v)) for n, v in sorted(values.items())),
                    issues=tuple(sorted(set(issues))))


def label_landmark(dataset: CycleDataset, landmark: Landmark, *, labels_cutoff: str,
                   data_kind: Literal["synthetic", "observational"], cohort: str) -> LabelledCase:
    dataset = parse_model(CycleDataset, dataset)
    landmark = parse_model(Landmark, landmark)
    q = landmark.query
    label_q = Query(subject_id=q.subject_id, as_of=local_day(labels_cutoff, q.utc_offset_minutes),
                    cutoff=labels_cutoff, utc_offset_minutes=q.utc_offset_minutes, context=q.context)
    if labels_cutoff <= q.cutoff:
        raise InputError("label_cutoff_not_later")
    onsets = sorted((e for e in snapshot(dataset, label_q).events if isinstance(e, Onset)), key=lambda o: (o.date, o.id))
    anchor = next((o for o in onsets if o.id == landmark.anchor_id), None)
    if anchor is None or anchor.date != landmark.anchor_date or anchor.certainty != "confirmed" or anchor.exclude_from_history:
        raise InputError("anchor-revised-after-prediction")
    later = [o for o in onsets if o.date > anchor.date]
    if not later:
        raise InputError("right-censored-no-known-outcome")
    end = later[0]
    if end.certainty != "confirmed" or end.exclude_from_history or end.previous_onset_id != anchor.id or end.continuity != "confirmed":
        raise InputError("unconfirmed-label-continuity")
    if sum(o.date == end.date for o in onsets) != 1:
        raise InputError("conflicting-label")
    if end.date < q.as_of:
        raise InputError("retrospective-label-before-landmark")
    if max(anchor.available_at, end.available_at) <= q.cutoff:
        raise InputError("outcome-already-known-at-landmark")
    return LabelledCase(landmark=landmark, outcome_date=end.date,
                        outcome_known_at=max(anchor.available_at, end.available_at), data_kind=data_kind, cohort=cohort)


@dataclass(frozen=True)
class CaseBuildResult:
    cases: tuple[LabelledCase, ...]
    rejected: tuple[tuple[str, str, str], ...]


def build_cases(dataset: CycleDataset, queries: tuple[Query, ...], *, spec: LandmarkSpec,
                labels_cutoff: str, data_kind: Literal["synthetic", "observational"], cohort: str) -> CaseBuildResult:
    """Account for every requested landmark, including censored and invalid ones."""
    cases: list[LabelledCase] = []
    rejected: list[tuple[str, str, str]] = []
    for query in queries:
        try:
            landmark = make_landmark(dataset, query, spec)
            cases.append(label_landmark(dataset, landmark, labels_cutoff=labels_cutoff, data_kind=data_kind, cohort=cohort))
        except InputError as exc:
            rejected.append((query.subject_id, query.as_of, exc.code))
    return CaseBuildResult(tuple(cases), tuple(rejected))
