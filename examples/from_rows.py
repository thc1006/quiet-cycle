"""An upstream application explicitly attests to the three consecutive intervals."""
from quietcycle import CycleContext, CycleDataset, CyclePipeline, Onset, Query


def main() -> None:
    days = ("2025-01-01", "2025-01-29", "2025-02-26", "2025-03-26")
    events = tuple(Onset(
        subject_id="synthetic", id=f"start-{i}", date=day, certainty="confirmed",
        recorded_at=day + "T12:00:00Z", utc_offset_minutes=0,
        previous_onset_id=None if i == 0 else f"start-{i - 1}",
        continuity="unknown" if i == 0 else "confirmed",
    ) for i, day in enumerate(days))
    query = Query(subject_id="synthetic", as_of="2025-04-01",
        cutoff="2025-04-01T12:00:00Z", utc_offset_minutes=0,
        context=CycleContext(mode="natural-cycle"))
    result = CyclePipeline().run(CycleDataset(events=events), query)
    print(result.forecast.status, result.forecast.point_date)

if __name__ == "__main__":
    main()
