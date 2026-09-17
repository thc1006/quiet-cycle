# Evidence review and implementation mapping

Reviewed 2026-09-17. This is a targeted engineering literature review, not a
registered systematic review or proof that every publication has been identified.
No patient data were downloaded. No published clinical accuracy is inherited by
this implementation. The learned residual model is our specified, testable
engineering design, not a claimed reproduction of a proprietary algorithm.

| Source and date | What it supports | Consequence here | Not established here |
| --- | --- | --- | --- |
| [Fukaya et al., 2016](https://arxiv.org/abs/1606.02536) | Sequential BBT observations and latent cycle state can inform onset forecasting | Retain separate state/duration extension and causal inputs | Their fitted parameters or accuracy are not reproduced |
| [Kawamori et al., 2017](https://arxiv.org/abs/1707.06452) | Biphasic latent-state extension | Do not assume fixed ovulation day or fixed 14-day luteal duration | The ridge learner does not diagnose ovulation |
| [Li et al., JAMIA, 2021/2022](https://academic.oup.com/jamia/article/29/1/3/6371799) | Tracking adherence changes apparent cycle lengths | Preserve revisions, knowledge time and explicit continuity | We do not fit their latent missed-cycle model |
| [Urteaga et al., MLHC 2021](https://proceedings.mlr.press/v149/urteaga21a.html) | Predictive distributions need calibration, not just point estimates | Separate forecast type, held-out calibration and interval evaluation | Interval regression is not their generative probability model |
| [Wang et al., Human Reproduction 2025](https://academic.oup.com/humrep/article/40/3/469/7989515) | Wrist temperature can improve next-menses prediction in the studied setting | Normalize and expose temperature changes; require fair lead-time comparison | The paper explicitly withholds proprietary model details; this repo does not reproduce them |
| [Linzmayer et al., npj Women's Health, 2026-04-28](https://www.nature.com/articles/s44294-026-00142-x) | Large multi-symptom sequences support representation learning | Preserve typed symptom history and a replaceable model interface | No foundation-model weights, private data or paper performance are bundled |
| [Digital health scoping review, 2026](https://www.nature.com/articles/s44294-026-00146-7) | Evidence has representation and generalizability limitations | Explicit cohort, eligibility and failure reporting | No claim of equal validity across ages, conditions, regions or devices |
| [mcPHASES, Scientific Data, 2026](https://www.nature.com/articles/s41597-026-06805-3) | Multimodal longitudinal data and practical collection burden | Distinguish raw measurements, vendor-derived labels and self-report | It is a dataset paper, not our accuracy benchmark |
| [MCAnalysis, preprint, 2026-04](https://arxiv.org/abs/2604.12536) | Cycle-associated changes can be studied with periodic models | Separate descriptive symptom analysis from future onset prediction | Association does not establish causality or next-date accuracy |
| [Lei et al., distribution-free predictive inference](https://arxiv.org/abs/1604.04173) | Split calibration for regression | Exact finite-sample score rank with infinity atom | Coverage assumptions are not verified merely by splitting data |
| [Barber et al., beyond exchangeability](https://arxiv.org/abs/2202.13415) | Dependence and drift require care | Forward-personal mode has no exchangeability guarantee; drift stress test retained | No universal calibration under arbitrary drift |
| [TRIPOD+AI, 2024](https://www.bmj.com/content/385/bmj-2023-078378) | Transparent prediction-model reporting | Publish target, cutoffs, development partitions, metrics and limitations | A reporting checklist is not clinical validation |
| [PROBAST+AI, 2025](https://www.bmj.com/content/388/bmj-2024-082505) | Bias/applicability review across data and analysis | Keep selected-population and leakage risks visible | No independent low-risk-of-bias certification |

## Numbers that must not be transferred between tasks

The 2025 wrist-temperature study reports next-menses predictions made at the time
of its ovulation estimate. Its all-signal analysis reports MAE 1.70 days, versus
1.90 for a calendar comparator; its ≥0.2°C subset has different results. This is
not a day-1 next-cycle forecast and not a benchmark for our fixed landmark model.
The paper also states the algorithms are proprietary. No public equation here
can be presented as that algorithm without access and validation.

The 2026 foundation-model study uses 1,206,919 app users; 87% are younger than 33.
Its next-cycle-length task reports MAE 8.90 and RMSE 14.18 days. This is a different
data/task setting from the wearable cohort. Ranking the two by these numbers would
confound task, population, available information and data quality.

mcPHASES includes 42 participants and restrictions on the released human data.
Some phase labels use vendor-provided Mira estimates. They are not independent
ultrasound ground truth. The second collection round reduced burden after user
feedback. We neither bundled restricted files nor used published summary numbers
to fabricate a training cohort.

## Why not add every model to one ensemble?

A weighted sum of unrelated paper results is not a trained ensemble. Algorithms
may predict different targets at different times, use incompatible labels or
require unavailable proprietary parameters. Learned weights require compatible,
authorized observations and an untouched evaluation cohort.

This release therefore provides one fully specified fit/select/calibrate path and
keeps the parameterized state/duration method separate. Model complexity is not an
accuracy claim. Stable-signal, no-signal and reversed-signal fixtures remain in the
repository, including scenarios where the learned model is worse than its baseline.

## Engineering references

- [Scientific Python design](https://learn.scientific-python.org/development/principles/design/): small composable library interfaces.
- [PyPA packaging](https://packaging.python.org/en/latest/tutorials/packaging-projects/): pyproject, wheel/sdist and installable src package.
- [Python typed package distribution](https://typing.python.org/en/latest/spec/distributing.html): `py.typed` and public type information.
- [JSON Schema 2020-12](https://json-schema.org/draft/2020-12): wire contracts; semantic checks remain in code.
- [FHIR R4 Observation](https://hl7.org/fhir/R4/observation.html): limited explicit observation mapping, not a full FHIR implementation.
- [Ridge objective](https://scikit-learn.org/stable/modules/linear_model.html#ridge-regression-and-classification): regularized least squares; our exact solver is independent.
- [Google technical writing tone](https://developers.google.com/style/tone): direct instructions and concrete limits, not promotional claims.

Sources guide design and claims. They do not endorse Quiet Cycle.
