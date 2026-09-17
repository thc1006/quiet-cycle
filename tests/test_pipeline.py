
import pytest
from pydantic import ValidationError

from quietcycle import (
    CycleDataset,
    CyclePipeline,
    EmpiricalPredictor,
    Forecast,
    NoOnset,
    Onset,
    Policy,
    Query,
    Symptom,
    Tombstone,
    canonical_json,
)
from quietcycle.dates import add_days
from quietcycle.errors import InputError
from quietcycle.predictors import allocate_ppm, kernel_weights


def change_sample(sample, *, events=None, query=None):
    dataset = CycleDataset(events=sample.dataset.events if events is None else events)
    return CyclePipeline().run(dataset, sample.query if query is None else query)


def query_on(sample, day):
    data = sample.query.model_dump()
    data.update(as_of=day, cutoff=day + "T12:00:00Z")
    return Query.model_validate(data)


def test_forecast_normalized(sample):
    result = change_sample(sample)
    assert result.forecast.status == "estimate"
    assert result.forecast.point_date == "2025-07-21"
    assert sum(p.mass.as_fraction() for p in result.forecast.distribution) == 1
    assert sum(p.ppm for p in result.forecast.distribution) == 1000000
    assert result.used_features == ("onset", "no-onset", "context")
    for interval in result.forecast.intervals:
        mass = sum(p.mass.as_fraction() for p in result.forecast.distribution if interval.start <= p.date <= interval.end)
        assert mass == interval.included_mass.as_fraction()
        assert mass * 1000000 >= interval.requested_mass_ppm


def test_permutation_and_idempotence(sample):
    baseline = canonical_json(change_sample(sample))
    assert baseline == canonical_json(change_sample(sample, events=tuple(reversed(sample.dataset.events))))
    assert baseline == canonical_json(change_sample(sample, events=sample.dataset.events * 2))
    assert sample.dataset.merge(sample.dataset) == sample.dataset


def test_missing_is_not_no_onset(sample):
    result = change_sample(sample, query=query_on(sample, "2025-07-21"))
    assert result.forecast.reason == "onset-status-unconfirmed"


def test_explicit_completed_day_conditions_distribution(sample):
    report = NoOnset(subject_id="demo", id="no", anchor_id="onset-6", through="2025-07-20",
                     recorded_at="2025-07-21T08:00:00Z", utc_offset_minutes=0)
    result = change_sample(sample, events=sample.dataset.events + (report,), query=query_on(sample, "2025-07-21"))
    assert result.forecast.status == "estimate"
    assert result.forecast.distribution[0].date == "2025-07-21"
    assert result.forecast.audit.unresolved_past_mass.as_fraction() == 0


def test_exhausted_and_weak_support(sample):
    for day, reason in [("2025-07-24", "weak-remaining-support"), ("2025-07-25", "support-exhausted")]:
        report = NoOnset(subject_id="demo", id="no", anchor_id="onset-6", through=add_days(day, -1), recorded_at=day + "T08:00:00Z", utc_offset_minutes=0)
        assert change_sample(sample, events=sample.dataset.events + (report,), query=query_on(sample, day)).forecast.reason == reason


def test_late_revision_is_invisible_in_replay(sample):
    original = sample.dataset.events[-1]
    altered = original.model_dump()
    altered.update(revision=2, recorded_at="2025-07-03T00:00:00Z", date="2025-06-21")
    revised = Onset.model_validate(altered)
    assert canonical_json(change_sample(sample)) == canonical_json(change_sample(sample, events=sample.dataset.events + (revised,)))
    newer = change_sample(sample, events=sample.dataset.events + (revised,), query=query_on(sample, "2025-07-03"))
    assert newer.forecast.audit.anchor_date == "2025-06-21"


def test_imported_at_prevents_backdating(sample):
    events = tuple(Onset.model_validate({**e.model_dump(), "provenance": {"source": "import", "imported_at": "2025-07-03T00:00:00Z"}}) for e in sample.dataset.events)
    result = change_sample(sample, events=events)
    assert result.observation_count == 0
    assert result.forecast.reason == "no-confirmed-onset"


def test_subject_isolation(sample):
    other = tuple(Onset.model_validate({**e.model_dump(), "subject_id": "other"}) for e in sample.dataset.events)
    assert canonical_json(change_sample(sample)) == canonical_json(change_sample(sample, events=sample.dataset.events + other))


def test_conflicting_revision_rejected(sample):
    event = Onset.model_validate({**sample.dataset.events[0].model_dump(), "certainty": "uncertain"})
    with pytest.raises(InputError, match="conflicting_revision"):
        change_sample(sample, events=sample.dataset.events + (event,))
    with pytest.raises(InputError):
        sample.dataset.merge(CycleDataset(events=(event,)))


