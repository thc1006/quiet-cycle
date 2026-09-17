import { insist, integer } from './errors.js';
const lengths = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
const leap = y => y % 4 === 0 && (y % 100 !== 0 || y % 400 === 0);
const beforeYear = y => 365 * (y - 1) + Math.floor((y - 1) / 4) - Math.floor((y - 1) / 100) + Math.floor((y - 1) / 400);
const epoch = beforeYear(1970);
/** A civil date is not a timestamp. No host locale, time zone, Date.parse or clock. */
export function dayNumber(value) {
  insist(typeof value === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(value), 'date');
  const [y, m, d] = value.split('-').map(Number);
  integer(y, 1900, 2200, 'date.year'); integer(m, 1, 12, 'date.month');
  integer(d, 1, lengths[m - 1] + (m === 2 && leap(y) ? 1 : 0), 'date.day');
  return beforeYear(y) - epoch + lengths.slice(0, m - 1).reduce((a, b) => a + b, 0)
    + (m > 2 && leap(y) ? 1 : 0) + d - 1;
}
export function dateFromDay(n) {
  integer(n, dayNumber('1900-01-01'), dayNumber('2200-12-31'), 'dayNumber');
  let y = 1900;
  while (y < 2200 && beforeYear(y + 1) - epoch <= n) y++;
  let remaining = n - (beforeYear(y) - epoch), m = 1;
  while (remaining >= lengths[m - 1] + (m === 2 && leap(y) ? 1 : 0)) {
    remaining -= lengths[m - 1] + (m === 2 && leap(y) ? 1 : 0); m++;
  }
  return `${y}-${String(m).padStart(2, '0')}-${String(remaining + 1).padStart(2, '0')}`;
}
export function addDays(date, days) { integer(days, -200000, 200000, 'days'); return dateFromDay(dayNumber(date) + days); }
/** Canonical UTC timestamps only. Leap seconds and offset spellings are rejected. */
export function instant(value) {
  insist(typeof value === 'string' && /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/.test(value), 'recordedAt');
  const day = dayNumber(value.slice(0, 10));
  const h = integer(Number(value.slice(11, 13)), 0, 23, 'instant.hour');
  const m = integer(Number(value.slice(14, 16)), 0, 59, 'instant.minute');
  const s = integer(Number(value.slice(17, 19)), 0, 59, 'instant.second');
  return day * 86400000 + h * 3600000 + m * 60000 + s * 1000 + Number(value.slice(20, 23));
}
export function localDay(timestamp, offsetMinutes) {
  integer(offsetMinutes, -840, 840, 'utcOffsetMinutes');
  return dateFromDay(Math.floor((instant(timestamp) + offsetMinutes * 60000) / 86400000));
}
