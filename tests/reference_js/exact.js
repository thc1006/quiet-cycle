import { insist, integer, compare, plain } from './errors.js';
export const SCALE = 1000000;
export function gcd(a, b) { a = a < 0n ? -a : a; b = b < 0n ? -b : b; while (b) [a, b] = [b, a % b]; return a; }
export function rational(n, d = 1n) {
  insist(typeof n === 'bigint' && typeof d === 'bigint' && d > 0n, 'fraction');
  const g = gcd(n, d); return { n: n / g, d: d / g };
}
export const plus = (a, b) => rational(a.n * b.d + b.n * a.d, a.d * b.d);
export const times = (a, b) => rational(a.n * b.n, a.d * b.d);
export const divide = (a, b) => { insist(b.n > 0n, 'divisor'); return rational(a.n * b.d, a.d * b.n); };
export const fractionJSON = a => ({ numerator: String(a.n), denominator: String(a.d) });
export function ratioPPM(n, d) { insist(n >= 0n && d > 0n && n <= d, 'ratio'); return Number(n * BigInt(SCALE) / d); }
/** Hamilton apportionment. Equal remainders break toward the earlier input index. */
export function allocate(weights, scale = SCALE) {
  integer(scale, 1, 1000000000, 'scale');
  insist(Array.isArray(weights) && weights.length > 0 && weights.length <= 10000, 'weights');
  weights.forEach(w => insist(typeof w === 'bigint' && w >= 0n, 'weight'));
  const total = weights.reduce((a, b) => a + b, 0n); insist(total > 0n, 'weights.total');
  const s = BigInt(scale), parts = weights.map((w, i) => ({ i, value: Number(w * s / total), rem: w * s % total }));
  let left = scale - parts.reduce((a, b) => a + b.value, 0);
  const ranked = parts.slice().sort((a, b) => compare(b.rem, a.rem) || a.i - b.i);
  for (let i = 0; i < left; i++) ranked[i].value++;
  return parts.map(p => p.value);
}
export function normalizeRationals(values) {
  const total = values.reduce(plus, rational(0n)); insist(total.n > 0n, 'mass.total');
  return values.map(v => divide(v, total));
}
/** Stable ASCII-key JSON. This is a project encoding, not an RFC 8785 claim. */
export function canonicalJSON(value) {
  if (value === null || typeof value === 'boolean' || typeof value === 'string') return JSON.stringify(value);
  if (typeof value === 'number') { insist(Number.isSafeInteger(value), 'canonical.number'); return JSON.stringify(value); }
  if (Array.isArray(value)) return `[${value.map(canonicalJSON).join(',')}]`;
  plain(value, 'canonical.object');
  const names = Object.keys(value).sort(compare);
  insist(names.every(k => /^[A-Za-z0-9_.-]+$/.test(k)), 'canonical.key');
  return `{${names.map(k => JSON.stringify(k) + ':' + canonicalJSON(value[k])).join(',')}}`;
}
