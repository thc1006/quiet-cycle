"""Select one person's latest visible revisions without rewriting history."""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256

from .errors import InputError
from .models import CycleDataset, Event, Query, Tombstone
from .serialization import canonical_json


@dataclass(frozen=True)
class Snapshot:
    events: tuple[Event, ...]
    sha256: str


def snapshot(dataset: CycleDataset, query: Query) -> Snapshot:
    groups: dict[str, dict[int, Event]] = {}
    for event in dataset.events:
        if event.subject_id != query.subject_id or event.available_at > query.cutoff:
            continue
        event_date = getattr(event, "date", getattr(event, "through", None))
        if event_date is not None and event_date > query.as_of:
            raise InputError("event_after_query_date")
        if event.kind == "no-onset" and event.through >= query.as_of:
            raise InputError("incomplete_day")
        revisions = groups.setdefault(event.id, {})
        old = revisions.get(event.revision)
        if old is not None and old != event:
            raise InputError("conflicting_revision")
        revisions[event.revision] = event
    active: list[Event] = []
    for event_id in sorted(groups):
        versions = [groups[event_id][n] for n in sorted(groups[event_id])]
        for previous, current in zip(versions, versions[1:]):
            previous_kind = previous.target_kind if isinstance(previous, Tombstone) else previous.kind
            current_kind = current.target_kind if isinstance(current, Tombstone) else current.kind
            if current_kind != previous_kind:
                raise InputError("revision_kind_change")
            if current.recorded_at < previous.recorded_at:
                raise InputError("revision_time_order")
        if not isinstance(versions[-1], Tombstone):
            active.append(versions[-1])
    # Future revisions and other people do not affect this fingerprint.
    digest = sha256(canonical_json({"events": active, "query": query}).encode("utf-8")).hexdigest()
    return Snapshot(tuple(active), digest)
