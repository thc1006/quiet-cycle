# Release review — 0.2.0

Scope: input adapters, immutable contracts, time-aware event selection, unit
normalization, exact forecasts, extension boundaries, package contents and local
integration. This is an engineering review, not clinical approval.

## Corrections made

| Finding | Change | Regression evidence |
| --- | --- | --- |
| Malformed CSV integer tokens could reach generic conversion failures | Validate the complete integer spelling before conversion | Adapter malformed-row tests |
| Blank JSONL rows could shift error line numbers | Preserve physical line numbers | JSONL row-error test |
| Serialized nested models could bypass the float guard | Recursively validate their dumped content | Nested-model serialization test |
| Different custom unit rules could share an identity | Hash exact rules into the feature-builder identity; expose no mutable rule map | Custom-registry tests |
| FHIR resources from different servers could collide | Include an explicit source ID in stable identity | Two-server source test |
| FHIR body site or method might disappear at normalization | Require an explicit mapping when supplied; reject unmapped metadata | Site/method mapping tests |
| Very large exact fractions could hit Python's decimal conversion limit | Bound calculation precision and fail explicitly instead of rounding or changing process-global limits | Precision-budget test |
| Public model copies can bypass Pydantic construction-time validation | Revalidate dataset, query, model and forecast at public execution boundaries | Forged-copy tests |
| A selected Fahrenheit mutation survived its test target | Add nonzero and zero-point Fahrenheit conversions | Before/after mutation evidence |

The OpenAPI adapter uses an explicit application subclass rather than replacing an
instance method at runtime. Generated schemas are checked against the models.
No frontend files or frozen JS reference files enter the installable wheel.

## Invariants reviewed

An unknown day is not a negative report. Bleeding and onset are different event
kinds. A no-onset report only covers completed local dates. Revisions are selected
using both report and import time. Other subjects and unavailable future records
do not affect a query's snapshot. A new import does not backdate knowledge.

Body, skin and wrist temperatures remain different metrics; RMSSD and SDNN do too.
Decimal spellings are preserved until exact conversion. A custom unit rule cannot
silently override a builtin rule. Device measurements are carried through the
pipeline but do not secretly alter the default historical predictor.

Forecast mass is conserved, displayed ppm sums to one million, and the duration
model retains probability outside the supplied horizon. A research configuration
must identify its model, evidence rule and feature builder. Finite arithmetic
budgets may reject complex research inputs; they do not trigger a float fallback.

The repository does not fetch imports, authenticate users, infer pregnancy,
classify disorders, store a database, or manage application-level consent. Those
boundaries belong to the host application. Forks may replace the model but should
change its identifier and tests rather than retain misleading provenance.

## Residual limitations

The baseline uses engineering policy values, not fitted or clinically calibrated
parameters. Strict import rules may require explicit upstream cleanup. FHIR support
is a deliberately limited scalar Observation subset. Full FHIR profile validation,
vendor data connectors and automatic terminology resolution are not included.

The exact research state model is parameterized by the caller; no wearable-trained
model or globally representative prior is shipped. Passing synthetic tests proves
neither predictive utility nor equality of outcomes across populations.

Static type/lint tools, the complete dependency installation path, and the CI OS /
interpreter matrix remain unexecuted here. See TEST_REPORT.md. Runtime types and
installed artifacts were checked, but that is not equivalent evidence.

## Editorial review

Documentation starts with working code and explicit input/output behavior. It
avoids invented users, badges, DOI identifiers, publication claims and testimonials.
Examples have fixed synthetic dates. Claims distinguish implementation from test
results and research proposals. AI assistance is disclosed in NOTICE; no claim is
made that an authorship detector will classify the text in a particular way.
