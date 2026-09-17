# Quiet Cycle

**0.3.0 — a typed Python library for menstrual-event data, exact forecasts and
multifactor model development.**

Import records, replay what was known at a prediction time, train a small model,
freeze it as JSON, and use that artifact in another application. No frontend,
account, database, cloud model or training service is required.

The library is executable; **clinical accuracy is not established**. This release
adds a fitted multifactor model to the historical baseline from 0.2.0. It does not
ship human-trained weights and does not claim to combine every published algorithm
or outperform commercial products. The supplied cohort is synthetic software-test
data. Do not use its weights for patient-facing predictions, contraception,
diagnosis, or decisions about seeking care.

[繁體中文](README.zh-TW.md) · [Evidence review](docs/EVIDENCE_REVIEW.md) ·
[Training contract](docs/TRAINING.md) · [Actual tests](docs/TEST_REPORT.md)

## Install and run

Python 3.11+; only Pydantic is required at runtime. NumPy is used by one independent
test, not the learner. This checkout has not been published to PyPI.

```sh
python -m pip install .
python examples/train_multifactor.py --output /tmp/quiet-cycle-example
quiet-cycle forecast /tmp/quiet-cycle-example/request.json \
  --model /tmp/quiet-cycle-example/model.json
```

The example fits, selects, calibrates and evaluates a model on separate synthetic
partitions. It writes the request, fitted artifact, prediction and evaluation so
that each step can be reproduced. It does not download health records.

Embed the **same fitted model** in Python:

```python
from pathlib import Path
from quietcycle import PipelineRequest
from quietcycle.learning import FittedModel, MultiFactorPipeline
from quietcycle.serialization import loads

folder = Path("/tmp/quiet-cycle-example")
model = FittedModel.model_validate(loads((folder / "model.json").read_text()))
request = PipelineRequest.model_validate(loads((folder / "request.json").read_text()))
result = MultiFactorPipeline(model).run(request.dataset, request.query)

print(result.status)
print(result.point_date)
for interval in result.intervals:
    print(interval.nominal_coverage_ppm, interval.start, interval.end, interval.unbounded)
```

No fitted cohort available? `CyclePipeline().run(dataset, query)` still provides
the **uncalibrated historical baseline**, not an equivalent replacement for a
validated multifactor model. See [the baseline example](examples/basic.py).

## What changed

0.2.0 accepted physiological measurements but did not learn their relationship to
cycle length. In 0.3.0, measurements and symptoms can affect a fitted residual
model. Training, candidate selection, calibration and testing are separate. Model
files contain exact coefficients, feature transforms, chosen hyperparameters,
calibration residuals and provenance. They are data, not executable pickles.

| Component | Delivered behavior |
| --- | --- |
| Inputs | Python, JSON, JSON Lines, CSV, mapping rows, limited FHIR R4 Observations |
| Temporal replay | Revisions, import/report time, tombstones, explicit onset continuity |
| Features | History, reported symptom rate/impact, normalized sensor levels and changes |
| Learner | Exact ridge candidates, held-out blending and selection |
| Uncertainty | Split-conformal integer-day intervals; infinity for insufficient ranks |
| Outputs | Typed Python objects, canonical JSON, CLI, optional HTTP |
| Research extension | Separate exact duration/state engine with caller-supplied parameters |

The new result is an **interval forecast**, not a full probability distribution.
It does not invent a probability of starting within three days from two quantiles.

## Mathematical specification

These are the implemented equations, not a proposed future architecture. Source
references below identify the corresponding functions. All fitted arithmetic uses
Python integers and `Fraction` after the explicitly specified feature
quantization. Fixed-point quantization is a modeling choice, not hidden numerical
precision.

### 1. Information available at prediction time

For event revision `e`, let its knowledge time be

$$
k_e=\max(t_{\mathrm{recorded},e},t_{\mathrm{imported},e}).
$$

A query with cutoff `t` sees only the selected subject's revisions with
$k_e\leq t$, choosing the latest available revision of each event. A later
correction cannot improve an earlier replay. Event dates must also be visible in
the query's local-date snapshot. See `ledger.snapshot`.

