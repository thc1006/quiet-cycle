"""Regression parity with the supplied 0.1.0 implementation, not a clinical benchmark."""
from __future__ import annotations

from datetime import date, timedelta
import json
from pathlib import Path
import random
import shutil
import subprocess

import pytest

from quietcycle import CyclePipeline
from quietcycle.adapters.legacy import from_v1
from quietcycle.predictors import kernel_weights, allocate_ppm

ROOT = Path(__file__).resolve().parents[1]


def make_legacy(lengths, elapsed, negative):
    dates = [date(2023, 1, 1)]
    for length in lengths:
        dates.append(dates[-1] + timedelta(days=length))
    current = dates[-1] + timedelta(days=elapsed)
    events = [{"kind": "onset", "id": f"onset-{i}", "revision": 1,
        "recordedAt": f"{d}T12:00:00.000Z", "utcOffsetMinutes": 0, "deleted": False,
        "date": str(d), "certainty": "confirmed", "previousOnsetId": None if i == 0 else f"onset-{i - 1}",
        "continuity": "unknown" if i == 0 else "confirmed", "excludeFromHistory": False}
        for i, d in enumerate(dates)]
    if negative and elapsed > 0:
        events.append({"kind": "no-onset", "id": "negative", "revision": 1,
            "recordedAt": f"{current}T12:00:00.000Z", "utcOffsetMinutes": 0, "deleted": False,
            "anchorId": f"onset-{len(dates) - 1}", "through": str(current - timedelta(days=1))})
    return {"schemaVersion": 1, "events": events, "asOf": str(current),
        "cutoff": f"{current}T12:00:00.000Z", "utcOffsetMinutes": 0,
        "context": {"mode": "natural-cycle", "changedSince": None, "paused": False}}


def test_300_predictions_match_original_javascript():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js is required only for the frozen legacy reference test")
    rng = random.Random(20260917)
    inputs = []
    for i in range(300):
        base = rng.randrange(18, 41)
        lengths = [base + rng.randrange(-2, 3) for _ in range(rng.randrange(2, 9))]
        if i % 10 == 0:
            lengths[-1] = 80
        raw = make_legacy(lengths, rng.randrange(0, 55), i % 2 == 0)
        if i % 29 == 0:
            raw["context"]["paused"] = True
        inputs.append(raw)
    output = subprocess.run([node, str(ROOT / "tests/reference_js/runner.mjs")],
        input="\n".join(json.dumps(r) for r in inputs) + "\n", text=True, encoding="utf-8",
        capture_output=True, check=True, timeout=30)
    reference = [json.loads(line) for line in output.stdout.splitlines()]
    assert len(reference) == len(inputs)
    for raw, expected in zip(inputs, reference):
        migrated = from_v1(raw, subject_id="synthetic")
        actual = CyclePipeline().run(migrated.dataset, migrated.query).forecast
        assert "error" not in expected, expected
        assert actual.status == expected["status"]
        assert actual.reason == expected["reason"]
        assert actual.point_date == expected["pointDate"]
        if actual.status == "estimate":
            for a, e in zip(actual.distribution, expected["distribution"]):
                assert (a.date, a.cycle_length, a.ppm) == (e["date"], e["length"], e["ppm"])
                assert a.mass.model_dump() == e["mass"]
            assert len(actual.distribution) == len(expected["distribution"])
            assert actual.within_three_days.model_dump() == expected["within3Days"]["modelMass"]
            assert [(p.start, p.end) for p in actual.intervals] == [(p["from"], p["to"]) for p in expected["intervals"]]


def test_1400_kernel_and_allocation_cases():
    rng = random.Random(99)
    for _ in range(1400):
        bandwidth = rng.randrange(15)
        lengths = tuple(rng.randrange(bandwidth + 1, 100) for _ in range(rng.randrange(1, 10)))
        weights = kernel_weights(lengths, bandwidth)
        assert sum(w for _, w in weights) == len(lengths) * (bandwidth + 1) ** 2
        allocated = allocate_ppm(tuple(w for _, w in weights))
        assert sum(allocated) == 1000000
        total = sum(w for _, w in weights)
        for (_, weight), ppm in zip(weights, allocated):
            assert abs(ppm * total - weight * 1000000) < total
