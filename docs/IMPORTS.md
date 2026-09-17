# Import guide

## Canonical JSON and JSON Lines

Use `load_json(path)` for a dataset, `from_json(text)` for text, or
`PipelineRequest.model_validate(...)` for a full request. JSON Lines stores one
event per nonblank line. Duplicate JSON keys are rejected rather than taking the
last value. `to_jsonl()` and `to_csv()` provide round-trip exports.

## CSV

The full header list is `quietcycle.adapters.csv.COLUMNS`; `examples/events.csv`
is a working template. Unknown headers, duplicate headings, malformed rows, and
surrounding cell whitespace are errors. A column map goes from source heading to
canonical name. Defaults are typed values, not strings to guess later.

```python
from quietcycle.adapters import CSVAdapter
adapter = CSVAdapter(column_map={"participant": "subject_id", "event": "id"},
                     defaults={"utc_offset_minutes": 0})
data = adapter.load("export.csv")
```

Boolean cells are exactly `true` or `false`. Empty optional fields are null or
unspecified, never a negative symptom. Missing measurements require an explicit
state/reason. Decimal quantity cells remain strings. This adapter does not guess
whether `3` means a date, score, or temperature.

## Dataframes and database rows

`from_records(rows)` accepts mappings in the canonical event shape. It does not
open a database or depend on pandas/NumPy. For pandas, normalize missing values and
dtypes before export: `frame.astype(object).where(frame.notna(), None).to_dict("records")`.
Ensure structural integers remain real Python integers and decimal quantities are
strings. A float `1.0` will not be accepted as a revision just because it looks integral.
A dataframe whose columns represent daily averages is not automatically an event ledger.

For SQLAlchemy, materialize `row._mapping`; for `sqlite3.Row`, use `dict(row)`.
Adapters should propagate source/import times and stable source IDs. Treat a changed
source record as an explicit revision, not an unrelated new observation.

## FHIR R4 subset

```python
from quietcycle.adapters import FHIRObservationAdapter
adapter = FHIRObservationAdapter(
    subject_map={"Patient/example": "demo"},
    imported_at="2025-07-02T12:00:00Z", utc_offset_minutes=0,
)
data = adapter.load("examples/fhir-observation.json")
```

Supported: `Observation` with final/amended/corrected status, `effectiveDateTime`,
optional issued time, a single `valueQuantity` in UCUM, or an explicit
`dataAbsentReason`. Complete collection/searchset Bundles are accepted. A next-page
link is an error, not a silently truncated successful import.

Built-in LOINC mappings: 8867-4 -> heart_rate; 8310-5 -> body_temperature.
Other scalar quantities require an explicit `(system, code)` mapping and a matching
unit rule. A caller-provided code map replaces, rather than silently extends, the
default mapping. Unknown patients and ambiguous codes fail.

FHIR JSON numeric decimals are read as decimal spelling before any binary float
conversion. Already-parsed Python floats are rejected: their original precision
cannot be recovered. Use `loads(text)`/`load(path)` for normal FHIR exports.

Not supported: components, effectivePeriod/Timing, valueString/valueCodeableConcept,
quantity comparisons, modifierExtension, other resource types, arbitrary profiles,
FHIR validation/terminology services, pagination fetching, or FHIR network access.
This is not a general FHIR importer or a clinically certified converter.
Version IDs are opaque; supply `revision_map` explicitly when merging revised exports.
Use a distinct `source_id` for each FHIR server. It participates in stable event
identity; the adapter does not fetch or discover server identity. If bodySite or
method is present, supply `body_site_map` / `method_map` explicitly. Unmapped values
are errors, not silently dropped metadata. Only mapped site/method identifiers are
retained; keep original source exports in the authorized upstream system if needed.

FHIR observations never become onset events by inference. Build confirmed onset
reports separately from a trustworthy upstream record.

## Units and devices

| Metric | Input units | Normalized output |
| --- | --- | --- |
| body_temperature / skin_temperature / wrist_temperature | Cel, [degF], K | Cel; metrics remain distinct |
| heart_rate / resting_heart_rate | /min, 1/s | /min |
| hrv_rmssd / hrv_sdnn | ms, s | ms; metrics remain distinct |
| sleep_duration | s, min, h | s |
| steps | {count} | integral {count} |

This is a documented UCUM subset, not a full UCUM parser. An unsupported metric/unit
fails even if the default predictor would not use it: discarded data must not look
successfully processed. Extend `UnitRegistry` explicitly. There is no automatic
conversion between device sites, HRV statistics, raw samples, or daily summaries.
Method, body site, source, and timestamps remain available downstream.

## Migrate the old JavaScript input

```sh
quiet-cycle migrate-v1 examples/legacy-v1.json --subject-id demo --output migrated.json
quiet-cycle predict migrated.json
```

Add `--imported-at` for a new live import. The old format lacks a subject identifier,
so one is required. Payload-bearing legacy tombstones are rejected by the stricter
contract; migrate their deletion identity explicitly. The migration does not make
old browser snapshots or reconstructed history valid as-of evidence.
