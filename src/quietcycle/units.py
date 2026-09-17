"""A small, explicit UCUM subset. No universal unit parser or implicit site conversion."""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from hashlib import sha256
from types import MappingProxyType
from typing import Mapping

from .errors import InputError
from .models import Measurement, NormalizedMeasurement, Rational
from .serialization import canonical_json


@dataclass(frozen=True)
class UnitRule:
    canonical_unit: str
    scale: Fraction = Fraction(1)
    offset: Fraction = Fraction(0)


TEMPERATURE = {
    "Cel": UnitRule("Cel"),
    "[degF]": UnitRule("Cel", Fraction(5, 9), Fraction(-160, 9)),
    "K": UnitRule("Cel", Fraction(1), Fraction(-27315, 100)),
}
_defaults: dict[tuple[str, str], UnitRule] = {}
for _metric in ("body_temperature", "skin_temperature", "wrist_temperature"):
    for _unit, _rule in TEMPERATURE.items():
        _defaults[_metric, _unit] = _rule
for _metric in ("heart_rate", "resting_heart_rate"):
    _defaults[_metric, "/min"] = UnitRule("/min")
    _defaults[_metric, "1/s"] = UnitRule("/min", Fraction(60))
for _metric in ("hrv_rmssd", "hrv_sdnn"):
    _defaults[_metric, "ms"] = UnitRule("ms")
    _defaults[_metric, "s"] = UnitRule("ms", Fraction(1000))
for _unit, _scale in (("s", 1), ("min", 60), ("h", 3600)):
    _defaults["sleep_duration", _unit] = UnitRule("s", Fraction(_scale))
_defaults["steps", "{count}"] = UnitRule("{count}")

DEFAULT_RULES = MappingProxyType(_defaults)
del _defaults


class UnitRegistry:
    """An instance owns its rules; extending one pipeline does not mutate another."""

    def __init__(self, extra_rules: Mapping[tuple[str, str], UnitRule] | None = None) -> None:
        rules = dict(DEFAULT_RULES)
        if extra_rules:
            for key, rule in extra_rules.items():
                if (not isinstance(key, tuple) or len(key) != 2 or
                    any(not isinstance(part, str) for part in key) or not isinstance(rule, UnitRule)):
                    raise InputError("invalid_unit_rule")
                if key in rules:
                    raise InputError("unit_rule_override_forbidden")
                if not isinstance(rule.scale, Fraction) or not isinstance(rule.offset, Fraction):
                    raise InputError("unit_rule_requires_fractions")
                if rule.scale <= 0:
                    raise InputError("nonpositive_unit_scale")
                rules[key] = rule
        config = [(key, rule.canonical_unit, str(rule.scale), str(rule.offset))
                  for key, rule in sorted(rules.items())]
        self.signature = sha256(canonical_json(config).encode()).hexdigest()
        self._rules = MappingProxyType(rules)

    def normalize(self, event: Measurement) -> NormalizedMeasurement:
        rule = self._rules.get((event.metric, event.unit))
        if rule is None:
            raise InputError("unsupported_metric_or_unit")
        value = None if event.value is None else Fraction(event.value) * rule.scale + rule.offset
        # These are representation constraints, not clinical normal ranges.
        if value is not None:
            if event.metric in ("body_temperature", "skin_temperature", "wrist_temperature"):
                if value < Fraction(-27315, 100):
                    raise InputError("temperature_below_absolute_zero")
            elif value < 0 and event.metric in ("heart_rate", "resting_heart_rate", "hrv_rmssd", "hrv_sdnn", "sleep_duration", "steps"):
                raise InputError("negative_unsigned_measurement")
            if event.metric == "steps" and value.denominator != 1:
                raise InputError("fractional_step_count")
        return NormalizedMeasurement(
            event_id=event.id, date=event.date, measured_at=event.measured_at,
            available_at=event.available_at, metric=event.metric,
            value=None if value is None else Rational.from_fraction(value),
            unit=rule.canonical_unit, state=event.state, source=event.provenance.source,
            method=event.method, body_site=event.body_site,
        )
