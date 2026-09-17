# Test report — 0.2.0

Audited on 2026-09-17. This report covers software behavior on Linux with Python
3.13.5 and Node.js 22.16.0. Examples and generated records are synthetic. No clinical
accuracy, contraceptive effectiveness, or clinical safety was evaluated.

## Executed

| Check | Result | Evidence |
| --- | --- | --- |
| Complete pytest suite | 127 passed; no skips or failures | `evidence/pytest.log`, `pytest.xml` |
| Statement/branch coverage combined | 87.55% | `evidence/coverage.json` |
| Legacy JS/Python comparison | 300 generated requests agree on the compared forecast fields | `tests/test_reference.py` |
| Integer kernel and ppm allocation | 1,400 generated cases | `tests/test_reference.py` |
| Independent duration oracle | 200 exact countdown-state models agree | `tests/test_research.py` |
| Selected mutation regressions | 8 of 8 mutations detected after a test correction | `evidence/mutations.json` |
| Installed wheel checks | 18 passed, including actual localhost HTTP and Node-to-Python calls | `evidence/artifact-smoke.json` |
| Wire contracts | Six packaged JSON Schemas and one OpenAPI document reproduce | `evidence/contracts.json` |
| Repository checks | Public exports, runtime type hints, Python 3.11 syntax, local documentation links | `evidence/repository-check.json` |

The property/oracle cases are loops within the pytest tests, not additional users
or clinical observations. Legacy parity covers the documented shared baseline,
not all version-1 validation rules. The reference implementation is frozen test
material, not a second production engine.

Coverage includes 1,383 statements and 488 branches. It is not 100%; subprocess
entry points are also exercised by installed-artifact checks without merging their
coverage. Coverage measures exercised code, not the absence of defects.

## A test gap found during review

The first selected-mutation run detected 7 of 8 changes. The Fahrenheit scale
mutation survived because that target's parametrized unit cases covered Kelvin
and Celsius but not Fahrenheit. Explicit 98.6 F -> 37 C and 32 F -> 0 C cases were
added, then the complete suite and the mutation set were rerun. The original
result remains in `evidence/mutations-before.json`. This is targeted mutation
testing, not an exhaustive mutation score.

## Installed-artifact boundary

The wheel was installed with `pip --no-deps --no-index --target` into a temporary
location outside the checkout. Imports, packaged schemas, CLI output, five Python
examples, a Node JSON caller, and a real Uvicorn loopback request were exercised.
The SDK, CLI, and HTTP results agree with the committed synthetic result.

This isolates the installed project from its source tree, but reuses the host's
dependencies. It is **not** a clean-environment dependency-resolution test.
Wheel RECORD hashes and source-distribution paths were checked. The distribution
was built by invoking the provisioned setuptools PEP 517 backend directly via
`scripts/build_local.py`, not by pretending that an unavailable build frontend ran.

## Not executed here

- mypy, Ruff, Twine, and the `build` frontend were unavailable. Package-download
  attempts failed because the runtime could not resolve the package host.
  Runtime type validation, exported annotations and `py.typed` were checked; these
  do not substitute for a static type checker.
- The configured GitHub Actions matrix was not run: Windows, macOS, and Python
  3.11/3.12/3.14 execution remain to be verified. Syntax compatibility is narrower
  evidence than running those interpreters.
- No complete clean-environment dependency resolution, general FHIR conformance
  validator, clinical dataset benchmark, independent security audit, or public
  deployment was performed.
- The optional HTTP adapter is unauthenticated. Local HTTP success does not make it
  a production-ready health-data service.

No browser or frontend tests are required by this repository: it contains neither
a web application nor browser runtime code. A service consumer must validate its
own interface, authentication, database behavior, and privacy controls.

## Reproduce

```sh
python -m pip install -c constraints-contracts.txt -e ".[dev,api]"
python -m pytest --cov=quietcycle --cov-report=term
python scripts/generate_contracts.py --check
python scripts/check_repository.py
python scripts/run_mutations.py
python -m mypy src/quietcycle
python -m ruff check src tests examples scripts
python -m build
python scripts/check_artifacts.py
```

These are the intended checks, not a claim that every command above ran here.
See `evidence/environment.json` for the versions actually available. A public
release should complete the unexecuted checks before making wider compatibility
claims.
