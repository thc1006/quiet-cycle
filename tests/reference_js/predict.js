import { insist, integer, keys } from './errors.js';
import { addDays, dayNumber } from './dates.js';
import { allocate, SCALE, ratioPPM, fractionJSON, rational } from './exact.js';
import { snapshot, historyFromSnapshot } from './ledger.js';
export const VERSION = '0.1.0';
export const POLICY = Object.freeze({ minHistory: 3, maxHistory: 6, minLength: 10, maxLength: 180, bandwidth: 2, maxSpread: 20, minSurvivalPPM: 100000, minRemainingDays: 3 });
/** Exact integer triangular kernel. This is a heuristic model, not a fitted population prior. */
export function kernelWeights(lengths, bandwidth = 2) {
  insist(Array.isArray(lengths) && lengths.length >= 1 && lengths.length <= 100, 'lengths');
  integer(bandwidth, 0, 14, 'bandwidth');
  const out = new Map();
  for (const c of lengths) {
    integer(c, bandwidth + 1, 10000, 'length');
    for (let k = -bandwidth; k <= bandwidth; k++) out.set(c + k, (out.get(c + k) ?? 0n) + BigInt(bandwidth + 1 - Math.abs(k)));
  }
  return [...out].sort((a, b) => a[0] - b[0]).map(([day, weight]) => ({ day, weight }));
}
function quantile(rows, total, ppm) {
  let sum = 0n;
  for (const row of rows) { sum += row.weight; if (sum * BigInt(SCALE) >= total * BigInt(ppm)) return row.day; }
  return rows.at(-1).day;
}
function centralInterval(rows, total, coveragePPM) {
  const tail = (SCALE - coveragePPM) / 2;
  const lower = quantile(rows, total, tail), upper = quantile(rows, total, SCALE - tail);
  const selected = rows.filter(r => r.day >= lower && r.day <= upper).reduce((s, r) => s + r.weight, 0n);
  return { lower, upper, requestedModelMassPPM: coveragePPM, includedModelMassPPM: ratioPPM(selected, total), calibrated: false };
}
export function predict(request) {
  const events = snapshot(request), history = historyFromSnapshot(events, request.context);
  const result = { schemaVersion: 1, engineVersion: VERSION, model: 'empirical-triangle-v1', status: 'abstain',
    asOf: request.asOf, cutoff: request.cutoff, utcOffsetMinutes: request.utcOffsetMinutes, reason: null, pointDate: null, intervals: null,
    distribution: null, within3Days: null, calibration: 'not-validated', unmodeledRisk: 'not-quantified',
    audit: { historyLengths: [], intervalCount: 0, anchorDate: null, noOnsetThrough: null, survivalMass: null, unresolvedPastMass: null },
    suggestedAction: 'none' };
  const stop = (reason, action = 'none') => ({ ...result, reason, suggestedAction: action });
  if (request.context.paused) return stop('paused');
  if (request.context.mode !== 'natural-cycle') return stop('outside-declared-scope');
  if (history.conflicts) return stop('conflicting-onsets', 'review-onsets');
  const anchor = history.onsets.at(-1);
  if (!anchor) return stop('no-confirmed-onset', 'confirm-onset');
  if (anchor.certainty !== 'confirmed') return stop('uncertain-current-onset', 'confirm-onset');
  if (anchor.excludeFromHistory) return stop('current-onset-excluded');
  result.audit.anchorDate = anchor.date;
  for (const report of events.filter(e => e.kind === 'no-onset')) {
    const origin = history.onsets.find(e => e.id === report.anchorId);
    if (!origin || origin.certainty !== 'confirmed') return stop('orphan-no-onset-report', 'review-onsets');
    insist(report.through >= origin.date, 'through', 'REPORT_BEFORE_ANCHOR');
    if (history.onsets.some(e => e.date > origin.date && e.date <= report.through)) return stop('conflicting-no-onset-report', 'review-onsets');
  }
  // Reset means old intervals cannot supply pseudo-confidence for a new context.
  const recent = history.intervals.filter(i => !i.changed).slice(-POLICY.maxHistory);
  result.audit.intervalCount = recent.length;
  if (recent.length < POLICY.minHistory) return stop('insufficient-history');
  if (recent.some(i => !i.known)) return stop('unconfirmed-continuity', 'confirm-continuity');
  if (recent.some(i => i.excluded)) return stop('excluded-recent-interval');
  const lengths = recent.map(i => i.length); result.audit.historyLengths = lengths;
  if (lengths.some(c => c < POLICY.minLength || c > POLICY.maxLength)) return stop('outside-model-support');
  if (Math.max(...lengths) - Math.min(...lengths) > POLICY.maxSpread) return stop('high-observed-variation');
  const all = kernelWeights(lengths, POLICY.bandwidth);
  if (dayNumber(anchor.date) + all.at(-1).day > dayNumber('2200-12-31')) return stop('date-domain-limit');
  const original = all.reduce((s, r) => s + r.weight, 0n);
  const reports = events.filter(e => e.kind === 'no-onset' && e.anchorId === anchor.id);
  for (const e of reports) insist(e.through >= anchor.date, 'through', 'REPORT_BEFORE_ANCHOR');
  const through = reports.length ? reports.map(e => e.through).sort().at(-1) : anchor.date;
  result.audit.noOnsetThrough = reports.length ? through : null;
  const elapsedConfirmed = dayNumber(through) - dayNumber(anchor.date);
  const remaining = all.filter(r => r.day > elapsedConfirmed), total = remaining.reduce((s, r) => s + r.weight, 0n);
  result.audit.survivalMass = fractionJSON(rational(total, original));
  if (total === 0n) return stop('support-exhausted', 'review-onsets');
  const currentDay = dayNumber(request.asOf) - dayNumber(anchor.date);
  const past = remaining.filter(r => r.day < currentDay).reduce((s, r) => s + r.weight, 0n);
  result.audit.unresolvedPastMass = fractionJSON(rational(past, total));
  if (past > 0n) return stop('onset-status-unconfirmed', 'confirm-completed-days');
  if (total * BigInt(SCALE) < original * BigInt(POLICY.minSurvivalPPM) || remaining.length < POLICY.minRemainingDays) return stop('weak-remaining-support', 'review-onsets');
  const median = quantile(remaining, total, 500000);
  // PMF quantization is presentation only; decisions and quantiles use exact weights.
  const ppm = allocate(remaining.map(r => r.weight));
  const distribution = remaining.map((r, i) => ({ date: addDays(anchor.date, r.day), length: r.day, mass: fractionJSON(rational(r.weight, total)), ppm: ppm[i] }));
  const intervals = [800000, 900000].map(target => {
    const x = centralInterval(remaining, total, target);
    return { from: addDays(anchor.date, x.lower), to: addDays(anchor.date, x.upper),
      requestedModelMassPPM: x.requestedModelMassPPM, includedModelMassPPM: x.includedModelMassPPM, calibrated: false };
  });
  const near = remaining.filter(r => r.day >= currentDay && r.day < currentDay + 3).reduce((s, r) => s + r.weight, 0n);
  return { ...result, status: 'estimate', reason: 'historical-model-only', pointDate: addDays(anchor.date, median), intervals, distribution,
    within3Days: { from: request.asOf, through: addDays(request.asOf, 2), modelMass: fractionJSON(rational(near, total)), ppm: ratioPPM(near, total), calibrated: false } };
}
