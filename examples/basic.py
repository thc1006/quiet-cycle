"""Run from any directory after installing the package."""
from pathlib import Path

from quietcycle import CyclePipeline, Query, canonical_json
from quietcycle.adapters import load_csv
from quietcycle.serialization import loads, read_text

HERE = Path(__file__).resolve().parent

def main() -> None:
    dataset = load_csv(HERE / "events.csv")
    query = Query.model_validate(loads(read_text(HERE / "query.json")))
    result = CyclePipeline().run(dataset, query)
    print(canonical_json(result))

if __name__ == "__main__":
    main()
