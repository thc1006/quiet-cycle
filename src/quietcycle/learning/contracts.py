"""Versioned contracts for a fitted, fixed-landmark residual model.

Artifacts contain fitted statistics, not executable pickles. They remain sensitive:
subject hashes and small-sample coefficients are not anonymization.
"""
from __future__ import annotations

from typing import Annotated, Literal, Self

from pydantic import BeforeValidator, Field, StrictBool, StrictInt, StringConstraints, model_validator

from ..dates import day_difference, local_day
from ..models import CivilDate, Identifier, Instant, Model, Query, Rational, _tuple

Hash = Annotated[str, StringConstraints(strict=True, pattern=r"^[a-f0-9]{64}$")]
Names = Annotated[tuple[Identifier, ...], BeforeValidator(_tuple)]


class LandmarkSpec(Model):
    # Elapsed days, zero at onset. An artifact only applies at this landmark.
    elapsed_day: Annotated[StrictInt, Field(ge=1, le=180)] = 20
    min_history: Annotated[StrictInt, Field(ge=1, le=30)] = 3
    max_history: Annotated[StrictInt, Field(ge=1, le=30)] = 12
    recent_days: Annotated[StrictInt, Field(ge=1, le=14)] = 3
    reference_days: Annotated[StrictInt, Field(ge=1, le=30)] = 7
    minimum_measurement_days: Annotated[StrictInt, Field(ge=1, le=14)] = 2
    metrics: Names = ("wrist_temperature", "resting_heart_rate", "hrv_rmssd", "sleep_duration")
    symptoms: Names = ("headache", "fatigue", "abdominal_pain", "gastrointestinal")

    @model_validator(mode="after")
    def valid(self) -> Self:
        if self.min_history > self.max_history:
            raise ValueError("invalid_history_window")
        if self.recent_days + self.reference_days > self.elapsed_day:
            raise ValueError("landmark_before_observation_windows")
        if self.minimum_measurement_days > min(self.recent_days, self.reference_days):
            raise ValueError("measurement_days_exceed_window")
        if len(self.metrics) > 8 or len(self.symptoms) > 8:
            raise ValueError("feature_budget")
        if len(set(self.metrics)) != len(self.metrics) or len(set(self.symptoms)) != len(self.symptoms):
            raise ValueError("duplicate_feature")
        return self


def expected_feature_names(spec: LandmarkSpec) -> tuple[str, ...]:
    names = ["history.median", "history.last", "history.mad", "history.change", "history.count"]
    names.extend(f"measurement.{metric}.{stat}" for metric in spec.metrics for stat in ("recent", "delta"))
    names.extend(f"symptom.{symptom}.{stat}" for symptom in spec.symptoms for stat in ("rate", "impact"))
    return tuple(sorted(names))


class FeatureValue(Model):
    name: Identifier
    value: Rational | None


Values = Annotated[tuple[FeatureValue, ...], BeforeValidator(_tuple), Field(max_length=64)]


class Landmark(Model):
    subject_id: Identifier
    anchor_id: Identifier
    anchor_date: CivilDate
    query: Query
    spec_sha256: Hash
    snapshot_sha256: Hash
    baseline_length: Rational
    values: Values
    issues: Names = ()

    @model_validator(mode="after")
    def valid(self) -> Self:
        if self.subject_id != self.query.subject_id:
            raise ValueError("subject_mismatch")
        if self.anchor_date >= self.query.as_of:
            raise ValueError("invalid_anchor")
        names = [x.name for x in self.values]
        if names != sorted(set(names)):
            raise ValueError("feature_order")
        for item in self.values:
            if item.value is not None:
                f = item.value.as_fraction()
                if max(abs(f.numerator).bit_length(), f.denominator.bit_length()) > 256:
                    raise ValueError("feature_precision_budget")
        if self.baseline_length.as_fraction() <= 0:
            raise ValueError("invalid_baseline")
        historical = next((v.value for v in self.values if v.name == "history.median"), None)
        if historical is None or historical != self.baseline_length:
            raise ValueError("baseline_history_mismatch")
        return self