A learned artifact is for one **fixed landmark** $d$, the elapsed days since the
confirmed onset $A$. Default $d=20$ means cycle day 21, not day 20. It requires an
explicit no-onset report through the completed date immediately before the query.
An unknown day is not negative evidence. Today may still contain the next onset,
so the admissible target is $L\geq d$, not $L>d$.

Default history is 3–12 confirmed consecutive intervals. A break in continuity is
not divided into invented cycles. Context changes exclude earlier intervals;
pauses, a non-natural-cycle declaration and a change within the current cycle
prevent prediction. These gates are engineering scope, not a clinical diagnosis.

### 2. Causal feature extraction

Let $\mathcal H_i$ be the eligible history for case $i$. The personal baseline is

$$
b_i=\operatorname{median}_{\ell\in\mathcal H_i}\ell.
$$

History features also include the last interval, median absolute deviation,
last-minus-previous change, and count.

For each sensor metric $m$, take the median of samples on each **completed** day,
then summarize the recent window $W_r$ and preceding reference window $W_b$:

$$
u_{i,m}=\operatorname{median}_{t\in W_r}\operatorname{median}(v_{i,m,t}),\qquad
\Delta_{i,m}=u_{i,m}-\operatorname{median}_{t\in W_b}\operatorname{median}(v_{i,m,t}).
$$

Defaults: 3 recent days, 7 reference days, at least 2 measured dates per required
window. Wrist temperature, resting heart rate, RMSSD HRV and sleep duration are
separate metrics. Units are normalized exactly. Different source/method/body-site
streams within a window are not averaged; that feature becomes missing and is
flagged. The library does not claim to clean raw optical signals or correct sensor
hardware bias.

For symptom $s$, with $P$ explicitly present dates and $N$ explicitly absent dates:

$$
r_{i,s}=\frac{P}{P+N}\quad(P+N>0).
$$

If $P+N=0$, the value is missing, not zero. An impact feature averages available
impact ratings; explicit absence contributes zero. Conflicting or uncertain
reports do not become negative observations. Defaults are headache, fatigue,
abdominal pain and gastrointestinal symptoms. Names are configurable. See
`learning.landmarks.make_landmark`.

### 3. Train-only scaling, missingness and interactions

Using **training observations only**, feature $j$ has

$$
c_j=\operatorname{median}_{i\in O_j}x_{ij},\qquad
s_j=\frac{1}{|O_j|}\sum_{i\in O_j}|x_{ij}-c_j|.
$$

This scale is the **mean** absolute deviation about the median, not the historical
median absolute deviation above. Set $s_j=1$ when zero. Never-observed training
columns are disabled for inference even if they later appear.

For observed values, use

$$
z_{ij}=\frac{1}{q}\left\lfloor q\,\operatorname{clip}
\left(\frac{x_{ij}-c_j}{s_j},-B,B\right)+\frac12\right\rfloor;
$$

for missing values, $z_{ij}=0$ and a separate missing-indicator column is one.
Defaults $B=8$, $q=1000$ bound outliers and exact-arithmetic cost; clipped values
are flagged. Ties round toward positive infinity. Two predeclared interactions
are temperature-change × heart-rate-change and fatigue-rate × sleep-change.
They use the standardized values. An absent input has zero interaction; missing
indicators remain available. Train-constant columns are removed except intercept.
See `learning.fitting.fit_columns` and `vector`.

### 4. Exact regularized residual models

Predict the residual $r_i=L_i-b_i$. For each predeclared feature family and positive
penalty $\lambda$:

$$
\hat\beta_\lambda=\arg\min_\beta
\left[\sum_{i\in\mathrm{train}}(r_i-x_i^\top\beta)^2
+\lambda\sum_{j=1}^{p-1}\beta_j^2\right].
$$

The intercept $\beta_0$ is not penalized. The normal equations are

$$
(X^\top X+\lambda D)\hat\beta=X^\top r,\qquad
D=\operatorname{diag}(0,1,\ldots,1).
$$

