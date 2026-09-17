"""Run: python examples/train_multifactor.py --output /path/to/private-directory"""
from __future__ import annotations

import argparse
from pathlib import Path

from quietcycle.learning import MultiFactorPipeline, evaluate, fit
from quietcycle.serialization import canonical_json, write_private

from synthetic_cohort import cohort


def main() -> None:
    parser = argparse.ArgumentParser(description="Synthetic training smoke test; not a clinical model")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    request, test, inputs, rejected = cohort()
    model = fit(request)
    result = MultiFactorPipeline(model).run(*inputs[0])
    report = evaluate(model, test)
    for name, value in (("fit-request.json", request), ("model.json", model), ("prediction.json", result),
                        ("test-cases.json", test), ("evaluation.json", report)):
        write_private(args.output / name, canonical_json(value))
    write_private(args.output / "request.json", canonical_json({"dataset": inputs[0][0], "query": inputs[0][1]}))
    print(canonical_json({"selected": model.selected.name, "test": report, "rejected_cases": rejected}))


if __name__ == "__main__":
    main()
