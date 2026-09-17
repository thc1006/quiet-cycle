"""Merge an explicitly mapped scalar FHIR measurement with a separate onset ledger."""
from pathlib import Path

from quietcycle import CyclePipeline, Query
from quietcycle.adapters import FHIRObservationAdapter, load_json
from quietcycle.serialization import loads, read_text


def main() -> None:
    here = Path(__file__).resolve().parent
    adapter = FHIRObservationAdapter(subject_map={"Patient/example": "demo"},
        imported_at="2025-07-02T12:00:00Z", utc_offset_minutes=0)
    data = load_json(here / "dataset.json").merge(adapter.load(here / "fhir-observation.json"))
    query = Query.model_validate(loads(read_text(here / "query.json")))
    result = CyclePipeline().run(data, query)
    measurement = result.measurements[0]
    print(measurement.metric, measurement.value.as_fraction(), measurement.unit)
    print(result.forecast.point_date)  # Measurements do not affect the default baseline.

if __name__ == "__main__":
    main()