They are solved by deterministic rational Gaussian elimination, not an explicit
matrix inverse. The returned solution is checked against the normal equations
with **exact equality**. Precision budgets fail explicitly; no floating-point
fallback exists. This proves the selected linear-system solution, not prediction
accuracy. See `learning.exact.ridge`.

Candidate families: history, history+symptoms, history+wearables, and combined with
interactions. Default penalties are 1, 10 and 100; a pure personal-baseline
candidate is always included. These are a small predeclared search space, not an
exhaustive model search or a published state-of-the-art claim.

### 5. Held-out blending and candidate selection

On the **tuning partition**, candidate correction $g_i=x_i^\top\hat\beta$ receives

$$
a=\operatorname{clip}\left(
\frac{\sum_i g_i(L_i-b_i)}{\sum_i g_i^2},0,1\right),
$$

with $a=0$ for a zero denominator. This is the exact least-squares blend **before**
the survival floor; it is not asserted to optimize the floored objective globally.
Candidates are scored using the actual floored continuous prediction:

$$
\widetilde L_i=\max(d,b_i+a g_i),\qquad
\mathrm{MSE}_{\mathrm{tune}}=\frac1n\sum_i(L_i-\widetilde L_i)^2.
$$

Choose minimum tuning MSE. Ties favor baseline, then simpler family, then larger
penalty. Do not refit on calibration. The output day is

$$
\widehat L_i=\max\left(d,\left\lfloor b_i+a g_i+\frac12\right\rfloor\right),
\qquad \widehat T_i=A_i+\widehat L_i.
$$

The tuning optimum can still be worse on a new test cohort. Both good and bad
synthetic examples remain in [the benchmark](evidence/learning-benchmark.json).

### 6. Separate calibration; never hide an unbounded interval

For the frozen predictor, calibration scores are

$$
e_i=|L_i-\widehat L_i|,\quad
k=\lceil(n_{\mathrm{cal}}+1)(1-\alpha)\rceil,\quad
q_\alpha=\begin{cases} e_{(k)},&k\leq n_{\mathrm{cal}},\\+\infty,&k>n_{\mathrm{cal}}.\end{cases}
$$

For finite $q_\alpha$, return

$$
[A+\max(d,\widehat L-q_\alpha),\ A+\widehat L+q_\alpha].
$$

Otherwise `unbounded=true` with null bounds/radius. The implementation returns
80% and 90% **nominal** intervals. It never substitutes the largest available
residual for the required infinity atom. An interval includes calendar dates at
both ends; width reports count those dates.

