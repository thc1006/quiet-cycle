"""Version 2 wire contract and immutable public data objects.

Decimals are strings. Record times are instants; event dates are civil dates.
Unknown fields and implicit numeric coercions are rejected.
"""
from __future__ import annotations

from fractions import Fraction
from typing import Annotated, Any, Literal, Self, TypeAlias

from pydantic import (
    AfterValidator, BaseModel, BeforeValidator, ConfigDict, Field,
    StrictBool, StrictInt, StringConstraints, TypeAdapter, model_validator,
)

from .dates import DATE_PATTERN, INSTANT_PATTERN, civil, instant, local_day

SCHEMA_VERSION = "2.0"
VERSION = "0.3.0"

CivilDate = Annotated[str, StringConstraints(strict=True, pattern=DATE_PATTERN), AfterValidator(civil)]
Instant = Annotated[str, StringConstraints(strict=True, pattern=INSTANT_PATTERN), AfterValidator(instant)]
Identifier = Annotated[str, StringConstraints(strict=True, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,95}$")]
DecimalText = Annotated[str, StringConstraints(strict=True, pattern=r"^-?(?:0|[1-9][0-9]{0,11})(?:\.[0-9]{1,12})?$")]
Unit = Annotated[str, StringConstraints(strict=True, min_length=1, max_length=32, pattern=r"^[A-Za-z0-9\[\]{}./%_-]+$")]
Offset = Annotated[StrictInt, Field(ge=-840, le=840)]


def _tuple(value: Any) -> tuple[Any, ...]:
    if not isinstance(value, (list, tuple)):
        raise ValueError("array_required")
    return tuple(value)


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, validate_default=True,
                              revalidate_instances="always")


class Provenance(Model):
    source: Identifier = "manual"
    source_record_id: Identifier | None = None
    imported_at: Instant | None = None


class EventBase(Model):
    subject_id: Identifier
    id: Identifier
    revision: Annotated[StrictInt, Field(ge=1, le=100000)] = 1
    recorded_at: Instant
    utc_offset_minutes: Offset
    provenance: Provenance = Field(default_factory=Provenance)

    @property
    def available_at(self) -> str:
        return max(self.recorded_at, self.provenance.imported_at or self.recorded_at)


class DatedEvent(EventBase):
    date: CivilDate

    @model_validator(mode="after")
    def occurred_before_report(self) -> Self:
        if self.date > local_day(self.recorded_at, self.utc_offset_minutes):
            raise ValueError("future_observation")
        return self


class Onset(DatedEvent):
    kind: Literal["onset"] = "onset"
    certainty: Literal["confirmed", "uncertain"]
    previous_onset_id: Identifier | None = None
    continuity: Literal["confirmed", "unknown"] = "unknown"
    exclude_from_history: StrictBool = False

    @model_validator(mode="after")
    def previous_reference(self) -> Self:
        if self.previous_onset_id == self.id:
            raise ValueError("self_reference")
        if self.continuity == "confirmed" and self.previous_onset_id is None:
            raise ValueError("continuity_requires_reference")
        return self


class NoOnset(EventBase):
    kind: Literal["no-onset"] = "no-onset"
    anchor_id: Identifier
    through: CivilDate

    @model_validator(mode="after")
    def completed_day(self) -> Self:
        if self.through >= local_day(self.recorded_at, self.utc_offset_minutes):
            raise ValueError("incomplete_day")
        return self


class Symptom(DatedEvent):
    kind: Literal["symptom"] = "symptom"
    symptom: Identifier
    state: Literal["present", "absent", "uncertain", "skipped"]
    impact: Annotated[StrictInt, Field(ge=0, le=3)] | None = None

    @model_validator(mode="after")
    def consistent_impact(self) -> Self:
        if self.state != "present" and self.impact is not None:
            raise ValueError("impact_without_present_symptom")
        return self


class Checkin(DatedEvent):
    kind: Literal["checkin"] = "checkin"
    state: Literal["marked", "none", "uncertain", "skipped"]


class Bleeding(DatedEvent):
    """A bleeding report is deliberately not an Onset."""
    kind: Literal["bleeding"] = "bleeding"
    state: Literal["none", "spotting", "flow", "uncertain"]


