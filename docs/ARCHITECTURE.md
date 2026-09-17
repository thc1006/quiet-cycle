# Architecture

The package has one event-data boundary and two explicit forecast paths.
The historical path retains these replaceable steps:

1. An importer returns `CycleDataset`. It does not read user accounts or invent missing events.
2. `Query` states the subject, civil date, cutoff instant, offset, and operating context.
3. `snapshot()` selects the subject and versions actually available at the cutoff.
4. `FeatureBuilder.build()` returns an immutable `Features` object.
5. `Predictor.predict()` returns `Forecast`; the pipeline revalidates it before returning.

The default feature builder normalizes only an explicit UCUM subset. Unit-registry
configuration contributes to its identifier. The default model's policy contributes
to its version. A custom component must change its identity when behavior changes.
The pipeline checks returned identity, non-past support, probability conservation,
interval mass, near-term mass, date/length consistency, and feature provenance.
Custom Python components remain trusted code; this is not a plugin sandbox.

## Package boundaries

`models.py` defines the contract. `adapters/` translates transport formats.
`ledger.py` resolves versions. `features.py` constructs evidence.
`predictors.py` implements the default baseline. `research/` contains caller-
parameterized exact duration calculations, not fitted physiology.
`cli.py` and `api.py` are transport adapters; neither owns the algorithm.

The SDK has no database, telemetry, hidden clock, network request, account, or
process-global auto-discovery. Pydantic is the only required dependency.
The API extra does not load when importing the core library.

## Why Python rather than a web application

The target is an embedded scientific library: a program supplies objects and gets
objects back. Python packaging, a `src/` layout, typed exports, protocols, wheel/sdist,
and examples make that use straightforward. A HTTP wrapper remains optional.
The earlier JavaScript release is retained only as a frozen regression oracle under
`tests/reference_js`, not as a second maintained runtime or a browser feature.

## Extension policy

Use explicit object injection. It is inspectable, easy to test, and avoids loading
third-party entry points merely because they are installed. A downstream project
may add entry-point discovery at its own application boundary. Keep secrets,
data retrieval, encryption, and authentication there, not inside prediction math.


## Fitted multifactor path (0.3)

`learning.landmarks` builds a fixed, original-cutoff feature vector from the same
snapshot and normalized evidence. Outcome labels come from a separate later
snapshot. `learning.fitting` owns training, tuning and calibration; it returns a
frozen `FittedModel` JSON artifact. `learning.prediction` loads that artifact without
refitting and returns `LearnedPrediction`, a date/interval contract, not the
historical probability-mass contract. `learning.evaluation` consumes held-out
labels without exposing them to prediction. README contains the actual equations.

Raw-event and direct-landmark APIs both check scope and model availability.
External feature builders remain trusted code. Their content cannot be proved by
hashing or validation alone. The optional model-bound HTTP route is only transport;
it shares the same predictor and never accepts untrusted training jobs.
