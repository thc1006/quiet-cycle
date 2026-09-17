"""Exact regularized residual regression, held-out model selection and calibration.

This is a deliberately inspectable statistical model, not a reproduction of a
published wearable algorithm. No clinically fitted artifact ships in the package.
"""
from __future__ import annotations

from fractions import Fraction
from hashlib import sha256

from ..errors import InputError
from ..models import Rational
from ..serialization import canonical_json, parse_model
from .contracts import FitRequest, FittedModel, LabelledCase, Landmark, LinearCandidate, ScaleColumn, expected_feature_names
from .exact import median, ridge, round_day
from .landmarks import spec_digest


def subject_hash(subject_id: str) -> str:
    # Audit token only: low-entropy identifiers can be guessed. Not anonymization.
    return sha256(("quietcycle-subject-v1:" + subject_id).encode()).hexdigest()


def model_digest(model: FittedModel) -> str:
    return sha256(canonical_json(model).encode()).hexdigest()


def _values(landmark: Landmark) -> dict[str, Fraction | None]:
    return {v.name: None if v.value is None else v.value.as_fraction() for v in landmark.values}


def fit_columns(cases: tuple[LabelledCase, ...]) -> tuple[ScaleColumn, ...]:
    columns: list[ScaleColumn] = []
    names = [v.name for v in cases[0].landmark.values]
    for name in names:
        observed = [v for case in cases if (v := _values(case.landmark).get(name)) is not None]
        center = median(observed) if observed else Fraction(0)
        # Mean absolute deviation about the median avoids an all-zero MAD for sparse features.
        scale = sum((abs(x - center) for x in observed), Fraction(0)) / len(observed) if observed else Fraction(1)
        if not scale:
            scale = Fraction(1)
        columns.append(ScaleColumn(name=name, center=Rational.from_fraction(center),
                                   scale=Rational.from_fraction(scale), observed_in_train=bool(observed)))
    return tuple(columns)


def vector(landmark: Landmark, columns: tuple[ScaleColumn, ...], clipping: int, quantization: int) -> tuple[dict[str, Fraction], tuple[str, ...]]:
    supplied = _values(landmark)
    if tuple(supplied) != tuple(c.name for c in columns):
        raise InputError("feature-schema-mismatch")
    result: dict[str, Fraction] = {"intercept": Fraction(1)}
    issues: list[str] = []
    for c in columns:
        value = supplied[c.name]
        if not c.observed_in_train:
            if value is not None:
                issues.append("untrained-feature." + c.name)
            value = None
        missing = value is None
        z = Fraction(0) if missing else (value - c.center.as_fraction()) / c.scale.as_fraction()
        if abs(z) > clipping:
            issues.append("clipped." + c.name)
        z = min(Fraction(clipping), max(-Fraction(clipping), z))
        z = Fraction(round_day(z * quantization), quantization)
        result[c.name] = z
        result["missing." + c.name] = Fraction(int(missing))
    # Predeclared interactions; not a search over all possible correlations.
    for name, a, b in (
        ("interaction.temperature_heart", "measurement.wrist_temperature.delta", "measurement.resting_heart_rate.delta"),
        ("interaction.fatigue_sleep", "symptom.fatigue.rate", "measurement.sleep_duration.delta"),
    ):
        if a in result and b in result:
            result[name] = result[a] * result[b]
    return result, tuple(sorted(set(issues)))


def raw_length(model: FittedModel, landmark: Landmark) -> tuple[Fraction, dict[str, Fraction], tuple[str, ...]]:
    x, issues = vector(landmark, model.columns, model.clipping, model.quantization)
    candidate = model.selected
    if any(t not in x for t in candidate.terms):
        raise InputError("unknown-model-term")
    parts = {term: coefficient.as_fraction() * x[term] * candidate.blend.as_fraction()
             for term, coefficient in zip(candidate.terms, candidate.coefficients)}
    value = landmark.baseline_length.as_fraction() + sum(parts.values(), Fraction(0))
    return value, parts, issues


def point_length(model: FittedModel, landmark: Landmark) -> int:
    value, _, _ = raw_length(model, landmark)
    # A completed-day no-onset assertion, required by make_landmark, permits this floor.
    return max(model.spec.elapsed_day, round_day(value))


def _validate_partitions(request: FitRequest) -> tuple[tuple[LabelledCase, ...], tuple[LabelledCase, ...], tuple[LabelledCase, ...]]:
    groups = tuple(tuple(sorted(cases, key=lambda c: (c.landmark.query.cutoff, c.landmark.subject_id, c.landmark.anchor_id)))
                   for cases in (request.train, request.tune, request.calibration))
    all_cases = sum(groups, ())
    expected_spec = spec_digest(request.spec)
    expected_features = expected_feature_names(request.spec)
    keys = [(c.landmark.subject_id, c.landmark.anchor_id) for c in all_cases]
    if len(set(keys)) != len(keys):
        raise InputError("duplicate-cycle-across-or-within-partitions")
    if len({c.data_kind for c in all_cases}) != 1:
        raise InputError("mixed-synthetic-and-observational-data")
    for case in all_cases:
        context = case.landmark.query.context
        if context.paused or context.mode != "natural-cycle":
            raise InputError("development-case-outside-scope")
        if context.changed_since and case.landmark.anchor_date < context.changed_since:
            raise InputError("development-case-context-change")
        if case.landmark.spec_sha256 != expected_spec:
            raise InputError("landmark-spec-mismatch")
        from ..dates import day_difference
        if day_difference(case.landmark.query.as_of, case.landmark.anchor_date) != request.spec.elapsed_day:
            raise InputError("landmark-day-mismatch")
        if tuple(v.name for v in case.landmark.values) != expected_features:
            raise InputError("feature-schema-mismatch")
    for left, right in zip(groups, groups[1:]):
        if max(c.outcome_known_at for c in left) >= min(c.landmark.query.cutoff for c in right):
            raise InputError("partition-temporal-leakage")
    if request.split_mode == "new-subject":
        ids = [{c.landmark.subject_id for c in group} for group in groups]
        if any(ids[i] & ids[j] for i in range(3) for j in range(i)):
            raise InputError("subject-overlap")
        if len(ids[2]) != len(groups[2]):
            raise InputError("one-calibration-case-per-subject-required")
    return groups  # type: ignore[return-value]


