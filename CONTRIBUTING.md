# Contributing

Keep a change small enough to review with its tests. Explain the input that fails,
the expected behavior, and why the proposed data interpretation is justified.
Use synthetic records. Do not include private exports in fixtures or logs.

For a new adapter, include round-trip or equivalence tests, invalid inputs, unit
handling, missingness, source timestamps, duplicate records, and revision behavior.
An adapter must not silently infer a period start or confirmed continuity.

For a model change, provide a new model/version identity, deterministic fixtures,
probability-conservation checks, and explicit behavior outside its support. A good
score on synthetic data is not evidence of clinical accuracy. Preserve abstentions
in evaluation denominators and keep training, calibration, and test data separate.

Run `python -m pytest`, schema drift checks, type checking, lint, and installed-wheel
smoke tests. See `docs/TEST_REPORT.md` for what the handoff environment actually ran.
A failed check is not a reason to weaken validation or edit a golden file without
explaining the semantic change.

AI tools may assist, but a contribution needs an accountable reviewer. Verify API
names against primary documentation, inspect every dependency added, and run the
examples. Avoid generated prose that promises correctness without evidence. Comments
should explain constraints or non-obvious choices, not restate the following line.
Disclose substantive assistance; do not manufacture human reviewers or provenance.

Be respectful and specific in review. Disagreement about a model is a request for
evidence, not a personal judgment about patients, contributors, or their identities.
