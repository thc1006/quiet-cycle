"""Synthetic engineering fixtures, not plausible population data or clinical evidence.

The signal fixture deliberately makes temperature/fatigue informative. The drift
fixture reverses that relation only in test. No fitted values here came from people.
"""
from __future__ import annotations

from hashlib import sha256

from quietcycle import CycleContext, CycleDataset, Measurement, NoOnset, Onset, Query, Symptom
from quietcycle.dates import add_days
from quietcycle.learning import FitRequest, LandmarkSpec, build_cases


def decimal_tenths(n: int) -> str:
    sign = "-" if n < 0 else ""
    return f"{sign}{abs(n) // 10}.{abs(n) % 10}"


def subject_fixture(subject: str, anchor: str, index: int, *, regime: str = "signal"):
    base = 29 + index % 5
    temperature = index % 3 - 1
    fatigue = (index // 3) % 2
    heart = (index // 6) % 3 - 1
    noise = int(sha256(("noise:" + subject).encode()).hexdigest()[:8], 16) % 5 - 2
    effect = 3 * temperature + 2 * fatigue + heart
    if regime == "noise":
        effect = int(sha256(("unrelated:" + subject).encode()).hexdigest()[:8], 16) % 11 - 5
    elif regime == "drift":
        effect = -effect
    outcome_length = base + effect + noise
    events = []
    previous = None
    for j in range(5):
        d = add_days(anchor, -(4 - j) * base)
        event_id = f"o{j}"
        events.append(Onset(subject_id=subject, id=event_id, date=d, recorded_at=d + "T08:00:00Z", utc_offset_minutes=0,
                            certainty="confirmed", previous_onset_id=previous,
                            continuity="confirmed" if previous else "unknown"))
        previous = event_id
    as_of = add_days(anchor, 20)
    events.append(NoOnset(subject_id=subject, id="no-onset", anchor_id="o4", through=add_days(as_of, -1),
                           recorded_at=as_of + "T08:00:00Z", utc_offset_minutes=0))
    for elapsed in range(10, 20):
        d = add_days(anchor, elapsed)
        later = elapsed >= 17
        values = {
            "wrist_temperature": (decimal_tenths(355 + index % 4 + (2 * temperature if later else 0)), "Cel"),
            "resting_heart_rate": (str(60 + index % 5 + (3 * heart if later else 0)), "/min"),
            "hrv_rmssd": (str(40 + index % 7 - (2 * heart if later else 0)), "ms"),
            "sleep_duration": (str(8 - (fatigue if later else 0)), "h"),
        }
        for metric, (value, unit) in values.items():
            events.append(Measurement(subject_id=subject, id=f"m-{elapsed}-{metric}", date=d, recorded_at=d+"T08:00:00Z",
                measured_at=d+"T07:00:00Z", utc_offset_minutes=0, metric=metric, value=value, unit=unit))
        if later:
            for symptom, state in (("fatigue", bool(fatigue)), ("headache", temperature == 1), ("abdominal_pain", False), ("gastrointestinal", False)):
                events.append(Symptom(subject_id=subject, id=f"s-{elapsed}-{symptom}", date=d, recorded_at=d+"T08:00:00Z",
                    utc_offset_minutes=0, symptom=symptom, state="present" if state else "absent"))
    end = add_days(anchor, outcome_length)
    events.append(Onset(subject_id=subject, id="o5", date=end, recorded_at=end+"T08:00:00Z", utc_offset_minutes=0,
                         certainty="confirmed", previous_onset_id="o4", continuity="confirmed"))
    dataset = CycleDataset(events=tuple(events))
    query = Query(subject_id=subject, as_of=as_of, cutoff=as_of+"T12:00:00Z", utc_offset_minutes=0,
                  context=CycleContext(mode="natural-cycle"))
    return dataset, query


def cohort(*, train_n=36, tune_n=18, calibration_n=24, test_n=24, regime="signal"):
    spec = LandmarkSpec()
    groups = []
    test_inputs = []
    rejected = []
    for phase, count, anchor, labels_cutoff in (
        ("train", train_n, "2023-06-01", "2023-09-01T00:00:00Z"),
        ("tune", tune_n, "2024-01-01", "2024-04-01T00:00:00Z"),
        ("calibration", calibration_n, "2024-07-01", "2024-10-01T00:00:00Z"),
        ("test", test_n, "2025-01-01", "2025-04-01T00:00:00Z"),
    ):
        cases = []
        for i in range(count):
            idx = i + {"train": 0, "tune": 41, "calibration": 83, "test": 127}[phase]
            use_regime = "signal" if regime == "drift" and phase != "test" else regime
            dataset, query = subject_fixture(f"{phase}-{i}", anchor, idx, regime=use_regime)
            built = build_cases(dataset, (query,), spec=spec, labels_cutoff=labels_cutoff,
                                data_kind="synthetic", cohort="synthetic-engineering")
            cases.extend(built.cases)
            rejected.extend(built.rejected)
            if phase == "test":
                test_inputs.append((dataset, query))
        groups.append(tuple(cases))
    request = FitRequest(spec=spec, train=groups[0], tune=groups[1], calibration=groups[2])
    return request, groups[3], tuple(test_inputs), tuple(rejected)
