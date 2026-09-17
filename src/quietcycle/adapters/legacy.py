"""Explicit migration from Quiet Cycle Core 0.1.0's JavaScript request contract."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ..errors import InputError
from ..models import CycleDataset, PipelineRequest, Provenance
from ..serialization import parse_model
from .records import from_records

FIELDS = {
    "recordedAt": "recorded_at", "utcOffsetMinutes": "utc_offset_minutes",
    "previousOnsetId": "previous_onset_id", "excludeFromHistory": "exclude_from_history",
    "anchorId": "anchor_id",
}


def from_v1(request: Mapping[str, Any], *, subject_id: str,
            imported_at: str | None = None) -> PipelineRequest:
    """No continuity or availability is invented. Set imported_at for a new live import."""
    allowed = {"schemaVersion", "asOf", "cutoff", "utcOffsetMinutes", "context", "events"}
    if not isinstance(request, Mapping) or set(request) != allowed or type(request.get("schemaVersion")) is not int or request["schemaVersion"] != 1:
        raise InputError("unsupported_legacy_request")
    if not isinstance(request["events"], (list, tuple)) or not isinstance(request["context"], Mapping):
        raise InputError("invalid_legacy_request")
    context = request["context"]
    if set(context) != {"mode", "changedSince", "paused"}:
        raise InputError("invalid_legacy_context")
    records = []
    for old in request["events"]:
        if not isinstance(old, Mapping) or type(old.get("deleted")) is not bool:
            raise InputError("invalid_legacy_event")
        record = {FIELDS.get(key, key): value for key, value in old.items() if key != "deleted"}
        if old["deleted"]:
            record["target_kind"] = old["kind"]
            record["kind"] = "delete"
        record["subject_id"] = subject_id
        record["provenance"] = Provenance(source="quiet-cycle-v1", imported_at=imported_at)
        records.append(record)
    dataset: CycleDataset = from_records(records)
    return parse_model(PipelineRequest, {
        "dataset": dataset,
        "query": {
            "subject_id": subject_id, "as_of": request["asOf"], "cutoff": request["cutoff"],
            "utc_offset_minutes": request["utcOffsetMinutes"],
            "context": {"mode": context["mode"], "changed_since": context["changedSince"], "paused": context["paused"]},
        },
    })
