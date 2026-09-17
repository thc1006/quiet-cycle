from fractions import Fraction

import pytest
from pydantic import ValidationError

from quietcycle import (
    CycleContext,
    CyclePipeline,
    NoOnset,
    Onset,
    PipelineRequest,
    Probability,
    Rational,
    Symptom,
)
from quietcycle.dates import add_days, civil, instant, local_day
from quietcycle.errors import InputError
from quietcycle.serialization import canonical_json, loads, parse_model


@pytest.mark.parametrize("bad", ["2025-02-29", "2026-13-01", "2026-1-01", "2026-01-32", "1899-12-31", "2201-01-01", "2026-０１-01"])
def test_invalid_dates(bad):
    with pytest.raises(ValueError):
        civil(bad)


@pytest.mark.parametrize("bad", ["2026-01-01", "2026-01-01T00:00:00", "2026-01-01T00:00:60Z", "2026-01-01T00:00:00-00:00", "2026-01-01T00:00:00+14:01", "2026-01-01T00:00:00+08:99", "2026-01-01T00:00:00.0001Z"])
def test_invalid_instants(bad):
    with pytest.raises(ValueError):
        instant(bad)


def test_offset_normalization_and_midnight():
    assert instant("2026-09-17T08:00:00+08:00") == "2026-09-17T00:00:00.000Z"
    assert local_day("2026-09-16T23:00:00Z", 120) == "2026-09-17"
    assert add_days("2000-02-28", 2) == "2000-03-01"
    assert add_days("1900-02-28", 1) == "1900-03-01"


@pytest.mark.parametrize("field,value", [("revision", True), ("revision", "1"), ("utc_offset_minutes", 8.0), ("exclude_from_history", "false"), ("certainty", "probable")])
def test_no_implicit_coercions(request_data, field, value):
    request_data["dataset"]["events"][0][field] = value
    with pytest.raises(ValidationError):
        PipelineRequest.model_validate(request_data)


def test_unknown_fields_rejected(request_data):
    request_data["dataset"]["events"][0]["secret_health_note"] = "sensitive-content"
    with pytest.raises(InputError) as caught:
        parse_model(PipelineRequest, request_data)
    assert "sensitive-content" not in str(caught.value)


def test_future_event_and_incomplete_day():
    with pytest.raises(ValidationError):
        Onset(subject_id="p", id="o", date="2026-09-18", recorded_at="2026-09-17T12:00:00Z", utc_offset_minutes=0, certainty="confirmed")
    with pytest.raises(ValidationError):
        NoOnset(subject_id="p", id="n", anchor_id="o", through="2026-09-17", recorded_at="2026-09-17T23:59:59Z", utc_offset_minutes=0)


def test_context_and_continuity_required():
    with pytest.raises(ValidationError):
        CycleContext()
    with pytest.raises(ValidationError):
        Onset(subject_id="p", id="o", date="2026-09-17", recorded_at="2026-09-17T12:00:00Z", utc_offset_minutes=0, certainty="confirmed", continuity="confirmed")


def test_symptom_impact_consistency():
    with pytest.raises(ValidationError):
        Symptom(subject_id="p", id="s", date="2026-09-17", recorded_at="2026-09-17T12:00:00Z", utc_offset_minutes=0, symptom="headache", state="absent", impact=2)


def test_fraction_and_probability():
    assert Probability.from_fraction(Fraction(1, 3)).as_fraction() == Fraction(1, 3)
    for numerator, denominator in [("2", "4"), ("0", "2"), ("1", "0")]:
        with pytest.raises(ValidationError):
            Rational(numerator=numerator, denominator=denominator)
    with pytest.raises(ValidationError):
        Probability.from_fraction(Fraction(2))


@pytest.mark.parametrize("text", ['{"a":1,"a":2}', '{"a":NaN}', '{"a":Infinity}', '{"a":1.5}', '{bad}'])
def test_wire_parser_rejects_ambiguous_json(text):
    with pytest.raises(InputError):
        loads(text)


def test_source_decimal_import_explicit():
    assert loads('{"value":36.70}', source_decimals=True)["value"] == "36.70"
    with pytest.raises(InputError):
        canonical_json({"x": 0.1})


def test_frozen_objects_and_revalidation(sample):
    with pytest.raises(ValidationError):
        sample.query.as_of = "2026-01-01"
    hacked_query = sample.query.model_copy(update={"as_of": "not-a-date"})
    with pytest.raises(InputError):
        CyclePipeline().run(sample.dataset, hacked_query)


def test_event_lists_normalize_to_immutable_tuples(request_data):
    request = PipelineRequest.model_validate(request_data)
    assert isinstance(request.dataset.events, tuple)
    assert isinstance(request.model_dump(mode="json")["dataset"]["events"], list)


def test_precision_budget_rejects_without_float_fallback():
    from fractions import Fraction
    from quietcycle import InputError, Probability
    with pytest.raises(InputError, match="fraction_precision_budget"):
        Probability.from_fraction(Fraction(1, 1 << 7000))
