"""Exact duration-expanded first-passage model with caller-supplied parameters.

A state duration of 1 exits on the next step. Exit index len(states) is absorbing.
Residual probability includes both events after the horizon and events that never occur.
"""
from __future__ import annotations

from fractions import Fraction
from typing import Annotated, Literal, Self

from pydantic import BeforeValidator, Field, StrictInt, model_validator

from ..errors import InputError
from ..models import Identifier, Model, Probability, _tuple

Weight = Annotated[StrictInt, Field(ge=0, le=1000000)]
Weights = Annotated[tuple[Weight, ...], BeforeValidator(_tuple), Field(min_length=1, max_length=120)]


class DurationState(Model):
    id: Identifier
    duration_weights: Weights
    exit_weights: Weights

    @model_validator(mode="after")
    def support(self) -> Self:
        if self.duration_weights[-1] <= 0 or sum(self.exit_weights) == 0:
            raise ValueError("empty_duration_or_exit_support")
        return self


class InitialState(Model):
    state: Annotated[StrictInt, Field(ge=0)]
    age: Annotated[StrictInt, Field(ge=1)]
    weight: Weight


class DurationModel(Model):
    id: Identifier
    states: Annotated[tuple[DurationState, ...], BeforeValidator(_tuple), Field(min_length=1, max_length=8)]
    initial: Annotated[tuple[InitialState, ...], BeforeValidator(_tuple), Field(min_length=1, max_length=512)]

    @model_validator(mode="after")
    def dimensions(self) -> Self:
        n = len(self.states)
        if len({s.id for s in self.states}) != n:
            raise ValueError("duplicate_state")
        if sum(len(s.duration_weights) for s in self.states) > 512:
            raise ValueError("too_many_expanded_states")
        if any(len(s.exit_weights) != n + 1 for s in self.states):
            raise ValueError("exit_dimension_mismatch")
        for point in self.initial:
            if point.state >= n or point.age > len(self.states[point.state].duration_weights):
                raise ValueError("initial_state_outside_support")
        if sum(p.weight for p in self.initial) == 0:
            raise ValueError("empty_initial_support")
        return self


class PassagePoint(Model):
    after_days: Annotated[StrictInt, Field(ge=1)]
    mass: Probability


class DurationResult(Model):
    model_id: Identifier
    clinical_validated: Literal[False] = False
    parameter_source: Literal["caller-supplied"] = "caller-supplied"
    steps: Annotated[tuple[PassagePoint, ...], BeforeValidator(_tuple)]
    residual_mass: Probability
    residual_meaning: Literal["after-horizon-or-never-no-renormalization"] = "after-horizon-or-never-no-renormalization"

    @model_validator(mode="after")
    def conservation(self) -> Self:
        total = sum((p.mass.as_fraction() for p in self.steps), Fraction()) + self.residual_mass.as_fraction()
        if total != 1:
            raise ValueError("mass_not_conserved")
        if [p.after_days for p in self.steps] != list(range(1, len(self.steps) + 1)):
            raise ValueError("nonconsecutive_steps")
        return self


def duration_forecast(model: DurationModel, *, horizon: int = 60,
                      state_likelihood_weights: tuple[int, ...] | None = None) -> DurationResult:
    model = DurationModel.model_validate(model)
    if type(horizon) is not int or not 1 <= horizon <= 180:
        raise InputError("invalid_horizon")
    n = len(model.states)
    likelihood = (1,) * n if state_likelihood_weights is None else state_likelihood_weights
    if len(likelihood) != n or any(type(w) is not int or not 0 <= w <= 1000000 for w in likelihood):
        raise InputError("invalid_likelihood_weights")
    mass: dict[tuple[int, int], Fraction] = {}
    for point in model.initial:
        key = (point.state, point.age)
        mass[key] = mass.get(key, Fraction()) + point.weight * likelihood[point.state]
    total = sum(mass.values(), Fraction())
    if total == 0:
        raise InputError("impossible_evidence")
    mass = {key: value / total for key, value in mass.items() if value}
    transitions: dict[tuple[int, int], tuple[tuple[tuple[int, int] | None, Fraction], ...]] = {}
    for index, state in enumerate(model.states):
        exit_total = sum(state.exit_weights)
        for age in range(1, len(state.duration_weights) + 1):
            survival = sum(state.duration_weights[age - 1:])
            exit_probability = Fraction(state.duration_weights[age - 1], survival)
            edges: list[tuple[tuple[int, int] | None, Fraction]] = []
            if age < len(state.duration_weights):
                edges.append(((index, age + 1), 1 - exit_probability))
            for target, weight in enumerate(state.exit_weights):
                if weight:
                    edges.append((None if target == n else (target, 1), exit_probability * Fraction(weight, exit_total)))
            transitions[index, age] = tuple(edges)
    steps = []
    for day in range(1, horizon + 1):
        updated: dict[tuple[int, int], Fraction] = {}
        hit = Fraction()
        for key, value in mass.items():
            for target, chance in transitions[key]:
                moved = value * chance
                if target is None:
                    hit += moved
                elif moved:
                    updated[target] = updated.get(target, Fraction()) + moved
        if any(max(abs(v.numerator).bit_length(), v.denominator.bit_length()) > 6800 for v in updated.values()):
            raise InputError("fraction_precision_budget")
        steps.append(PassagePoint(after_days=day, mass=Probability.from_fraction(hit)))
        mass = updated
    return DurationResult(model_id=model.id, steps=tuple(steps),
                          residual_mass=Probability.from_fraction(sum(mass.values(), Fraction())))