class LabelledCase(Model):
    landmark: Landmark
    outcome_date: CivilDate
    outcome_known_at: Instant
    # This describes supplied data, not a claim made by the library.
    data_kind: Literal["synthetic", "observational"]
    cohort: Identifier

    @model_validator(mode="after")
    def valid(self) -> Self:
        q = self.landmark.query
        if self.outcome_date < q.as_of or self.outcome_known_at <= q.cutoff:
            raise ValueError("outcome_not_future_to_prediction")
        if self.outcome_date > local_day(self.outcome_known_at, q.utc_offset_minutes):
            raise ValueError("label_available_before_event")
        return self

    @property
    def length(self) -> int:
        return day_difference(self.outcome_date, self.landmark.anchor_date)


Cases = Annotated[tuple[LabelledCase, ...], BeforeValidator(_tuple), Field(max_length=5000)]


class FitRequest(Model):
    schema_version: Literal["learning-1.0"] = "learning-1.0"
    spec: LandmarkSpec = Field(default_factory=LandmarkSpec)
    train: Cases
    tune: Cases
    calibration: Cases
    ridge_penalties: Annotated[tuple[StrictInt, ...], BeforeValidator(_tuple)] = (1, 10, 100)
    split_mode: Literal["new-subject", "forward-personal"] = "new-subject"
    # Clipping is a numerical robustness choice, not a physiological normal range.
    clipping: Annotated[StrictInt, Field(ge=1, le=100)] = 8
    quantization: Annotated[StrictInt, Field(ge=1, le=1000000)] = 1000

    @model_validator(mode="after")
    def valid(self) -> Self:
        if not 1 <= len(self.ridge_penalties) <= 8 or any(x <= 0 for x in self.ridge_penalties):
            raise ValueError("positive_ridge_penalties_required")
        if tuple(sorted(set(self.ridge_penalties))) != self.ridge_penalties:
            raise ValueError("penalties_must_be_sorted_unique")
        if len(self.train) < 8 or len(self.tune) < 4 or len(self.calibration) < 1:
            raise ValueError("insufficient_development_cases")
        return self


class ScaleColumn(Model):
    name: Identifier
    center: Rational
    scale: Rational
    observed_in_train: StrictBool

    @model_validator(mode="after")
    def valid(self) -> Self:
        if self.scale.as_fraction() <= 0:
            raise ValueError("nonpositive_scale")
        return self


class LinearCandidate(Model):
    name: Identifier
    penalty: Annotated[StrictInt, Field(ge=0)]
    terms: Names
    coefficients: Annotated[tuple[Rational, ...], BeforeValidator(_tuple), Field(max_length=128)]
    blend: Rational
    tune_mse: Rational

    @model_validator(mode="after")
    def valid(self) -> Self:
        if len(self.coefficients) != len(self.terms) or len(set(self.terms)) != len(self.terms):
            raise ValueError("coefficient_shape")
        if not 0 <= self.blend.as_fraction() <= 1 or self.tune_mse.as_fraction() < 0:
            raise ValueError("invalid_candidate")
        return self


