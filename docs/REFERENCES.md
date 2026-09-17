> For the 0.3.0 research update and implementation mapping, see [EVIDENCE_REVIEW.md](EVIDENCE_REVIEW.md).

# References and design decisions

Consulted for this handoff, 2026-09-17. Standards references define interfaces,
not evidence that the predictor is clinically useful. Some background research was
identified in the earlier discussion; no clinical dataset was used in this build.

## 1. RocketPy pyproject and API design

https://github.com/RocketPy-Team/RocketPy/blob/master/pyproject.toml

Inspected through the GitHub connector: an importable Python distribution with optional extras and explicit metadata. We did not copy rocket simulation code.

## 2. Scientific Python development guide

https://learn.scientific-python.org/development/

Scientific-library structure, testing and packaging; not an endorsement of this package.

## 3. Scientific Python API design

https://learn.scientific-python.org/development/principles/design/

Prefer small composable interfaces and interoperability over application-specific scaffolding.

## 4. pyOpenSci package guide

https://www.pyopensci.org/python-package-guide/

Scientific-package maintainability and review practices. This project has not undergone pyOpenSci peer review.

## 5. PyPA packaging tutorial

https://packaging.python.org/en/latest/tutorials/packaging-projects/

Standard pyproject metadata, PEP 517 backend, wheel and sdist. Consulted page showed a 2026-09-09 update.

## 6. PyPA src layout

https://packaging.python.org/en/latest/discussions/src-layout-vs-flat-layout/

Use src layout and verify the installed distribution rather than accidentally importing from the working tree.

## 7. PyPA plugin guide

https://packaging.python.org/en/latest/guides/creating-and-discovering-plugins/

Entry points are one discovery option. This library intentionally uses explicit injection, not auto-discovery.

## 8. Python typing distribution specification

https://typing.python.org/en/latest/spec/distributing.html

Ship py.typed and inline type information. A marker alone does not prove a type checker passes.

## 9. Pydantic strict mode

https://docs.pydantic.dev/latest/concepts/strict_mode/

Reject coercion at the public boundary. Custom BeforeValidators only normalize list-to-tuple transport shape.

## 10. Pydantic JSON Schema generation

https://docs.pydantic.dev/latest/api/json_schema/

Generate wire shape from the source models; semantic ledger invariants still require runtime checks.

## 11. JSON Schema 2020-12

https://json-schema.org/draft/2020-12

The package schema dialect. It is not a standard menstrual-health ontology.

## 12. OpenAPI 3.1.1 specification

https://spec.openapis.org/oas/v3.1.1.html

OpenAPI 3.1 contract family for the optional service. Generated document declares 3.1.0, not latest-version support.

## 13. FHIR R4 Observation

https://hl7.org/fhir/R4/observation.html

Scalar quantity, effective time, issued time, subject, status and missing-data semantics. Adapter is a documented subset, not full FHIR validation.

## 14. UCUM specification

https://ucum.org/ucum

Explicit unit codes and exact conversions; no complete UCUM expression parser is supplied.

## 15. pytest good integration practices

https://docs.pytest.org/en/stable/explanation/goodpractices.html

src layout, importlib test mode and installed-package checks.

## 16. GitHub citation files

https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-citation-files

CITATION.cff metadata without fabricated DOI, author credentials or repository URL.

## 17. Google developer documentation tone

https://developers.google.com/style/tone

Use direct language and explain the task; no sales language or claims of effortless universal interoperability.

## 18. Google technical writing: clear sentences

https://developers.google.com/tech-writing/one/clear-sentences

Use specific subjects and verbs, short task-focused instructions.

## 19. Google technical writing: advanced summary

https://developers.google.com/tech-writing/course-summaries/two

Comments explain non-obvious choices; examples should work and show useful counterexamples.

## 20. Security weaknesses in generated code: empirical study

https://arxiv.org/abs/2310.02059

Primary research motivating independent checks rather than trusting generated code. Its sampled prevalence is not a risk estimate for this repo.

## 21. Claude Code best practices

https://code.claude.com/docs/en/best-practices

Short project instructions, concrete verification commands, and separate review tasks; not a claim of autonomous correctness.

## 22. Cycle prediction with tracking adherence

https://academic.oup.com/jamia/article/29/1/3/6371799

Background for separating observed reports from unobserved cycles. This package does not reproduce its trained model.

## 23. Calibrated menstrual-cycle predictive uncertainty

https://proceedings.mlr.press/v149/urteaga21a.html

Background on probabilistic forecast evaluation. Exact arithmetic does not provide empirical calibration.

## 24. mcPHASES dataset description

https://www.nature.com/articles/s41597-026-06805-3

Potential future multimodal research; no dataset is bundled, downloaded, or used to claim validation.

