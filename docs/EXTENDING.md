# Extending the library

Start with a small adapter or a replacement predictor, not a fork of the whole pipeline.
`examples/custom_predictor.py` is executable. It wraps the baseline with different,
explicitly versioned policy settings; it does not pretend those settings are validated.

## Predictor protocol

```python
from quietcycle import Features, Forecast, Query

class Predictor:
    model_id: str
    model_version: str
    used_features: tuple[str, ...]

    def predict(self, features: Features, query: Query) -> Forecast:
        ...
```

This is a structural protocol: subclassing is optional. Pass an instance to
`CyclePipeline(predictor=instance)`. Return exact fractions and declare which features
you use. All predictor results pass the same output checks. Change model_version
when parameters or logic change. A calibration claim needs a separate validated
contract; the current `Forecast` deliberately fixes calibration to `unvalidated`.

## Feature builder and unit registry

`FeatureBuilder.build(snapshot, query)` returns `Features`. Keep the snapshot hash,
subject boundary, and knowledge cutoff intact. Do not normalize using future samples.
A custom `builder_id` must identify the code and configuration, including aggregation
and unit rules. Feature builders are trusted code, not isolated extensions.

`UnitRegistry(extra_rules=...)` accepts exact Fraction scale/offset transformations.
It rejects replacement of built-ins. Its signature is included in the default
builder ID, which prevents silently reusing provenance after changing a conversion.

## Research duration model

`DurationResearchPipeline` consumes the same typed data and snapshot, normalizes
measurements, chooses the latest eligible value for an explicit metric/unit/source,
applies a caller-defined range rule, and calls `duration_forecast()`.
Equal-time competing values cause abstention rather than order-dependent selection.
The range is [lower, upper); thresholds and likelihood weights are entirely supplied
by the caller. These are research parameters, not clinical defaults.

The exact model expands each state by age. Its duration weights induce an exit
hazard; weighted transitions can enter another state or the absorbing event.
The result includes mass after the horizon or never, without renormalization.
Duration 1 means exit on the next step. Initial age is conditioned on still being
in that state. Tests compare this implementation with an independent remaining-
duration countdown calculation.

## Adapter contract

A custom adapter can be a simple function from source rows to `CycleDataset`.
Do not insert guessed continuity, drop unknown columns without disclosure, infer an
onset from a symptom/temperature, or label retrospective reports as prospective.
Keep retrieval, consent, and credentials outside the package. Vendor-specific SDKs
can remain separate optional packages maintained by their users.

## Forking

MIT permits modification and redistribution with the license notice.
Change distribution/import names when maintaining an incompatible fork. Keep the
contract version or introduce an explicit new one; do not reuse model identities
for changed behavior. Run the installed-artifact tests, not only tests against src/.
