# Model card: exact-landmark-ridge-ensemble-v1

## Status

An implemented training/inference algorithm, first shipped with Quiet Cycle 0.3.0.
No clinically fitted artifact ships with the library. Synthetic example artifacts
are marked synthetic and must not be used for real patient predictions. Actual
clinical validation is not established. This is not a best-in-world model claim.

## Intended use and exclusions

Research and developer integration for predicting the next user-confirmed menstrual
onset at one fixed elapsed-day landmark, under a declared natural-cycle context.
Not contraception, diagnosis, pregnancy detection, PMDD assessment, emergency
triage or automatic ovulation confirmation. The user supplies trustworthy context;
the library cannot detect conditions or treatments absent from the record.

A prediction requires confirmed history and explicit no-onset evidence through
yesterday. Missingness, uncertain anchors, continuity breaks, pause or within-cycle
context changes cause abstention or a missing feature. Frequent abstention may
make a configuration unsuitable for the intended application even if MAE looks low.

## Inputs and output

Uses typed event data or externally constructed, validated landmarks. Default
history, symptom and sensor features are documented mathematically in README.
Features may be absent. Missing-indicator patterns can encode logging behavior;
they should not be interpreted as inferred symptoms.

Produces integer date estimates, nominal 80/90% intervals, exact raw contributions,
model digest and issue flags. It does not provide a calibrated daily probability
mass function. Interpretation of a contribution is algebraic, not causal.

## Learning and numerics

Train-only median / mean-absolute-deviation transforms, bounded quantization,
exact positive-ridge residual fits, tune-only constrained blend and candidate
selection, then separate rank calibration. No stochastic training, BLAS or matrix
inverse. Fixed rational equations do not eliminate statistical, measurement,
sampling or future-state uncertainty. See README for each formula and its source.

All hyperparameters are explicit in the specification/artifact. Defaults are
engineering choices, not clinical recommendations. Dense rational fitting is
intended for small feature sets and bounded datasets. Each partition has a 5,000
case input bound; that is not a throughput guarantee. Precision budgets may reject
larger/higher-complexity calculations rather than approximate silently.

## Validation limitations

Software tested on synthetic fixtures, exact independent mathematical checks and
installed interfaces. No human-cohort benchmark, external validation, power study,
subgroup fairness assessment, multi-site testing or clinical trial was performed.
The synthetic stress suite contains harmfully misleading feature relationships;
when test relationships reverse, error can exceed a historical baseline.

New-subject mode checks person disjointness but cannot prove calibration/test
exchangeability. Forward-personal mode labels intervals as lacking a coverage
guarantee. Drift, selection, device changes and symptom-related missingness can
break calibration. Censored outcomes are not fitted; report every excluded case.

## Deployment responsibilities

Use a prespecified external test and persist prediction snapshots. Validate each
landmark, device, cohort, consent process and user workflow. Track error tails,
coverage/width, abstention and material data shifts. Recalibration requires fresh
labels and versioning; do not secretly refit on production outcomes then reuse old
metrics. Set product-level stopping criteria before using the result with people.

Artifacts contain sensitive derived information. Hashed IDs are not anonymization.
Protect them, avoid logs/analytics containing records and use authenticated host
services. The optional HTTP adapter is not a production security boundary.