def test_revision_time_order_and_kind(sample):
    old = sample.dataset.events[-1]
    wrong_time = Onset.model_validate({**old.model_dump(), "revision": 2, "recorded_at": "2025-06-21T00:00:00Z", "date": "2025-06-20"})
    with pytest.raises(InputError, match="revision_time_order"):
        change_sample(sample, events=sample.dataset.events + (wrong_time,))
    wrong_kind = Symptom(subject_id="demo", id=old.id, revision=2, date="2025-06-23", recorded_at="2025-06-23T00:00:00Z", utc_offset_minutes=0, symptom="fatigue", state="present")
    with pytest.raises(InputError, match="revision_kind_change"):
        change_sample(sample, events=sample.dataset.events + (wrong_kind,))


def test_tombstone_does_not_bridge_gap(sample):
    delete = Tombstone(subject_id="demo", id="onset-4", target_kind="onset", revision=2, recorded_at="2025-07-01T00:00:00Z", utc_offset_minutes=0)
    assert change_sample(sample, events=sample.dataset.events + (delete,)).forecast.reason == "unconfirmed-continuity"


@pytest.mark.parametrize("mode,paused,reason", [("other", False, "outside-declared-scope"), ("unknown", False, "outside-declared-scope"), ("natural-cycle", True, "paused")])
def test_outside_scope(sample, mode, paused, reason):
    query = Query.model_validate({**sample.query.model_dump(), "context": {"mode": mode, "paused": paused}})
    assert change_sample(sample, query=query).forecast.reason == reason


def test_context_reset_requires_new_history(sample):
    query = Query.model_validate({**sample.query.model_dump(), "context": {"mode": "natural-cycle", "changed_since": "2025-06-01"}})
    assert change_sample(sample, query=query).forecast.reason == "insufficient-history"


def test_duplicate_onset_days_and_uncertainty(sample):
    extra = Onset.model_validate({**sample.dataset.events[-1].model_dump(), "id": "another-onset"})
    assert change_sample(sample, events=sample.dataset.events + (extra,)).forecast.reason == "conflicting-onsets"
    uncertain = Onset.model_validate({**sample.dataset.events[-1].model_dump(), "certainty": "uncertain"})
    assert change_sample(sample, events=sample.dataset.events[:-1] + (uncertain,)).forecast.reason == "uncertain-current-onset"


def test_orphan_and_conflicting_no_onset(sample):
    report = NoOnset(subject_id="demo", id="n", anchor_id="unknown", through="2025-07-01", recorded_at="2025-07-02T00:00:00Z", utc_offset_minutes=0)
    assert change_sample(sample, events=sample.dataset.events + (report,)).forecast.reason == "orphan-no-onset-report"
    report = NoOnset.model_validate({**report.model_dump(), "anchor_id": "onset-0"})
    assert change_sample(sample, events=sample.dataset.events + (report,)).forecast.reason == "conflicting-no-onset-report"


def test_symptom_states_preserved_not_converted_to_onset(sample):
    events = []
    for i, state in enumerate(("present", "absent", "uncertain", "skipped")):
        events.append(Symptom(subject_id="demo", id=f"s{i}", date=f"2025-06-{24+i}", recorded_at="2025-07-01T00:00:00Z", utc_offset_minutes=0, symptom="headache", state=state))
    result = change_sample(sample, events=sample.dataset.events + tuple(events))
    assert result.forecast == change_sample(sample).forecast
    count = result.symptoms[0]
    assert (count.present, count.absent, count.uncertain, count.skipped, count.recalled_reports) == (1, 1, 1, 1, 4)


def test_policy_version_and_strictness():
    assert EmpiricalPredictor().model_version != EmpiricalPredictor(Policy(bandwidth=3)).model_version
    with pytest.raises(InputError):
        Policy(bandwidth=True)
    assert allocate_ppm((1, 1, 1)) == (333334, 333333, 333333)
    assert sum(w for _, w in kernel_weights((28, 29))) == 18


def test_batch_order(sample):
    results = CyclePipeline().run_many(sample.dataset, [sample.query, query_on(sample, "2025-07-21")])
    assert [r.as_of for r in results] == ["2025-07-02", "2025-07-21"]


def test_forecast_rejects_bad_probability(sample):
    valid = change_sample(sample).forecast.model_dump()
    valid["distribution"][0]["mass"] = {"numerator": "1", "denominator": "1"}
    with pytest.raises(ValidationError):
        Forecast.model_validate(valid)


def test_parallel_runs_do_not_mutate_shared_pipeline(sample):
    from concurrent.futures import ThreadPoolExecutor
    pipeline = CyclePipeline()
    expected = pipeline.run(sample.dataset, sample.query)
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: pipeline.run(sample.dataset, sample.query), range(24)))
    assert results == [expected] * 24
