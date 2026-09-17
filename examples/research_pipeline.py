"""Synthetic signal -> exact units -> state evidence -> first-event distribution.

All state parameters are made up for wiring tests. None describe human physiology.
"""
from fractions import Fraction

from quietcycle import CycleContext, CycleDataset, DefaultFeatureBuilder, Measurement, Query, UnitRegistry, UnitRule, canonical_json
from quietcycle.research.duration import DurationModel, DurationState, InitialState
from quietcycle.research.pipeline import DurationResearchPipeline, EvidenceRule


def main() -> None:
    model = DurationModel(id="synthetic-two-state", states=(
        DurationState(id="a", duration_weights=(1,), exit_weights=(0, 0, 1)),
        DurationState(id="b", duration_weights=(0, 1), exit_weights=(0, 0, 1)),
    ), initial=(InitialState(state=0, age=1, weight=1), InitialState(state=1, age=1, weight=1)))
    registry = UnitRegistry({("synthetic_signal", "{score}"): UnitRule("{score}", Fraction(1))})
    rule = EvidenceRule(metric="synthetic_signal", unit="{score}",
        lower={"numerator": "2", "denominator": "1"}, weights_inside=(3, 1),
        weights_outside=(1, 3), max_age_days=1)
    data = CycleDataset(events=(Measurement(subject_id="synthetic", id="signal-1",
        date="2025-07-02", recorded_at="2025-07-02T10:00:00Z", measured_at="2025-07-02T09:00:00Z",
        utc_offset_minutes=0, metric="synthetic_signal", unit="{score}", state="measured", value="2"),))
    query = Query(subject_id="synthetic", as_of="2025-07-02", cutoff="2025-07-02T12:00:00Z",
        utc_offset_minutes=0, context=CycleContext(mode="natural-cycle"))
    pipeline = DurationResearchPipeline(model, rule=rule, horizon=2,
        feature_builder=DefaultFeatureBuilder(registry))
    print(canonical_json(pipeline.run(data, query)))

if __name__ == "__main__":
    main()
