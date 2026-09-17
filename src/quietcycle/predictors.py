"""A deterministic historical baseline. No population fit or clinical calibration is claimed."""
from __future__ import annotations

from bisect import bisect_right
from dataclasses import asdict, dataclass
from fractions import Fraction
from hashlib import sha256
from typing import Protocol

from .dates import add_days, day_difference
from .errors import InputError
from .features import Features
from .models import Forecast, ForecastAudit, MassPoint, ModelInterval, Probability, Query
from .serialization import canonical_json

SCALE = 1000000


@dataclass(frozen=True)
class Policy:
    min_history: int = 3
    max_history: int = 6
    min_length: int = 10
    max_length: int = 180
    bandwidth: int = 2
    max_spread: int = 20
    min_survival_ppm: int = 100000
    min_remaining_days: int = 3

    def __post_init__(self) -> None:
        if any(type(value) is not int for value in asdict(self).values()):
            raise InputError("policy_requires_integers")
        if not (1 <= self.min_history <= self.max_history <= 100 and
                0 <= self.bandwidth <= 14 and self.bandwidth < self.min_length <= self.max_length <= 1000 and
                0 <= self.max_spread <= 1000 and 0 <= self.min_survival_ppm <= SCALE and
                1 <= self.min_remaining_days <= 1000):
            raise InputError("invalid_policy")


class Predictor(Protocol):
    model_id: str
    model_version: str
    used_features: tuple[str, ...]

    def predict(self, features: Features, query: Query) -> Forecast: ...


def kernel_weights(lengths: tuple[int, ...], bandwidth: int = 2) -> tuple[tuple[int, int], ...]:
    if type(bandwidth) is not int or not 0 <= bandwidth <= 14 or not 1 <= len(lengths) <= 100:
        raise InputError("invalid_kernel")
    counts: dict[int, int] = {}
    for length in lengths:
        if type(length) is not int or not bandwidth < length <= 10000:
            raise InputError("invalid_kernel_length")
        for delta in range(-bandwidth, bandwidth + 1):
            day = length + delta
            counts[day] = counts.get(day, 0) + bandwidth + 1 - abs(delta)
    return tuple(sorted(counts.items()))