class FittedModel(Model):
    schema_version: Literal["learning-1.0"] = "learning-1.0"
    algorithm: Literal["exact-landmark-ridge-ensemble-v1"] = "exact-landmark-ridge-ensemble-v1"
    spec: LandmarkSpec
    columns: Annotated[tuple[ScaleColumn, ...], BeforeValidator(_tuple), Field(max_length=64)]
    clipping: Annotated[StrictInt, Field(ge=1, le=100)]
    quantization: Annotated[StrictInt, Field(ge=1, le=1000000)]
    selected: LinearCandidate
    candidates: Annotated[tuple[LinearCandidate, ...], BeforeValidator(_tuple), Field(max_length=33)]
    calibration_scores: Annotated[tuple[StrictInt, ...], BeforeValidator(_tuple)]
    train_count: Annotated[StrictInt, Field(ge=8)]
    tune_count: Annotated[StrictInt, Field(ge=4)]
    calibration_count: Annotated[StrictInt, Field(ge=1)]
    train_subject_hashes: Annotated[tuple[Hash, ...], BeforeValidator(_tuple)]
    tune_subject_hashes: Annotated[tuple[Hash, ...], BeforeValidator(_tuple)]
    calibration_subject_hashes: Annotated[tuple[Hash, ...], BeforeValidator(_tuple)]
    split_mode: Literal["new-subject", "forward-personal"]
    fitted_at: Instant
    available_at: Instant
    training_digest: Hash
    data_kind: Literal["synthetic", "observational"]
    cohorts: Names
    clinical_validation: Literal["not-established"] = "not-established"

    @model_validator(mode="after")
    def valid(self) -> Self:
        if self.selected not in self.candidates:
            raise ValueError("selected_candidate_missing")
        if self.available_at < self.fitted_at:
            raise ValueError("model_time_order")
        names = [c.name for c in self.columns]
        if tuple(names) != expected_feature_names(self.spec):
            raise ValueError("column_order_or_schema")
        all_terms = set(names) | {"missing." + n for n in names} | {"intercept"}
        if "measurement.wrist_temperature.delta" in names and "measurement.resting_heart_rate.delta" in names:
            all_terms.add("interaction.temperature_heart")
        if "symptom.fatigue.rate" in names and "measurement.sleep_duration.delta" in names:
            all_terms.add("interaction.fatigue_sleep")
        if len({c.name for c in self.candidates}) != len(self.candidates):
            raise ValueError("duplicate_candidate")
        for candidate in self.candidates:
            if any(t not in all_terms for t in candidate.terms):
                raise ValueError("unknown_model_term")
            if candidate.name == "baseline":
                if candidate.terms or candidate.penalty or candidate.blend.as_fraction():
                    raise ValueError("invalid_baseline_candidate")
            elif not candidate.terms or candidate.terms[0] != "intercept" or candidate.penalty <= 0:
                raise ValueError("invalid_ridge_candidate")
        if len(self.calibration_scores) != self.calibration_count:
            raise ValueError("calibration_count_mismatch")
        if list(self.calibration_scores) != sorted(self.calibration_scores) or any(x < 0 for x in self.calibration_scores):
            raise ValueError("invalid_calibration_scores")
        for group in (self.train_subject_hashes, self.tune_subject_hashes, self.calibration_subject_hashes):
            if tuple(sorted(set(group))) != group:
                raise ValueError("subject_hash_order")
        if self.split_mode == "new-subject":
            groups = [set(self.train_subject_hashes), set(self.tune_subject_hashes), set(self.calibration_subject_hashes)]
            if any(groups[i] & groups[j] for i in range(3) for j in range(i)):
                raise ValueError("subject_overlap")
            if len(self.calibration_subject_hashes) != self.calibration_count:
                raise ValueError("calibration_subject_not_independent_unit")
        return self


class CalibratedInterval(Model):
    nominal_coverage_ppm: Annotated[StrictInt, Field(gt=0, lt=1000000)]
    start: CivilDate | None
    end: CivilDate | None
    radius_days: Annotated[StrictInt, Field(ge=0)] | None
    unbounded: StrictBool
    assumption: Literal["exchangeable-new-subjects-required", "dependent-time-series-no-coverage-guarantee"]

    @model_validator(mode="after")
    def valid(self) -> Self:
        if self.unbounded:
            if any(v is not None for v in (self.start, self.end, self.radius_days)):
                raise ValueError("unbounded_interval_has_bounds")
        elif self.start is None or self.end is None or self.radius_days is None or self.start > self.end:
            raise ValueError("invalid_interval")
        return self


class Contribution(Model):
    term: Identifier
    days: Rational


class LearnedPrediction(Model):
    schema_version: Literal["learning-1.0"] = "learning-1.0"
    model_sha256: Hash
    subject_id: Identifier
    as_of: CivilDate
    cutoff: Instant
    status: Literal["estimate", "abstain"]
    reason: Identifier
    point_date: CivilDate | None = None
    point_cycle_length: Annotated[StrictInt, Field(ge=1)] | None = None
    raw_cycle_length: Rational | None = None
    baseline_cycle_length: Rational | None = None
    intervals: Annotated[tuple[CalibratedInterval, ...], BeforeValidator(_tuple)] = ()
    contributions: Annotated[tuple[Contribution, ...], BeforeValidator(_tuple)] = ()
    issues: Names = ()
    clinical_validation: Literal["not-established"] = "not-established"

    @model_validator(mode="after")
    def valid(self) -> Self:
        if self.status == "abstain":
            if any(v is not None for v in (self.point_date, self.point_cycle_length, self.raw_cycle_length, self.baseline_cycle_length)) or self.intervals or self.contributions:
                raise ValueError("abstention_has_estimate")
        else:
            if any(v is None for v in (self.point_date, self.point_cycle_length, self.raw_cycle_length, self.baseline_cycle_length)):
                raise ValueError("estimate_missing_fields")
            if self.point_date is not None and self.point_date < self.as_of:
                raise ValueError("past_prediction")
        return self
