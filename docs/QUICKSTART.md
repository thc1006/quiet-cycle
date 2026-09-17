> This page starts with the retained historical baseline. For fitted multifactor training, see [TRAINING.md](TRAINING.md) and the root README.

# Quick start

## Install an artifact or checkout

From the repository root: `python -m pip install .`.
For the included wheel: `python -m pip install dist/quiet_cycle-0.3.0-py3-none-any.whl`.
Both routes resolve Pydantic if it is not installed. An offline environment needs
the appropriate dependency wheels; the repository does not bundle them.

The package import is `quietcycle`; the distribution/CLI name is `quiet-cycle`.
Install `.[api]` only when using the HTTP adapter. Install `.[dev,api]` to run the
complete development suite. Scientific arrays and dataframes are not runtime dependencies.

## Python

Run `python examples/basic.py` from the repository root after installation.
`examples/from_rows.py` builds a typed dataset without any file importer.
`examples/custom_predictor.py` replaces the predictor while keeping all data checks.
`examples/research_pipeline.py` connects a normalized measurement to a synthetic
state model using a caller-provided rule.

`CyclePipeline.run_many(dataset, queries)` processes a fixed dataset for multiple
queries in caller order. Each query selects exactly one local subject identifier.
An error stops the call; batch execution is not a transactional database operation.
For independent failure handling, call `run()` in your own loop.

## CLI

```sh
quiet-cycle predict examples/request.json
quiet-cycle run examples/events.csv --format csv --query examples/query.json
quiet-cycle import examples/events.jsonl --format jsonl --output normalized.json
quiet-cycle validate examples/request.json
quiet-cycle schema dataset
```

Use `-` as the input path for stdin. No shell expansion or network URLs are accepted
as input sources by the SDK. `validate` checks the typed contract and runs the
pipeline: a valid abstention is valid input, not an error.

Output files are atomically replaced, with 0600 permissions on Unix. On Windows,
set suitable ACLs in the calling application. Stdout may be captured by your shell,
CI system, notebook, or calling service; it is not private storage.

## Outcome versus error

`forecast.status == "abstain"` is a usable result explaining why this model cannot
estimate. `InputError` means the input or declared data relationship is invalid.
The CLI uses exit code 0 for either a forecast or abstention, and 2 for input errors.
Never replace an error or abstention with an invented date.
