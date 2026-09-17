# Training and evaluating a frozen artifact

## The unit of prediction

A case asks: at one prespecified number of elapsed days since a confirmed onset,
using only information available at the query cutoff, on which date will the next
confirmed onset occur? This is not a phase-classification or ovulation task.

The default landmark is 20 elapsed days. An artifact cannot be reused at another
landmark. The eligibility rule requires explicit completed-day no-onset evidence,
a declared natural-cycle context, and clean consecutive history. Results apply to
that selected population, not all cycles or all users.

## From the existing event pipeline

```python
from quietcycle.learning import LandmarkSpec, build_cases

spec = LandmarkSpec(elapsed_day=20)
built = build_cases(
    dataset,
    tuple(queries),
    spec=spec,
    labels_cutoff="2026-08-31T23:59:59Z",
    data_kind="observational",
    cohort="authorized-site-a-v1",
)
print(len(built.cases), built.rejected)
```

`dataset` and `queries` are caller-supplied typed objects. For an executable full
example use `examples/train_multifactor.py` with the included synthetic records.

Each feature snapshot uses its original query cutoff. Labels use a separate later
snapshot. A changed or removed anchor, unknown continuity, a duplicate onset date,
a later-discovered outcome before the landmark, and right censoring are not usable
regression labels. Every rejected requested case is returned with a reason. Save
that report; removing it produces a misleading complete-case benchmark.

Direct construction of `Landmark` / `LabelledCase` supports external ETL, but the
library cannot prove the truth of caller-supplied values. Prefer the raw event
builder. Query context (including treatment changes) must itself reflect what was
known at the query time; do not backfill future clinical knowledge into it.

## Four partitions, not random daily rows

1. Training fits scaling, missing-feature policy and ridge coefficients.
2. Tuning fits blend weights and selects one candidate.
3. Calibration only computes absolute residual ranks for the frozen selection.
4. Testing never affects any earlier step.

Use calendar-separated blocks. For each adjacent development partition, every
outcome in the earlier block must have become available before every prediction
cutoff in the next block. One subject/anchor pair cannot appear twice. The fitter
sorts cases before calculating, so input row order does not change the artifact.

In `new-subject` mode, subjects are disjoint across development partitions and from
inference. Calibration and testing permit one case per person. The model retains
hashed identifiers to detect reuse. This is conservative cohort-level evaluation,
not a proof of independent or exchangeable data.

`forward-personal` allows recurring people across time-separated partitions, but
it explicitly removes the exchangeable-coverage claim. It is not a free shortcut
to well-calibrated per-person intervals. Compare cold-start and returning-user
models separately, on future periods of data.

Training permits 8 cases, tuning 4, and calibration 1 to allow small reproducible
software fixtures. These minima are not a study design. With 1 calibration score,
the 80% and 90% intervals are both unbounded. With 8 scores, a 90% interval is
unbounded. The infinity atom is intentional.

## Fit, serialize, predict

```python
from quietcycle.learning import FitRequest, fit, evaluate, FittedModel
from quietcycle.serialization import canonical_json, loads
from pathlib import Path

request = FitRequest(
    spec=spec,
    train=train_cases,
    tune=tune_cases,
    calibration=calibration_cases,
    split_mode="new-subject",
)
model = fit(request)
Path("model.json").write_text(canonical_json(model), encoding="utf-8")
restored = FittedModel.model_validate(loads(Path("model.json").read_text()))
report = evaluate(restored, test_cases)
```

Do not fit a final model on calibration or test after selecting a good result.
That creates a different predictor whose intervals and test metrics no longer
apply. A refitted release needs fresh calibration and a genuinely untouched test.

The `fitted_at` and `available_at` fields encode data-knowledge boundaries. They
are not wall-clock execution timestamps or proof of deployment. Record artifact
creation time, code version, environment lock, consent/data agreement, cohort
selection and publication authorization separately in the host's audit trail.

## Interpreting the result

`point_date` is an integer-day estimate. `intervals` are nominal conformal sets.
`raw_cycle_length` is before rounding/survival flooring. `contributions` sum to the
raw length minus the personal baseline; they are not causal explanations.
An interval with null bounds and `unbounded=true` means insufficient calibration
rank, not that every future date has equal probability.

`evaluate()` preserves attempted, estimated, abstained, maximum error, MAE, MSE,
±1/±3-day counts, coverage, unbounded counts and finite interval width. Report it
alongside `build_cases.rejected`. Stratified reports must include each group's
count and all selection criteria. Small groups cannot establish performance
parity, and coverage is not a guarantee for each group.

## Sensor/data discipline

Use one prespecified measurement stream per metric. The learner cannot tell
whether a vendor changed firmware, preprocessing or a night-temperature algorithm
without supplied provenance. No normalization should use future days, full-cycle
means or post-onset corrections at an earlier cutoff. Do not resample missing
symptoms into absence. Do not combine wrist, body and skin temperatures.

The library imports measurements, but it does not fetch device accounts, derive
clinical hormone thresholds, perform signal-quality calibration or encode all
medical conditions. Extra covariates require a versioned feature builder,
predeclared evaluation plan, and validation of their incremental value.

## Before patient-facing deployment

Complete independent dataset validation, prespecified subgroup checks, lead-time
matching, failure/abstention reporting, privacy/security review and the applicable
clinical/regulatory assessment. This repository supplies tools for that work; it
does not supply approval. Never deploy the example's synthetic weights.