def fit(request: FitRequest) -> FittedModel:
    request = parse_model(FitRequest, request)
    train, tune, calibration = _validate_partitions(request)
    columns = fit_columns(train)
    train_x = [vector(c.landmark, columns, request.clipping, request.quantization)[0] for c in train]
    tune_x = [vector(c.landmark, columns, request.clipping, request.quantization)[0] for c in tune]
    residuals = [Fraction(c.length) - c.landmark.baseline_length.as_fraction() for c in train]
    baseline_mse = sum(((Fraction(c.length) - max(request.spec.elapsed_day, c.landmark.baseline_length.as_fraction())) ** 2 for c in tune), Fraction(0)) / len(tune)
    candidates = [LinearCandidate(name="baseline", penalty=0, terms=(), coefficients=(), blend=Rational.from_fraction(Fraction(0)), tune_mse=Rational.from_fraction(baseline_mse))]
    all_terms = sorted(train_x[0])
    # Remove train-constant columns except the intercept. Unknown-at-training features
    # cannot suddenly gain an effect at inference.
    varying = {t for t in all_terms if t == "intercept" or len({x[t] for x in train_x}) > 1}
    for family in ("history", "symptoms", "wearable", "combined"):
        def allowed(term: str) -> bool:
            base = term.removeprefix("missing.")
            return (term == "intercept" or base.startswith("history.") or
                    family in ("symptoms", "combined") and base.startswith("symptom.") or
                    family in ("wearable", "combined") and base.startswith("measurement.") or
                    family == "combined" and base.startswith("interaction."))
        terms = tuple(["intercept"] + [t for t in all_terms if t != "intercept" and t in varying and allowed(t)])
        rows = [tuple(x[t] for t in terms) for x in train_x]
        for penalty in request.ridge_penalties:
            coefficients = ridge(rows, residuals, penalty)
            corrections = [sum((b * x[t] for b, t in zip(coefficients, terms)), Fraction(0)) for x in tune_x]
            numerator = sum((g * (Fraction(c.length) - c.landmark.baseline_length.as_fraction()) for g, c in zip(corrections, tune)), Fraction(0))
            denominator = sum((g * g for g in corrections), Fraction(0))
            blend = min(Fraction(1), max(Fraction(0), numerator / denominator)) if denominator else Fraction(0)
            # Exact least-squares blend is fitted before the known-survival floor.
            # Candidate selection scores the actual floored continuous prediction.
            mse = sum(((Fraction(c.length) - max(Fraction(request.spec.elapsed_day), c.landmark.baseline_length.as_fraction() + blend * g)) ** 2 for c, g in zip(tune, corrections)), Fraction(0)) / len(tune)
            candidates.append(LinearCandidate(name=f"{family}-ridge-{penalty}", penalty=penalty, terms=terms,
                coefficients=tuple(Rational.from_fraction(b) for b in coefficients), blend=Rational.from_fraction(blend), tune_mse=Rational.from_fraction(mse)))
    # Fixed priority preserves baseline on ties, then simpler families and larger penalties.
    family_order = {"baseline": 0, "history": 1, "symptoms": 2, "wearable": 3, "combined": 4}
    selected = min(candidates, key=lambda c: (c.tune_mse.as_fraction(), family_order[c.name.split("-ridge-")[0]], -c.penalty))
    core = dict(spec=request.spec, columns=columns, clipping=request.clipping, quantization=request.quantization, selected=selected,
                candidates=tuple(candidates), calibration_scores=(0,) * len(calibration),
                train_count=len(train), tune_count=len(tune), calibration_count=len(calibration),
                train_subject_hashes=tuple(sorted({subject_hash(c.landmark.subject_id) for c in train})),
                tune_subject_hashes=tuple(sorted({subject_hash(c.landmark.subject_id) for c in tune})),
                calibration_subject_hashes=tuple(sorted({subject_hash(c.landmark.subject_id) for c in calibration})),
                split_mode=request.split_mode,
                fitted_at=max(c.outcome_known_at for c in train + tune),
                available_at=max(c.outcome_known_at for c in all_cases(train, tune, calibration)),
                training_digest=sha256(canonical_json({"spec": request.spec, "train": train, "tune": tune, "calibration": calibration,
                    "penalties": request.ridge_penalties, "clipping": request.clipping, "quantization": request.quantization, "split_mode": request.split_mode}).encode()).hexdigest(),
                data_kind=train[0].data_kind, cohorts=tuple(sorted({c.cohort for c in all_cases(train, tune, calibration)})))
    provisional = FittedModel.model_validate(core)
    scores = tuple(sorted(abs(c.length - point_length(provisional, c.landmark)) for c in calibration))
    core["calibration_scores"] = scores
    return FittedModel.model_validate(core)


def all_cases(*groups: tuple[LabelledCase, ...]) -> tuple[LabelledCase, ...]:
    return sum(groups, ())
