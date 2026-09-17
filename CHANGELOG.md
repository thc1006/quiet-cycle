# Changelog

## 0.3.0 — 2026-09-17

- Add causal fixed-landmark construction, explicit later labels and rejected-case accounting.
- Add exact regularized residual training, held-out blending/selection and separate conformal calibration.
- Add typed JSON model artifacts, prediction explanations and held-out evaluation with abstentions.
- Add fit/forecast/evaluate CLI commands, eleven schemas and optional model-bound HTTP forecast route.
- Check direct landmark scope as well as raw pipeline scope; certify exact ridge normal equations.
- Add synthetic signal/noise/drift stress cases without claiming clinical performance.
- Put the actual implemented formulas and applicability conditions in README.
- Preserve event wire version 2.0; learning artifacts use learning-1.0.


## 0.2.0 — 2026-09-17

Replaced the website-centered JavaScript deliverable with an embeddable Python SDK.
Added typed event contracts, JSON/JSONL/CSV/records/FHIR-subset import, exact unit
normalization, versioned knowledge-time snapshots, injectable feature/predictor
protocols, JSON CLI, optional OpenAPI HTTP adapter, packaged schemas, and wheel/sdist.
Connected normalized measurements to a caller-parameterized duration research model.
Removed the frontend and browser requirement. Preserved 0.1.0 model behavior for
explicitly equivalent requests and kept its source only as a regression reference.
Contract 2.0 is not wire compatible with 1; an explicit migration adapter is included.

This is an alpha engineering handoff, not a clinical release or a PyPI publication.
