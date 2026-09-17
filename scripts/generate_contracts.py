"""Regenerate contracts; --check detects drift without rewriting tracked files."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from quietcycle import CycleDataset, PipelineRequest, PipelineResult, Query
from quietcycle.api import create_app
from quietcycle.research import DurationModel, DurationResult
from quietcycle.learning import Landmark, LabelledCase, FitRequest, FittedModel, LearnedPrediction

ROOT = Path(__file__).resolve().parents[1]
MODELS = {"dataset": CycleDataset, "query": Query, "request": PipelineRequest, "result": PipelineResult,
          "duration-model": DurationModel, "duration-result": DurationResult,
          "landmark": Landmark, "labelled-case": LabelledCase, "fit-request": FitRequest,
          "fitted-model": FittedModel, "learned-prediction": LearnedPrediction}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    documents = {}
    for name, model in MODELS.items():
        schema = model.model_json_schema()
        schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
        version = "learning-1.0" if name in {"landmark", "labelled-case", "fit-request", "fitted-model", "learned-prediction"} else "2.0"
        schema["$id"] = uuid5(NAMESPACE_URL, f"quiet-cycle/contract/{version}/{name}").urn
        documents[ROOT / "src" / "quietcycle" / "schemas" / f"{name}.schema.json"] = schema
    documents[ROOT / "contracts" / "openapi.json"] = create_app().openapi()
    for path, value in documents.items():
        text = json.dumps(value, ensure_ascii=True, indent=2, sort_keys=True) + "\n"
        if args.check:
            if not path.exists() or path.read_text() != text:
                raise SystemExit(f"Contract drift: {path.relative_to(ROOT)}")
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
    print(f"{len(documents)} contracts checked" if args.check else f"{len(documents)} contracts generated")


if __name__ == "__main__":
    main()