class Measurement(DatedEvent):
    kind: Literal["measurement"] = "measurement"
    metric: Identifier
    state: Literal["measured", "missing"] = "measured"
    value: DecimalText | None
    unit: Unit
    measured_at: Instant
    method: Identifier | None = None
    body_site: Identifier | None = None
    missing_reason: Identifier | None = None

    @model_validator(mode="after")
    def measured_value(self) -> Self:
        if self.measured_at > self.recorded_at:
            raise ValueError("measurement_after_report")
        if local_day(self.measured_at, self.utc_offset_minutes) != self.date:
            raise ValueError("measurement_day_mismatch")
        if self.state == "measured" and (self.value is None or self.missing_reason is not None):
            raise ValueError("inconsistent_measurement")
        if self.state == "missing" and (self.value is not None or self.missing_reason is None):
            raise ValueError("inconsistent_missing_measurement")
        return self


EventKind = Literal["onset", "no-onset", "symptom", "checkin", "bleeding", "measurement"]


class Tombstone(EventBase):
    kind: Literal["delete"] = "delete"
    target_kind: EventKind


Event: TypeAlias = Annotated[
    Onset | NoOnset | Symptom | Checkin | Bleeding | Measurement | Tombstone,
    Field(discriminator="kind"),
]
EVENT_ADAPTER: TypeAdapter[Event] = TypeAdapter(Event)
EventTuple = Annotated[tuple[Event, ...], BeforeValidator(_tuple), Field(max_length=50000)]


class CycleDataset(Model):
    schema_version: Literal["2.0"] = "2.0"
    events: EventTuple

    def merge(self, *others: CycleDataset) -> CycleDataset:
        """Exact duplicates are idempotent. Same identity/version with new content is an error."""
        from .errors import InputError
        unique: dict[tuple[str, str, int], Event] = {}
        for dataset in (self, *others):
            for event in dataset.events:
                key = (event.subject_id, event.id, event.revision)
                if key in unique and unique[key] != event:
                    raise InputError("conflicting_revision")
                unique[key] = event
        return CycleDataset(events=tuple(unique[k] for k in sorted(unique)))


class CycleContext(Model):
    # No silent assumption about hormones or natural ovulation.
    mode: Literal["natural-cycle", "other", "unknown"]
    changed_since: CivilDate | None = None
    paused: StrictBool = False


class Query(Model):
    subject_id: Identifier
    as_of: CivilDate
    cutoff: Instant
    utc_offset_minutes: Offset
    context: CycleContext

    @model_validator(mode="after")
    def query_day(self) -> Self:
        if local_day(self.cutoff, self.utc_offset_minutes) != self.as_of:
            raise ValueError("cutoff_day_mismatch")
        if self.context.changed_since is not None and self.context.changed_since > self.as_of:
            raise ValueError("future_context_change")
        return self


class PipelineRequest(Model):
    schema_version: Literal["2.0"] = "2.0"
    dataset: CycleDataset
    query: Query


class Rational(Model):
    numerator: Annotated[str, StringConstraints(strict=True, pattern=r"^-?(?:0|[1-9][0-9]*)$", max_length=2048)]
    denominator: Annotated[str, StringConstraints(strict=True, pattern=r"^[1-9][0-9]*$", max_length=2048)]

    @model_validator(mode="after")
    def reduced(self) -> Self:
        f = Fraction(int(self.numerator), int(self.denominator))
        if str(f.numerator) != self.numerator or str(f.denominator) != self.denominator:
            raise ValueError("fraction_must_be_reduced")
        return self

    @classmethod
    def from_fraction(cls, value: Fraction) -> Rational:
        from .errors import InputError
        if max(abs(value.numerator).bit_length(), value.denominator.bit_length()) > 6800:
            raise InputError("fraction_precision_budget")
        return cls(numerator=str(value.numerator), denominator=str(value.denominator))

    def as_fraction(self) -> Fraction:
        return Fraction(int(self.numerator), int(self.denominator))


class Probability(Rational):
    @model_validator(mode="after")
    def bounded(self) -> Self:
        if not 0 <= self.as_fraction() <= 1:
            raise ValueError("probability_outside_unit_interval")
        return self

    @classmethod
    def from_fraction(cls, value: Fraction) -> Probability:
        from .errors import InputError
        if max(abs(value.numerator).bit_length(), value.denominator.bit_length()) > 6800:
            raise InputError("fraction_precision_budget")
        return cls(numerator=str(value.numerator), denominator=str(value.denominator))