def allocate_ppm(weights: tuple[int, ...]) -> tuple[int, ...]:
    if not weights or any(type(x) is not int or x < 0 for x in weights) or sum(weights) == 0:
        raise InputError("invalid_weights")
    total = sum(weights)
    floors = [w * SCALE // total for w in weights]
    order = sorted(range(len(weights)), key=lambda i: (-(weights[i] * SCALE % total), i))
    for i in order[:SCALE - sum(floors)]:
        floors[i] += 1
    return tuple(floors)


def _quantile(rows: tuple[tuple[int, int], ...], total: int, ppm: int) -> int:
    cumulative = 0
    for day, weight in rows:
        cumulative += weight
        if cumulative * SCALE >= total * ppm:
            return day
    return rows[-1][0]


class EmpiricalPredictor:
    model_id = "empirical-triangle-v1"
    used_features: tuple[str, ...] = ("onset", "no-onset", "context")

    def __init__(self, policy: Policy | None = None) -> None:
        self.policy = policy or Policy()
        # Distinct policy settings cannot silently reuse the same model version.
        self.model_version = "p-" + sha256(canonical_json(asdict(self.policy)).encode()).hexdigest()[:16]

    def predict(self, features: Features, query: Query) -> Forecast:
        policy = self.policy
        audit: dict[str, object] = {}

        def stop(reason: str) -> Forecast:
            return Forecast(model_id=self.model_id, model_version=self.model_version,
                            status="abstain", reason=reason, audit=ForecastAudit.model_validate(audit))

        if query.context.paused:
            return stop("paused")
        if query.context.mode != "natural-cycle":
            return stop("outside-declared-scope")
        if features.conflicting_onsets:
            return stop("conflicting-onsets")
        if not features.onsets:
            return stop("no-confirmed-onset")
        anchor = features.onsets[-1]
        if anchor.certainty != "confirmed":
            return stop("uncertain-current-onset")
        if anchor.exclude_from_history:
            return stop("current-onset-excluded")
        audit["anchor_date"] = anchor.date
        by_id = {onset.id: onset for onset in features.onsets}
        onset_dates = tuple(onset.date for onset in features.onsets)
        for report in features.no_onset:
            origin = by_id.get(report.anchor_id)
            if origin is None or origin.certainty != "confirmed":
                return stop("orphan-no-onset-report")
            if report.through < origin.date:
                raise InputError("report_before_anchor")
            if bisect_right(onset_dates, report.through) > bisect_right(onset_dates, origin.date):
                return stop("conflicting-no-onset-report")
        recent = tuple(i for i in features.intervals if not i.changed)[-policy.max_history:]
        audit["interval_count"] = len(recent)
        if len(recent) < policy.min_history:
            return stop("insufficient-history")
        if any(not interval.known for interval in recent):
            return stop("unconfirmed-continuity")
        if any(interval.excluded for interval in recent):
            return stop("excluded-recent-interval")
        lengths = tuple(interval.length for interval in recent)
        audit["history_lengths"] = lengths
        if any(c < policy.min_length or c > policy.max_length for c in lengths):
            return stop("outside-model-support")
        if max(lengths) - min(lengths) > policy.max_spread:
            return stop("high-observed-variation")
        all_rows = kernel_weights(lengths, policy.bandwidth)
        try:
            add_days(anchor.date, all_rows[-1][0])
            add_days(query.as_of, 2)
        except ValueError:
            return stop("date-domain-limit")
        reports = tuple(r for r in features.no_onset if r.anchor_id == anchor.id)
        through = max(r.through for r in reports) if reports else anchor.date
        audit["no_onset_through"] = through if reports else None
        confirmed = day_difference(through, anchor.date)
        rows = tuple((day, weight) for day, weight in all_rows if day > confirmed)
        original, total = sum(w for _, w in all_rows), sum(w for _, w in rows)
        audit["survival_mass"] = Probability.from_fraction(Fraction(total, original))
        if total == 0:
            return stop("support-exhausted")
        today = day_difference(query.as_of, anchor.date)
        past = sum(weight for day, weight in rows if day < today)
        audit["unresolved_past_mass"] = Probability.from_fraction(Fraction(past, total))
        if past:
            return stop("onset-status-unconfirmed")
        if total * SCALE < original * policy.min_survival_ppm or len(rows) < policy.min_remaining_days:
            return stop("weak-remaining-support")
        allocation = allocate_ppm(tuple(weight for _, weight in rows))
        distribution = tuple(MassPoint(date=add_days(anchor.date, day), cycle_length=day,
                                      mass=Probability.from_fraction(Fraction(weight, total)), ppm=allocation[i])
                             for i, (day, weight) in enumerate(rows))
        intervals = []
        for target in (800000, 900000):
            tail = (SCALE - target) // 2
            lower, upper = _quantile(rows, total, tail), _quantile(rows, total, SCALE - tail)
            included = sum(w for d, w in rows if lower <= d <= upper)
            intervals.append(ModelInterval(start=add_days(anchor.date, lower), end=add_days(anchor.date, upper),
                                           requested_mass_ppm=target,
                                           included_mass=Probability.from_fraction(Fraction(included, total))))
        near = sum(weight for day, weight in rows if today <= day < today + 3)
        return Forecast(
            model_id=self.model_id, model_version=self.model_version, status="estimate",
            reason="historical-model-only", point_date=add_days(anchor.date, _quantile(rows, total, 500000)),
            distribution=distribution, intervals=tuple(intervals),
            within_three_days=Probability.from_fraction(Fraction(near, total)),
            audit=ForecastAudit.model_validate(audit),
        )
