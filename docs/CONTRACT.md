# Data contract 2.0

Schemas are generated from the Pydantic models in `src/quietcycle/models.py`.
They ship in the wheel as `quietcycle.schemas` and can be exported through the CLI.
JSON Schema 2020-12 describes shape; runtime validation additionally checks calendar
validity, revision consistency, references, exact fractions, and probability sums.
Schema validation alone is not equivalent to running the pipeline. Schema IDs are
stable UUID URNs; all referenced definitions resolve locally. Exact fractions have
a 2,048-decimal-digit wire limit. The research engine rejects a 6,800-bit precision
budget overrun instead of rounding or changing the host integer-string limit.

## Dataset and query

`CycleDataset` contains `schema_version: "2.0"` and an event sequence.
`Query` requires `subject_id`, `as_of`, `cutoff`, `utc_offset_minutes`, and `context`.
`context.mode` is explicit: `natural-cycle`, `other`, or `unknown`.
The baseline only estimates in `natural-cycle` when not paused. `changed_since`
resets the usable history boundary; it does not diagnose the reason for change.

Use pseudonyms, not names or email addresses. Identifiers are bounded ASCII tokens.
Offsets are explicit minutes in [-840, 840]. Civil dates are Gregorian YYYY-MM-DD
in 1900–2200. Instants require an offset and at most millisecond precision and are
normalized to UTC. The query's local cutoff date must equal `as_of`.
No timezone database or host locale is consulted. DST and travel offsets are supplied
per event/query by the integration layer; the original event's civil day is not rewritten.

## Event kinds

| Kind | Required meaning | Important fields |
| --- | --- | --- |
| onset | A reported cycle-start event, distinct from arbitrary bleeding | date, certainty, previous_onset_id, continuity |
| no-onset | An explicit report covering completed days without a new onset | anchor_id, through |
| symptom | A named patient report, not a diagnosis | date, symptom, state, optional impact 0–3 |
| checkin | Minimal entry when the person has little time or energy | date, state |
| bleeding | No bleeding, spotting, flow, or uncertain | date, state |
| measurement | A measured quantity or explicit missing measurement | date, metric, value, unit, measured_at, state |
| delete | Tombstone for an event's later revision | target_kind |

Every event has `subject_id`, `id`, `revision`, `recorded_at`, `utc_offset_minutes`,
and source provenance. `revision` defaults to 1; it is not a timestamp.

A confirmed consecutive interval requires the later onset to name the preceding
onset and set `continuity: "confirmed"`. This is a claim supplied by the user or
responsible upstream system. The library cannot prove the report is true.
Generic imports never manufacture this link. Deleted, missing, uncertain, or
excluded starts can break history and cause abstention.

A no-onset report must end before the local date on which it is recorded.
The current unfinished day is never interpreted as a completed negative day.

## Knowledge time and revisions

Availability is `max(recorded_at, provenance.imported_at)` when an import timestamp
exists. Imported data must not be backdated into earlier predictions. Omit
`imported_at` only when the local system actually had the original report at
`recorded_at`. A later correction is a new revision, never an in-place rewrite.
The snapshot selects visible revisions only, then removes tombstones. A future
revision cannot overwrite a historical snapshot. An identical duplicate is
idempotent; different content at the same subject/id/revision is an error.
Revision times must not run backwards among the visible versions.

## Exact numbers

Structural integers are JSON integers, not booleans or numeric strings.
Measurement values are decimal strings, such as `"36.75"`, not binary floats.
No exponent notation or NaN/Infinity is accepted. A missing measurement requires
`state: "missing"`, `value: null`, a unit, and a missing reason.
Symptoms distinguish present, absent, uncertain, and skipped. No event means unknown.

Fractions are reduced numerator/denominator strings with positive denominators.
Prediction support is ordered and sums exactly to one; display ppm sums to
1,000,000. Model intervals are explicitly uncalibrated. The project-defined
canonical JSON is sorted, ASCII escaped, compact, and float-free. It is not JCS.

## Bounds and errors

Text imports and HTTP requests are limited to 16 MiB. A dataset contains at most
50,000 events. Batch queries are limited to 10,000. These are engineering limits,
not clinical thresholds or safeguards for an untrusted public service.
Input errors expose a code and, for tabular imports, a row number—not raw values.
Direct Pydantic constructor errors can include the caller's supplied data; do not
log them in a health-data application. The CLI/HTTP boundaries redact them.

## Versioning

Contract 2.0 is intentionally different from the JavaScript contract 1.
Do not silently rename fields in existing integrations. The `from_v1()` adapter
and `migrate-v1` command are explicit migration paths. Library 0.x APIs can change
in a minor release; contract changes need a new schema version and migration notes.
