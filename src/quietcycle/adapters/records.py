"""Adapters for ordinary mappings, JSON, and JSON Lines."""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from ..errors import InputError
from ..models import CycleDataset, EVENT_ADAPTER, Event
from ..serialization import canonical_json, loads, parse_model, read_text


def from_records(records: Iterable[Mapping[str, Any]]) -> CycleDataset:
    """Use with SQL mapping rows, dicts, or dataframe.to_dict(orient='records')."""
    events: list[Event] = []
    for index, record in enumerate(records, 1):
        if index > 50000:
            raise InputError("too_many_records", row=index)
        if not isinstance(record, Mapping):
            raise InputError("record_must_be_mapping", row=index)
        try:
            events.append(EVENT_ADAPTER.validate_python(dict(record)))
        except ValidationError:
            raise InputError("schema_validation_failed", row=index) from None
    return CycleDataset(events=tuple(events))


def from_json(text: str) -> CycleDataset:
    return parse_model(CycleDataset, loads(text))


def load_json(path: str | Path) -> CycleDataset:
    return from_json(read_text(path))


def from_jsonl(text: str) -> CycleDataset:
    records = []
    # Apply total size limit, not just a per-line limit.
    if len(text.encode("utf-8")) > 16 * 1024 * 1024:
        raise InputError("input_too_large")
    for line_number, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        try:
            record = loads(line)
            if not isinstance(record, dict):
                raise InputError("record_must_be_mapping")
            records.extend(from_records([record]).events)
        except InputError as exc:
            raise InputError(exc.code, row=line_number) from None
        if len(records) > 50000:
            raise InputError("too_many_records", row=line_number)
    return CycleDataset(events=tuple(records))


def load_jsonl(path: str | Path) -> CycleDataset:
    return from_jsonl(read_text(path))


def to_jsonl(dataset: CycleDataset) -> str:
    return "\n".join(canonical_json(event) for event in dataset.events) + ("\n" if dataset.events else "")