Split-conformal coverage requires exchangeable calibration/test scores under the
fixed predictor and eligibility rule. Person-disjoint partitions and one
calibration/test case per person prevent one obvious dependency error, but do not
prove exchangeability. Time drift, population changes and symptom-related missing
labels can invalidate coverage. `forward-personal` explicitly carries **no
coverage guarantee**. There is no per-person 90% guarantee and no guarantee for a
chosen subgroup. See [conformal theory](https://arxiv.org/abs/1604.04173) and
[non-exchangeable settings](https://arxiv.org/abs/2202.13415).

### 7. What explanations mean

Each returned contribution is $a\beta_jx_j$; summing contributions and $b_i$ exactly
recovers the **raw** prediction before rounding/flooring. This is arithmetic
attribution, not proof that fatigue or heart rate causes a change in cycle length.

The separate duration-model extension retains the previous first-passage method:
for a finite non-absorbing transition matrix $Q$, start distribution $\pi$ and
$r=\mathbf1-Q\mathbf1$,

$$
P(T=k)=\pi Q^{k-1}r.
$$

Its duration-expanded implementation preserves residual tail mass. It is not
jointly fitted by this ridge learner and ships no trained hormonal parameters.

## Train on authorized data

```python
from quietcycle.learning import FitRequest, fit, evaluate
from quietcycle.serialization import canonical_json

# train_cases, tune_cases, calibration_cases and test_cases must be built
# from separate knowledge-time snapshots; see docs/TRAINING.md.
request = FitRequest(train=train_cases, tune=tune_cases, calibration=calibration_cases)
model = fit(request)
report = evaluate(model, test_cases)
```

This code fragment assumes caller-supplied cases; the synthetic example above is
self-contained. `build_cases()` reports every rejected/censored request separately.
Right-censored cases are **not used for regression fitting**. Their exclusion can
bias the population; report it and do not present complete-case accuracy as an
all-user result.

The default `new-subject` mode checks subject disjointness and chronology:
all outcomes in each earlier partition must be known before the next partition's
prediction cutoffs. One cycle cannot enter two partitions. A fitted artifact cannot
be replayed before its data-availability boundary. These timestamps are supplied
data-knowledge limits, not evidence that a model was physically deployed then.
Hosts must keep their own model creation/release audit record.

A fixed day-20 model cannot be used at day 1, day 10 or day 25. Train and validate
separate artifacts for other allowed landmarks; do not interpolate accuracy
claims between them. The software minima (8 train, 4 tune, 1 calibration) are input
sanity limits, **not an adequate clinical sample-size recommendation**.

## Data and interfaces

```text
JSON / JSONL / CSV / rows / limited FHIR
 -> CycleDataset + Query
 -> causal snapshot + continuity checks + unit normalization
 -> fixed Landmark
 -> training: train -> tune -> frozen model -> calibration -> untouched test
 -> inference: FittedModel + Landmark -> LearnedPrediction
```

`quietcycle.learning` exports `make_landmark`, `label_landmark`, `build_cases`,
`fit`, `predict_landmark`, `MultiFactorPipeline`, `evaluate`, and typed contracts.
Use existing adapters to construct `CycleDataset`; no parallel sensor pipeline is
needed. See [imports](docs/IMPORTS.md) and [data contract](docs/CONTRACT.md).

```sh
quiet-cycle fit fit-request.json -o model.json
quiet-cycle forecast request.json --model model.json
quiet-cycle evaluate test-cases.json --model model.json
quiet-cycle schema fitted-model
```

The learning wire format is `learning-1.0`. Existing event/legacy forecast contracts
remain version 2.0. Eleven JSON Schemas ship with the wheel. HTTP is optional:
`create_app(model=fitted_model)` adds `/v3/forecast` beside `/v2/predict` and
OpenAPI 3.1. There is no training endpoint, HTML or authentication. See
[HTTP embedding](docs/HTTP.md); do not expose it directly to the internet.

## Reproducibility, privacy and extension

Fixed inputs, model, specification and dependency environment produce the same
project-canonical JSON. No RNG, wall-clock reads, floating-point fit, external
model API or telemetry is used. `canonical_json` is not RFC 8785 JCS. Dense exact
algebra has finite resource limits and is not a million-user training engine.

Model JSON contains statistics and audit hashes; **it is not anonymous**. Subject
hashes can be guessed, and small-group coefficients or calibration errors can
reveal information. Protect models, training reports and exported records like
health data. No patient dataset or human-fitted artifact is included. See
[SECURITY.md](SECURITY.md).

`CyclePipeline(predictor=..., feature_builder=...)` remains available for forks and
alternative models. Keep output contracts honest: an interval-only learner must
not pretend to provide a calibrated probability mass function. Change model IDs
when changing equations. See [extensions](docs/EXTENDING.md).

## Verify this release

```sh
python -m pip install -e ".[dev,api]"
python -m pytest --cov=quietcycle --cov-report=term
python scripts/generate_contracts.py --check
python scripts/check_repository.py
python scripts/benchmark_learning.py
python scripts/run_mutations.py
python -m mypy src/quietcycle
python -m ruff check src tests examples scripts
python -m build
python scripts/check_artifacts.py
```

The commands are a release checklist, not a claim that unavailable tools ran.
[TEST_REPORT.md](docs/TEST_REPORT.md) identifies executed and unexecuted checks.
Node is only a compatibility-test tool. No frontend is included.

MIT licensed. [Contributing](CONTRIBUTING.md) · [Release process](docs/RELEASING.md) ·
[Review findings](docs/REVIEW.md) · [Research mapping](docs/EVIDENCE_REVIEW.md).
