from __future__ import annotations

from fractions import Fraction
import random

import pytest
from pydantic import ValidationError

from quietcycle import CycleDataset, InputError
from quietcycle.research.duration import DurationModel, duration_forecast
from quietcycle.research.pipeline import DurationResearchPipeline, EvidenceRule
from quietcycle.research.evaluation import conformal_radius, mean_absolute_error


def model(duration=(1, 1), exits=(0, 1), age=1):
    return DurationModel.model_validate({"id": "synthetic", "states": [
        {"id": "a", "duration_weights": duration, "exit_weights": exits}],
        "initial": [{"state": 0, "age": age, "weight": 1}]})


def test_duration_simple_and_residual():
    result = duration_forecast(model(), horizon=1)
    assert result.steps[0].mass.as_fraction() == Fraction(1, 2)
    assert result.residual_mass.as_fraction() == Fraction(1, 2)
    assert duration_forecast(model(), horizon=2).residual_mass.as_fraction() == 0
    assert duration_forecast(model(age=2), horizon=1).steps[0].mass.as_fraction() == 1


def test_duration_never_absorbing_and_self_loop():
    assert duration_forecast(model(exits=(1, 0)), horizon=10).residual_mass.as_fraction() == 1
    result = duration_forecast(model(duration=(1,), exits=(1, 1)), horizon=5)
    assert [p.mass.as_fraction() for p in result.steps] == [Fraction(1, 2**i) for i in range(1, 6)]
    assert result.residual_mass.as_fraction() == Fraction(1, 32)


@pytest.mark.parametrize("patch", [
    {"initial": []}, {"states": []},
    {"initial": [{"state": 1, "age": 1, "weight": 1}]},
    {"initial": [{"state": 0, "age": 3, "weight": 1}]},
    {"initial": [{"state": 0, "age": 1, "weight": 0}]},
    {"states": [{"id": "a", "duration_weights": [1, 0], "exit_weights": [0, 1]}]},
    {"states": [{"id": "a", "duration_weights": [1], "exit_weights": [0, 0]}]},
    {"states": [{"id": "a", "duration_weights": [1], "exit_weights": [1]}]},
])
def test_bad_duration_model(patch):
    raw = model().model_dump(mode="json")
    raw.update(patch)
    with pytest.raises(ValidationError):
        DurationModel.model_validate(raw)


@pytest.mark.parametrize("horizon", [0, 181, True, 1.0])
def test_invalid_horizon(horizon):
    with pytest.raises(InputError):
        duration_forecast(model(), horizon=horizon)


@pytest.mark.parametrize("weights", [(0,), (-1,), (True,), (1, 2)])
def test_invalid_or_impossible_evidence(weights):
    with pytest.raises(InputError):
        duration_forecast(model(), state_likelihood_weights=weights)


def countdown_oracle(m, horizon):
    """Independent representation: sample total duration, then count remaining days."""
    mass = {}
    initial_total = sum(x.weight for x in m.initial)
    for start in m.initial:
        durations = m.states[start.state].duration_weights
        total = sum(durations[start.age - 1:])
        for d in range(start.age, len(durations) + 1):
            key = (start.state, d - start.age + 1)
            mass[key] = mass.get(key, Fraction()) + Fraction(start.weight, initial_total) * Fraction(durations[d - 1], total)
    hits = []
    for _ in range(horizon):
        nxt, hit = {}, Fraction()
        for (s, remaining), weight in mass.items():
            if remaining > 1:
                key = s, remaining - 1
                nxt[key] = nxt.get(key, Fraction()) + weight
                continue
            exits = m.states[s].exit_weights
            for target, count in enumerate(exits):
                moving = weight * Fraction(count, sum(exits))
                if target == len(m.states):
                    hit += moving
                else:
                    durations = m.states[target].duration_weights
                    for d, dw in enumerate(durations, 1):
                        key = target, d
                        nxt[key] = nxt.get(key, Fraction()) + moving * Fraction(dw, sum(durations))
        mass = nxt
        hits.append(hit)
    return hits, sum(mass.values(), Fraction())


def test_200_models_against_independent_countdown_oracle():
    rng = random.Random(2060917)
    for _ in range(200):
        states = []
        for i in range(2):
            duration = [rng.randrange(4) for _ in range(rng.randrange(1, 5))]
            duration[-1] = rng.randrange(1, 4)
            exits = [rng.randrange(4) for _ in range(3)]
            if not any(exits):
                exits[-1] = 1
            states.append({"id": f"s{i}", "duration_weights": duration, "exit_weights": exits})
        m = DurationModel.model_validate({"id": "synthetic-oracle", "states": states,
            "initial": [{"state": i, "age": rng.randrange(1, len(s["duration_weights"]) + 1), "weight": rng.randrange(1, 4)} for i, s in enumerate(states)]})
        expected, residual = countdown_oracle(m, 8)
        actual = duration_forecast(m, horizon=8)
        assert [x.mass.as_fraction() for x in actual.steps] == expected
        assert actual.residual_mass.as_fraction() == residual


def two_states():
    return DurationModel.model_validate({"id": "synthetic-two-state", "states": [
        {"id": "short", "duration_weights": [1], "exit_weights": [0, 0, 1]},
        {"id": "long", "duration_weights": [0, 1], "exit_weights": [0, 0, 1]}],
        "initial": [{"state": 0, "age": 1, "weight": 1}, {"state": 1, "age": 1, "weight": 1}]})


def test_measurement_runs_through_research_pipeline(sample):
    rule = EvidenceRule(metric="body_temperature", unit="Cel", max_age_days=1,
        lower={"numerator": "37", "denominator": "1"},
        weights_inside=(3, 1), weights_outside=(1, 3))
    pipeline = DurationResearchPipeline(two_states(), rule=rule, horizon=2)
    assert pipeline.run(sample.dataset, sample.query).reason == "no-eligible-measurement"
    raw = sample.dataset.model_dump(mode="json")
    raw["events"].append({"kind": "measurement", "subject_id": sample.query.subject_id,
        "id": "temperature-1", "utc_offset_minutes": 0, "date": sample.query.as_of, "recorded_at": sample.query.cutoff,
        "measured_at": sample.query.cutoff, "value": "98.6", "metric": "body_temperature",
        "unit": "[degF]", "state": "measured"})
    dataset = CycleDataset.model_validate(raw)
    run = pipeline.run(dataset, sample.query)
    assert run.evidence_ids == ("temperature-1",)
    assert run.result.steps[0].mass.as_fraction() == Fraction(3, 4)
    assert run.result.residual_mass.as_fraction() == 0
    assert run == pipeline.run(dataset, sample.query)
    raw["events"].append(dict(raw["events"][-1], id="second-at-same-time"))
    assert pipeline.run(CycleDataset.model_validate(raw), sample.query).reason == "ambiguous-latest-measurement"


def test_calibration_and_scores():
    assert conformal_radius((1, 2, 3, 4, 5), coverage=Fraction(9, 10)) is None
    assert conformal_radius(tuple(range(10)), coverage=Fraction(9, 10)) == 9
    assert conformal_radius((), coverage=Fraction(1, 2)) is None
    assert mean_absolute_error((1, 2, 3), (2, 3, 2)) == 1
    for data, probability in [((True,), Fraction(1, 2)), ((1,), 0.5), ((1,), Fraction(1))]:
        with pytest.raises(InputError):
            conformal_radius(data, coverage=probability)
