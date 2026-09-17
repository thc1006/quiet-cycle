"""Optional measurement-to-state evidence wiring. Rules must come from the caller.

This demonstrates the full data path without shipping invented hormone thresholds.
Only the latest eligible sample per rule is used; no hidden averaging or interpolation.
"""
from __future__ import annotations

from hashlib import sha256
from typing import Annotated, Literal, Self

from pydantic import BeforeValidator, Field, StrictInt, model_validator

from ..dates import day_difference
from ..errors import InputError
from ..features import DefaultFeatureBuilder, FeatureBuilder
from ..ledger import snapshot
from ..models import (
    CycleDataset, Identifier, Model, Query, Rational, Unit, _tuple,
)
from ..serialization import canonical_json, parse_model
from .duration import DurationModel, DurationResult, duration_forecast


class EvidenceRule(Model):
    metric: Identifier
    unit: Unit
    source: Identifier | None = None
    # All ranges are [lower, upper); null leaves that side unbounded.
    lower: Rational | None = None
    upper: Rational | None = None
    weights_inside: Annotated[tuple[StrictInt, ...], BeforeValidator(_tuple)]
    weights_outside: Annotated[tuple[StrictInt, ...], BeforeValidator(_tuple)]
    max_age_days: Annotated[StrictInt, Field(ge=0, le=30)]

    @model_validator(mode="after")
    def bounds(self) -> Self:
        if self.lower is not None and self.upper is not None and self.lower.as_fraction() >= self.upper.as_fraction():
            raise ValueError("empty_evidence_range")
        for weights in (self.weights_inside, self.weights_outside):
            if not weights or len(weights) > 8 or any(w < 0 or w > 1000000 for w in weights):
                raise ValueError("invalid_evidence_weights")
        return self


class ResearchRun(Model):
    schema_version: Literal["2.0"] = "2.0"
    status: Literal["evaluated", "abstain"]
    reason: Identifier
    configuration_sha256: str
    snapshot_sha256: str
    evidence_ids: Annotated[tuple[Identifier, ...], BeforeValidator(_tuple)] = ()
    result: DurationResult | None = None
    interpretation: Literal["caller-parameterized-research-not-a-validated-period-prediction"] = "caller-parameterized-research-not-a-validated-period-prediction"


class DurationResearchPipeline:
    def __init__(self, model: DurationModel, *, rule: EvidenceRule | None = None,
                 horizon: int = 60, feature_builder: FeatureBuilder | None = None) -> None:
        self.model = parse_model(DurationModel, model)
        self.rule = None if rule is None else parse_model(EvidenceRule, rule)
        if self.rule is not None and any(len(w) != len(model.states) for w in (self.rule.weights_inside, self.rule.weights_outside)):
            raise InputError("evidence_state_dimension")
        if type(horizon) is not int or not 1 <= horizon <= 180:
            raise InputError("invalid_horizon")
        self.horizon = horizon
        self.builder = feature_builder or DefaultFeatureBuilder()
        self.configuration_sha256 = sha256(canonical_json({"model": self.model, "rule": self.rule,
                                                           "horizon": horizon, "feature_builder_id": self.builder.builder_id}).encode()).hexdigest()

    def run(self, dataset: CycleDataset, query: Query) -> ResearchRun:
        dataset, query = parse_model(CycleDataset, dataset), parse_model(Query, query)
        selected = snapshot(dataset, query)
        features = self.builder.build(selected, query)
        if features.snapshot_sha256 != selected.sha256:
            raise InputError("feature_provenance_mismatch")
        common = {"configuration_sha256": self.configuration_sha256, "snapshot_sha256": selected.sha256}
        if query.context.paused or query.context.mode != "natural-cycle":
            return ResearchRun(status="abstain", reason="outside-declared-scope", **common)
        weights: tuple[int, ...] | None = None
        evidence_ids: tuple[str, ...] = ()
        if self.rule is not None:
            rule = self.rule
            candidates = [m for m in features.measurements
                          if m.metric == rule.metric and m.unit == rule.unit and m.state == "measured"
                          and (rule.source is None or rule.source == m.source)
                          and 0 <= day_difference(query.as_of, m.date) <= rule.max_age_days]
            if not candidates:
                return ResearchRun(status="abstain", reason="no-eligible-measurement", **common)
            newest = max(m.measured_at for m in candidates)
            latest = [m for m in candidates if m.measured_at == newest]
            if len(latest) != 1:
                return ResearchRun(status="abstain", reason="ambiguous-latest-measurement", **common)
            measurement = latest[0]
            assert measurement.value is not None
            value = measurement.value.as_fraction()
            inside = ((rule.lower is None or value >= rule.lower.as_fraction()) and
                      (rule.upper is None or value < rule.upper.as_fraction()))
            weights = rule.weights_inside if inside else rule.weights_outside
            evidence_ids = (measurement.event_id,)
        result = duration_forecast(self.model, horizon=self.horizon, state_likelihood_weights=weights)
        return ResearchRun(status="evaluated", reason="caller-supplied-parameters",
                           evidence_ids=evidence_ids, result=result, **common)
