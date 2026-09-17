# Test report — 0.3.0

Executed on 2026-09-17, Linux x86-64, Python 3.13.5. Synthetic fixtures only;
no clinical accuracy, contraceptive effectiveness or patient safety was evaluated.
The prior release reports are retained under `docs/archive/`, not presented as
current evidence.

## Executed checks

| Check | Result | Evidence |
| --- | --- | --- |
| Full pytest | 187 passed, no failures/skips in this run | `evidence/pytest.log`, `pytest.xml` |
| Combined statement/branch coverage | 85.64%; 2,082 statements and 774 branches | `evidence/coverage.json` |
| Legacy JS/Python parity | 300 generated requests | `tests/test_reference.py` |
| Integer kernel / display allocation | 1,400 generated cases | `tests/test_reference.py` |
| Independent duration countdown oracle | 200 exact models | `tests/test_research.py` |
| Ridge normal-equation check | 60 generated systems over 3 positive penalties | `tests/test_learning.py` |
| Independent numerical ridge comparison | One NumPy linear solve, error below 1e-12 | `tests/test_learning.py` |
| Conformal finite-sample enumeration | All 120 orderings; expected 4/5 coverage | `tests/test_learning.py` |
| Selected regression mutations | 14/14 caught | `evidence/mutations.json` |
| Installed wheel, outside checkout | 24 checks, including live learned HTTP | `evidence/artifact-smoke.json` |
| Contract drift | 11 JSON Schemas and 1 default OpenAPI document | `evidence/contracts.log` |
| Syntax / exports / documentation links | 52 Python files parse for 3.11; 29 core and 15 learning exports | `evidence/repository-check.json` |
| Different Python hash seeds | Same serialized learned result for 0, 7 and 123456 | `tests/test_learning.py` |

The generated cases are loops within tests, not extra test functions or people.
The normal-equation certificate checks the selected ridge objective, not whether
it is the right model for human cycles. Coverage is not proof of no defects.

## What the added tests exercise

Separate train/tune/calibration/test behavior; late reports and labels; model data
availability; person overlap; duplicate cycles; fixed-landmark mismatch; positive
penalties; collinearity; strict numeric types; exact rounding; unbounded calibration
sets; missing/uncertain symptoms; stream changes; completed-day windows; revised
anchors; right censoring; explicit scope and pause checks for both raw and direct
feature APIs; and equivalent SDK, CLI, JSON and HTTP outputs.

The CLI roundtrip executes fit, loads its artifact, predicts and evaluates in fresh
processes. Installed checks run outside the checkout using the built wheel, execute
the included synthetic training script and compare learned SDK/CLI/localhost HTTP.
They also check the baseline examples, Node caller, wheel RECORD hashes and no
frontend files in the wheel.

## Three fixed synthetic scenarios

Each uses 36 training, 18 tuning, 24 calibration and 24 test subjects/cases, with
separated calendar blocks and no rejected fixture cases. The generator specifies
which measurements correlate with the target; it is not a simulator validated
against human physiology.

| Scenario | Learned test MAE | Baseline MAE, same cases | Interpretation |
| --- | --- | --- | --- |
| Stable constructed signal | 13/12 days (1.0833) | 9/4 days (2.25) | The full pipeline can learn the supplied relation |
| Unrelated target component | 77/24 days (3.2083) | 11/4 days (2.75) | Tuning selection can overfit; it is not guaranteed better on test |
| Relation reverses only in test | 19/4 days (4.75) | 8/3 days (2.6667) | Drift can defeat the learned association and interval coverage |

All selected `wearable-ridge-1` in this fixture. This is not a conclusion that
wearables are universally superior. `evidence/learning-benchmark.json` retains the
full attempt counts, interval widths, coverage, tails, selected model and hashes.
There was no retuning to remove the adverse rows. These are software experiments,
not an empirical superiority claim or a clinical sample-size study.

## Boundary of installation evidence

The wheel was installed with `pip --no-deps --no-index --target` outside the source
tree. This isolates project imports but reuses the host's dependency installation.
The build used the provisioned setuptools PEP 517 backend through
`scripts/build_local.py`. It is not a clean dependency-resolution build.

## Not executed / not established

- mypy, Ruff, Twine and the `build` frontend are unavailable. Package installation
  attempts failed in this runtime; the logs remain in evidence. Runtime type
  checks, annotation resolution and syntax parsing do not replace those tools.
- The GitHub Actions matrix was not run. The existing full commit pins for
  checkout v4 and setup-python v5 were rechecked through GitHub on 2026-09-17,
  but verified pins do not constitute successful CI.
- No Windows/macOS execution or Python 3.11/3.12/3.14 runtime execution occurred.
  Declared support and 3.11 parsing are narrower evidence than running them.
- No independently authorized human-data fitting, external validation, prospective
  trial, sensor hardware validation, subgroup parity study, comprehensive FHIR
  certification, regulatory assessment or independent security review occurred.
- There is no pretrained clinical artifact and no unrestricted all-day forecaster.
  Default learned artifacts operate at 20 elapsed days; other landmarks need their
  own training and evaluation.

## Reproduce

```sh
python -m pip install -c constraints-contracts.txt -e ".[dev,api]"
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

Commands list desired release checks. Only those listed as executed above are
claimed as executed. `constraints-tested.txt` records the observed dependencies,
not a universal lock file. Release evidence about ZIP integrity is also supplied
beside the handoff archive; it does not make an unexecuted clinical test pass.
