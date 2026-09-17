"""Explicit CSV columns. Empty is null or unspecified, never a negative symptom report."""
from __future__ import annotations

import csv
import io
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from ..errors import InputError
from ..models import CycleDataset
from ..serialization import MAX_BYTES, read_text
from .records import from_records

COLUMNS = (
    "subject_id", "id", "revision", "kind", "recorded_at", "utc_offset_minutes", "date",
    "certainty", "previous_onset_id", "continuity", "exclude_from_history",
    "anchor_id", "through", "symptom", "state", "impact", "metric", "value", "unit",
    "measured_at", "method", "body_site", "missing_reason", "target_kind",
    "source", "source_record_id", "imported_at",
)
INTEGER_FIELDS = {"revision", "utc_offset_minutes", "impact"}
BOOL_FIELDS = {"exclude_from_history"}
NULLABLE = {"previous_onset_id", "impact", "value", "method", "body_site", "missing_reason"}
PROVENANCE = {"source", "source_record_id", "imported_at"}


class CSVAdapter:
    """column_map maps source headings to contract names; defaults are already typed."""

    def __init__(self, *, column_map: Mapping[str, str] | None = None,
                 defaults: Mapping[str, Any] | None = None) -> None:
        if column_map is not None and not isinstance(column_map, Mapping):
            raise InputError("invalid_csv_mapping")
        if defaults is not None and not isinstance(defaults, Mapping):
            raise InputError("invalid_csv_defaults")
        self.column_map = dict(column_map or {})
        self.defaults = dict(defaults or {})
        if any(not isinstance(k, str) or not isinstance(v, str) or v not in COLUMNS for k, v in self.column_map.items()) or any(k not in COLUMNS for k in self.defaults):
            raise InputError("invalid_csv_mapping")

    def loads(self, text: str) -> CycleDataset:
        if len(text.encode("utf-8")) > MAX_BYTES:
            raise InputError("input_too_large")
        reader = csv.reader(io.StringIO(text.lstrip("\ufeff"), newline=""), strict=True)
        try:
            original_headers = next(reader)
        except StopIteration:
            raise InputError("missing_csv_header") from None
        except csv.Error:
            raise InputError("invalid_csv") from None
        headers = [self.column_map.get(name, name) for name in original_headers]
        if len(headers) != len(set(headers)):
            raise InputError("duplicate_csv_column")
        if not headers or any(name not in COLUMNS for name in headers):
            raise InputError("unknown_csv_column")
        records = []
        try:
            for row_number, values in enumerate(reader, 2):
                if not values:
                    continue
                if len(values) != len(headers):
                    raise InputError("csv_column_count", row=row_number)
                record = dict(self.defaults)
                for name, text_value in zip(headers, values):
                    if text_value == "":
                        if name in NULLABLE and name not in record:
                            # Only retain applicable null fields after kind is known.
                            record[name] = None
                        continue
                    if text_value != text_value.strip():
                        raise InputError("csv_surrounding_whitespace", row=row_number)
                    if name in INTEGER_FIELDS:
                        if re.fullmatch(r"-?[0-9]{1,9}", text_value) is None:
                            raise InputError("csv_integer_required", row=row_number)
                        record[name] = int(text_value)
                    elif name in BOOL_FIELDS:
                        if text_value not in ("true", "false"):
                            raise InputError("csv_boolean_required", row=row_number)
                        record[name] = text_value == "true"
                    else:
                        record[name] = text_value
                kind = record.get("kind")
                applicable = {
                    "onset": {"previous_onset_id"},
                    "symptom": {"impact"},
                    "measurement": {"value", "method", "body_site", "missing_reason"},
                }.get(kind, set())
                record = {k: v for k, v in record.items() if v is not None or k in applicable}
                provenance = {k: record.pop(k) for k in tuple(record) if k in PROVENANCE}
                if provenance:
                    record["provenance"] = provenance
                try:
                    one = from_records([record])
                except InputError as exc:
                    raise InputError(exc.code, row=row_number) from None
                records.extend(one.events)
                if len(records) > 50000:
                    raise InputError("too_many_records", row=row_number)
        except csv.Error:
            raise InputError("invalid_csv", row=reader.line_num) from None
        return CycleDataset(events=tuple(records))

    def load(self, path: str | Path) -> CycleDataset:
        return self.loads(read_text(path))


def load_csv(path: str | Path, *, column_map: Mapping[str, str] | None = None,
             defaults: Mapping[str, Any] | None = None) -> CycleDataset:
    return CSVAdapter(column_map=column_map, defaults=defaults).load(path)


def to_csv(dataset: CycleDataset) -> str:
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=COLUMNS, lineterminator="\n")
    writer.writeheader()
    for event in dataset.events:
        record = event.model_dump(mode="json")
        record.update(record.pop("provenance"))
        for key, value in tuple(record.items()):
            if type(value) is bool:
                record[key] = "true" if value else "false"
            elif value is None:
                record[key] = ""
            elif isinstance(value, str) and value.startswith(("=", "+", "@", "\t", "\r", "\n")):
                raise InputError("unsafe_spreadsheet_cell")
        writer.writerow(record)
    return output.getvalue()