class MassPoint(Model):
    date: CivilDate
    cycle_length: Annotated[StrictInt, Field(ge=1)]
    mass: Probability
    ppm: Annotated[StrictInt, Field(ge=0, le=1000000)]


class ModelInterval(Model):
    start: CivilDate
    end: CivilDate
    requested_mass_ppm: Annotated[StrictInt, Field(gt=0, le=1000000)]
    included_mass: Probability
    calibrated: Literal[False] = False

    @model_validator(mode="after")
    def ordered(self) -> Self:
        if self.start > self.end:
            raise ValueError("reversed_interval")
        return self


class ForecastAudit(Model):
    history_lengths: Annotated[tuple[StrictInt, ...], BeforeValidator(_tuple)] = ()
    interval_count: Annotated[StrictInt, Field(ge=0)] = 0
    anchor_date: CivilDate | None = None
    no_onset_through: CivilDate | None = None
    survival_mass: Probability | None = None
    unresolved_past_mass: Probability | None = None


class Forecast(Model):
    model_id: Identifier
    model_version: Identifier
    status: Literal["estimate", "abstain"]
    reason: Identifier
    point_date: CivilDate | None = None
    distribution: Annotated[tuple[MassPoint, ...], BeforeValidator(_tuple)] = ()
    intervals: Annotated[tuple[ModelInterval, ...], BeforeValidator(_tuple)] = ()
    within_three_days: Probability | None = None
    calibration: Literal["unvalidated"] = "unvalidated"
    unmodeled_risk: Literal["not-quantified"] = "not-quantified"
    audit: ForecastAudit = Field(default_factory=ForecastAudit)

    @model_validator(mode="after")
    def consistency(self) -> Self:
        if self.status == "abstain":
            if self.point_date is not None or self.distribution or self.intervals or self.within_three_days is not None:
                raise ValueError("abstention_has_prediction")
        else:
            if self.point_date is None or not self.distribution or self.within_three_days is None:
                raise ValueError("estimate_missing_distribution")
            if any(p.mass.as_fraction() <= 0 for p in self.distribution):
                raise ValueError("nonpositive_distribution_mass")
            if sum((p.mass.as_fraction() for p in self.distribution), Fraction()) != 1:
                raise ValueError("mass_not_conserved")
            if sum(p.ppm for p in self.distribution) != 1000000:
                raise ValueError("display_mass_not_conserved")
            days = [p.date for p in self.distribution]
            if days != sorted(set(days)) or self.point_date not in days:
                raise ValueError("invalid_distribution_order")
            for interval in self.intervals:
                included = sum((p.mass.as_fraction() for p in self.distribution
                                if interval.start <= p.date <= interval.end), Fraction())
                if included != interval.included_mass.as_fraction():
                    raise ValueError("interval_mass_mismatch")
        return self


class NormalizedMeasurement(Model):
    event_id: Identifier
    date: CivilDate
    measured_at: Instant
    available_at: Instant
    metric: Identifier
    value: Rational | None
    unit: Unit
    state: Literal["measured", "missing"]
    source: Identifier
    method: Identifier | None = None
    body_site: Identifier | None = None
    used_by_default_model: Literal[False] = False


class SymptomCounts(Model):
    symptom: Identifier
    present: Annotated[StrictInt, Field(ge=0)]
    absent: Annotated[StrictInt, Field(ge=0)]
    uncertain: Annotated[StrictInt, Field(ge=0)]
    skipped: Annotated[StrictInt, Field(ge=0)]
    conflicting_days: Annotated[StrictInt, Field(ge=0)]
    recalled_reports: Annotated[StrictInt, Field(ge=0)]
    interpretation: Literal["recorded-days-only-not-a-risk-or-diagnosis"] = "recorded-days-only-not-a-risk-or-diagnosis"


class PipelineResult(Model):
    schema_version: Literal["2.0"] = "2.0"
    engine_version: str = VERSION
    subject_id: Identifier
    as_of: CivilDate
    cutoff: Instant
    snapshot_sha256: Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{64}$")]
    forecast: Forecast
    measurements: Annotated[tuple[NormalizedMeasurement, ...], BeforeValidator(_tuple)] = ()
    symptoms: Annotated[tuple[SymptomCounts, ...], BeforeValidator(_tuple)] = ()
    observation_count: Annotated[StrictInt, Field(ge=0)]
    feature_builder_id: Identifier
    used_features: Annotated[tuple[Identifier, ...], BeforeValidator(_tuple)]
