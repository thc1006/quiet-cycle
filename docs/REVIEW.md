# Release review — 0.3.0

Scope: audit the retained 0.2.0 library and add an actual fitted multifactor path
without claiming clinical accuracy. Review date: 2026-09-17. AI-assisted engineering
review and automated verification, not independent clinical or security approval.

## Material changes relative to 0.2.0

The old kernel is still a historical baseline. Previously, physiological data
passed through typed normalization without learned effects. The new path fits
history/symptom/wearable residual candidates, selects on a separate tuning block,
then calibrates on untouched observations. README contains the implemented
formulae and distinguishes proposed research from delivered behavior.

The old duration engine is retained as a separate parameterized model. It is not
silently claimed to have learned hormones from the ridge cohort. Published studies
with different prediction times and targets are not ranked as though they shared
one benchmark. Proprietary model internals were not fabricated from their results.

## Findings and corrections in this iteration

| Finding | Correction | Verification |
| --- | --- | --- |
| Raw-event scope checks could be bypassed through direct landmarks | Pause, natural-cycle and within-cycle context checks added to direct prediction; development cases checked too | Direct scope and training-scope regressions |
| A label discovered later could place the outcome before the original landmark | Reject and account for that case instead of letting it become a future label | Late-discovered-outcome regression |
| Exact multivariate normal equations can grow very expensive without a declared precision policy | Explicit train-only clip/quantize step, feature bit budget and exact solver budget; no float fallback | Strict numeric and solver tests; README formula |
| A computed linear solution might not be audited against the intended objective | Certify exact normal equations after solving; intercept remains unpenalized | 60 systems and independent NumPy comparison |
| Small calibration sets could tempt maximum-score substitution | Retain the n+1 rank and infinity atom | Rank tests, exhaustive permutation case and targeted mutation |
| Learned model scope could appear interchangeable with the baseline HTTP endpoint | Separate model-bound `/v3/forecast`, no training/model-upload route | Installed live HTTP equals SDK and CLI |
| Old release logs could be mistaken for current tests | New evidence directory; historical reports archived separately | New 187-test run and installed-artifact report |

## Adversarial checks and mathematical boundaries

Training does not use tuning scaling, calibration labels or test labels. The
selection and blend use tuning only. Calibration changes do not change fitted
coefficients. Future backfills cannot enter an earlier landmark. Data and model
knowledge boundaries are explicit; physically creating a model later is not proof
it was deployed historically, and hosts must retain that separate audit timestamp.

The blend equation minimizes the unfloored tuning residual objective. Candidate
selection uses floored continuous predictions. README states this distinction;
we do not falsely label the blend an exact optimizer of the floored piecewise loss.
Integer-day calibration uses the same frozen rounded predictor as inference.

The model's contribution sum equals its raw correction; contributions do not imply
causality. Missingness may still encode behavior and distribution shifts. Subject
hashes detect reuse but are not anonymous. A checksum detects changes, not trust.
Caller-built landmarks are validated structurally but their truth cannot be proven.

## Retained failures and residual risks

The unrelated-target and reversed-relation synthetic benchmarks are worse than
the personal-history baseline. The tuning winner is not guaranteed to generalize.
No attempt was made to relabel those cases or tune the generator after inspecting
test performance. Calibration under drift does not inherit the exchangeable proof.

The data gates select complete-labelled, confirmed-history cases; censoring and
symptom-related absence may bias that cohort. The model is not trained on all
medical states, all ages, all populations, or all device processing methods.
It is linear with two specified interactions, not an exhaustive model search.
There is no human-trained artifact, no clinically calibrated global parameter set,
and no claim of zero error. Exact arithmetic removes a numerical ambiguity; it
does not remove biological, measurement or sampling uncertainty.

Tests and packaging checks passed as listed in TEST_REPORT. Static checkers,
clean dependency resolution, full platform matrix and clinical validation remain
unexecuted. No hidden fallback presents them as passes.

## Publication gate

A maintainer should complete the unexecuted engineering checks and an authorized,
prespecified external validation before making clinical or population-wide claims.
The repository is usable for integration, reproducible training and research now.
Patient-facing use requires additional evidence and host-level safeguards.
