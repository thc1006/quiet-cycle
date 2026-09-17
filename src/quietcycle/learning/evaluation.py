"""Held-out evaluation. Attempt counts, abstentions and unbounded sets stay visible."""
from __future__ import annotations

from fractions import Fraction
from typing import Any

from ..dates import day_difference
from ..errors import InputError
from ..models import Rational
from ..serialization import parse_model
from .contracts import FittedModel, LabelledCase
from .exact import round_day
from .prediction import predict_landmark


def evaluate(model: FittedModel, cases: tuple[LabelledCase, ...]) -> dict[str, Any]:
    model = parse_model(FittedModel, model)
    cases = tuple(parse_model(LabelledCase, c) for c in cases)
    keys = [(c.landmark.subject_id, c.landmark.anchor_id) for c in cases]
    if len(keys) != len(set(keys)):
        raise InputError("duplicate-evaluation-cycle")
    if model.split_mode == "new-subject" and len({c.landmark.subject_id for c in cases}) != len(cases):
        raise InputError("one-test-case-per-subject-required")
    if len(cases) > 5000:
        raise InputError("evaluation-budget")
    errors: list[int] = []
    baseline_errors: list[int] = []
    covered = {800000: 0, 900000: 0}
    widths: dict[int, list[int]] = {800000: [], 900000: []}
    unbounded = {800000: 0, 900000: 0}
    abstentions: dict[str, int] = {}
    outputs: list[dict[str, Any]] = []
    for case in cases:
        if case.data_kind != model.data_kind:
            raise InputError("evaluation-data-kind-mismatch")
        result = predict_landmark(model, case.landmark)
        if result.status == "abstain":
            abstentions[result.reason] = abstentions.get(result.reason, 0) + 1
        else:
            assert result.point_cycle_length is not None
            error = abs(case.length - result.point_cycle_length)
            errors.append(error)
            baseline = max(model.spec.elapsed_day, round_day(case.landmark.baseline_length.as_fraction()))
            baseline_errors.append(abs(case.length - baseline))
            for interval in result.intervals:
                target = interval.nominal_coverage_ppm
                if interval.unbounded:
                    unbounded[target] += 1
                    covered[target] += 1
                else:
                    assert interval.start is not None and interval.end is not None
                    covered[target] += int(interval.start <= case.outcome_date <= interval.end)
                    widths[target].append(day_difference(interval.end, interval.start) + 1)
        # No subject IDs or raw health measurements in the aggregate report.
        outputs.append({"status": result.status, "reason": result.reason})
    def average(values: list[int]) -> Rational | None:
        return Rational.from_fraction(Fraction(sum(values), len(values))) if values else None
    return {
        "data_kind": model.data_kind, "clinical_validation": "not-established",
        "attempted": len(cases), "estimated": len(errors), "abstained": len(cases) - len(errors),
        "abstention_reasons": dict(sorted(abstentions.items())),
        "mae_days": average(errors), "mse_days_squared": average([e * e for e in errors]),
        "baseline_mae_same_estimated_cases": average(baseline_errors),
        "max_error_days": max(errors) if errors else None,
        "within_one_day": sum(e <= 1 for e in errors), "within_three_days": sum(e <= 3 for e in errors),
        "intervals": [{"nominal_coverage_ppm": p, "covered": covered[p], "denominator": len(errors),
                       "unbounded": unbounded[p], "mean_finite_width_dates": average(widths[p])} for p in (800000, 900000)],
        "attempt_statuses": outputs,
        "warning": "Complete-labelled eligible cases only; report build_cases rejections separately. Not a clinical benchmark.",
    }
