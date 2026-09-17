"""Replace the predictor while preserving the typed pipeline and output checks."""
from pathlib import Path

from quietcycle import CyclePipeline, EmpiricalPredictor, Features, Forecast, Policy, Query
from quietcycle.adapters import load_json
from quietcycle.serialization import loads, read_text


class LocalBaseline:
    model_id = "example-local-baseline"
    used_features = ("onset", "no-onset", "context")

    def __init__(self) -> None:
        self.inner = EmpiricalPredictor(Policy(min_history=4, max_history=8))
        self.model_version = self.inner.model_version

    def predict(self, features: Features, query: Query) -> Forecast:
        result = self.inner.predict(features, query)
        # CyclePipeline revalidates even results produced using model_copy.
        return result.model_copy(update={"model_id": self.model_id})


def main() -> None:
    here = Path(__file__).resolve().parent
    query = Query.model_validate(loads(read_text(here / "query.json")))
    result = CyclePipeline(predictor=LocalBaseline()).run(load_json(here / "dataset.json"), query)
    print(result.forecast.model_id, result.forecast.status, result.forecast.point_date)

if __name__ == "__main__":
    main()
