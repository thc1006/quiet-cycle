import { keys, insist, integer, choice, identifier, compare } from './errors.js';
import { dayNumber, instant, localDay } from './dates.js';
export const SYMPTOMS = Object.freeze(['headache', 'fatigue', 'sleep', 'abdomen', 'gut', 'mood', 'focus', 'other']);
const envelope = ['id', 'revision', 'kind', 'recordedAt', 'utcOffsetMinutes', 'deleted'];
const fields = {
  onset: ['date', 'certainty', 'previousOnsetId', 'continuity', 'excludeFromHistory'],
  'no-onset': ['anchorId', 'through'],
  symptom: ['date', 'symptom', 'state', 'impact'],
  checkin: ['date', 'state']
};
function validateEvent(e, asOf) {
  const allowed = [...envelope, ...fields[e.kind]];
  keys(e, allowed, [...envelope, ...(e.deleted ? [] : fields[e.kind])], 'event');
  insist(typeof e.deleted === 'boolean', 'event.deleted');
  if (e.deleted) return;
  const reported = localDay(e.recordedAt, e.utcOffsetMinutes);
  const eventDate = e.kind === 'no-onset' ? e.through : e.date;
  dayNumber(eventDate); insist(eventDate <= reported && eventDate <= asOf, 'event.date', 'FUTURE_OBSERVATION');
  if (e.kind === 'onset') {
    choice(e.certainty, ['confirmed', 'uncertain'], 'certainty');
    choice(e.continuity, ['confirmed', 'unknown'], 'continuity');
    if (e.previousOnsetId !== null) identifier(e.previousOnsetId, 'previousOnsetId');
    insist(e.previousOnsetId !== e.id, 'previousOnsetId');
    insist(typeof e.excludeFromHistory === 'boolean', 'excludeFromHistory');
  } else if (e.kind === 'no-onset') {
    identifier(e.anchorId, 'anchorId');
    // A day still in progress cannot be censored as a whole day without an intraday model.
    insist(e.through < reported && e.through < asOf, 'through', 'INCOMPLETE_DAY');
  } else if (e.kind === 'symptom') {
    choice(e.symptom, SYMPTOMS, 'symptom');
    choice(e.state, ['present', 'absent', 'uncertain', 'skipped'], 'state');
    insist(e.impact === null || (Number.isInteger(e.impact) && e.impact >= 0 && e.impact <= 3), 'impact');
    insist(e.state === 'present' || e.impact === null, 'impact', 'INCONSISTENT_IMPACT');
  } else {
    choice(e.state, ['marked', 'none', 'uncertain', 'skipped'], 'checkin.state');
  }
}
/** Materialize only what was recorded by cutoff. Do not mutate an append-only ledger. */
export function snapshot(request) {
  keys(request, ['schemaVersion', 'asOf', 'cutoff', 'utcOffsetMinutes', 'context', 'events'],
    ['schemaVersion', 'asOf', 'cutoff', 'utcOffsetMinutes', 'context', 'events'], 'request');
  insist(request.schemaVersion === 1, 'schemaVersion'); dayNumber(request.asOf);
  const cutoff = instant(request.cutoff);
  insist(localDay(request.cutoff, request.utcOffsetMinutes) === request.asOf, 'asOf', 'CUTOFF_DAY_MISMATCH');
  keys(request.context, ['mode', 'changedSince', 'paused'], ['mode', 'changedSince', 'paused'], 'context');
  choice(request.context.mode, ['natural-cycle', 'other', 'unknown'], 'context.mode');
  insist(typeof request.context.paused === 'boolean', 'context.paused');
  if (request.context.changedSince !== null) { dayNumber(request.context.changedSince); insist(request.context.changedSince <= request.asOf, 'context.changedSince'); }
  insist(Array.isArray(request.events) && request.events.length <= 5000, 'events');
  const groups = new Map();
  for (const e of request.events) {
    // Future payloads never influence a replay. Their envelope still must be parseable.
    insist(e !== null && typeof e === 'object', 'event');
    identifier(e.id, 'event.id'); integer(e.revision, 1, 100000, 'event.revision');
    const at = instant(e.recordedAt);
    if (at > cutoff) continue;
    choice(e.kind, Object.keys(fields), 'event.kind'); integer(e.utcOffsetMinutes, -840, 840, 'event.utcOffsetMinutes');
    validateEvent(e, request.asOf);
    const group = groups.get(e.id) ?? []; group.push(e); groups.set(e.id, group);
  }
  const active = [];
  for (const group of groups.values()) {
    group.sort((a, b) => a.revision - b.revision);
    for (let i = 1; i < group.length; i++) {
      insist(group[i].revision !== group[i - 1].revision, 'event.revision', 'DUPLICATE_REVISION');
      insist(group[i].recordedAt >= group[i - 1].recordedAt, 'event.recordedAt', 'REVISION_TIME_ORDER');
      insist(group[i].kind === group[i - 1].kind, 'event.kind', 'REVISION_KIND_CHANGE');
    }
    if (!group.at(-1).deleted) active.push({ ...group.at(-1) });
  }
  active.sort((a, b) => compare(a.id, b.id));
  return active;
}
export function historyFromSnapshot(events, context) {
  const onsets = events.filter(e => e.kind === 'onset').sort((a, b) => compare(a.date, b.date) || compare(a.id, b.id));
  const conflicts = onsets.some((e, i) => i > 0 && e.date === onsets[i - 1].date);
  const intervals = [];
  for (let i = 1; i < onsets.length; i++) {
    const a = onsets[i - 1], b = onsets[i];
    const known = a.certainty === 'confirmed' && b.certainty === 'confirmed'
      && b.previousOnsetId === a.id && b.continuity === 'confirmed';
    intervals.push({ start: a.date, end: b.date, length: dayNumber(b.date) - dayNumber(a.date),
      known, excluded: a.excludeFromHistory || b.excludeFromHistory,
      changed: context.changedSince !== null && a.date < context.changedSince,
      acquiredAt: a.recordedAt > b.recordedAt ? a.recordedAt : b.recordedAt });
  }
  return { onsets, intervals, conflicts };
}
