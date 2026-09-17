"""Default feature construction. No filling missing days or inferring onset from sensors."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .dates import day_difference, local_day
from .ledger import Snapshot
from .models import (
    Event, Measurement, NoOnset, NormalizedMeasurement, Onset,
    Query, Symptom, SymptomCounts,
)
from .units import UnitRegistry


@dataclass(frozen=True)
class Interval:
    start: str
    end: str
    length: int
    known: bool
    excluded: bool
    changed: bool


@dataclass(frozen=True)
class Features:
    events: tuple[Event, ...]
    onsets: tuple[Onset, ...]
    intervals: tuple[Interval, ...]
    no_onset: tuple[NoOnset, ...]
    conflicting_onsets: bool
    measurements: tuple[NormalizedMeasurement, ...]
    symptoms: tuple[SymptomCounts, ...]
    snapshot_sha256: str


class FeatureBuilder(Protocol):
    builder_id: str

    def build(self, selected: Snapshot, query: Query) -> Features: ...


def symptom_counts(events: tuple[Event, ...]) -> tuple[SymptomCounts, ...]:
    groups: dict[str, dict[str, list[Symptom]]] = {}
    for event in events:
        if isinstance(event, Symptom):
            groups.setdefault(event.symptom, {}).setdefault(event.date, []).append(event)
    results = []
    for name, days in sorted(groups.items()):
        counts = {"present": 0, "absent": 0, "uncertain": 0, "skipped": 0}
        conflicts = recalled = 0
        for reports in days.values():
            states = {report.state for report in reports}
            impacts = {report.impact for report in reports if report.state == "present"}
            recalled += sum(report.date < local_day(report.recorded_at, report.utc_offset_minutes) for report in reports)
            if len(states) != 1 or len(impacts) > 1:
                conflicts += 1
            else:
                counts[reports[0].state] += 1
        results.append(SymptomCounts(symptom=name, conflicting_days=conflicts,
                                     recalled_reports=recalled, **counts))
    return tuple(results)


class DefaultFeatureBuilder:
    builder_id = "default-features-v1"

    def __init__(self, registry: UnitRegistry | None = None) -> None:
        self.registry = registry if registry is not None else UnitRegistry()
        self.builder_id = "default-features-v1-" + self.registry.signature[:16]

    def build(self, selected: Snapshot, query: Query) -> Features:
        onsets = tuple(sorted((e for e in selected.events if isinstance(e, Onset)),
                              key=lambda e: (e.date, e.id)))
        conflicting = any(a.date == b.date for a, b in zip(onsets, onsets[1:]))
        intervals = []
        for a, b in zip(onsets, onsets[1:]):
            known = (a.certainty == b.certainty == "confirmed" and
                     b.previous_onset_id == a.id and b.continuity == "confirmed")
            intervals.append(Interval(
                start=a.date, end=b.date, length=day_difference(b.date, a.date), known=known,
                excluded=a.exclude_from_history or b.exclude_from_history,
                changed=query.context.changed_since is not None and a.date < query.context.changed_since,
            ))
        measurements = tuple(self.registry.normalize(e) for e in selected.events if isinstance(e, Measurement))
        return Features(
            events=selected.events, onsets=onsets, intervals=tuple(intervals),
            no_onset=tuple(e for e in selected.events if isinstance(e, NoOnset)),
            conflicting_onsets=conflicting, measurements=measurements,
            symptoms=symptom_counts(selected.events), snapshot_sha256=selected.sha256,
        )
