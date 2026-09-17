/** Error messages name fields, never echo health values. */
export class InputError extends Error {
  constructor(code, field) {
    super(`${code}: ${field}`);
    this.name = 'InputError'; this.code = code; this.field = field;
  }
}
export function insist(condition, field, code = 'INVALID_INPUT') {
  if (!condition) throw new InputError(code, field);
}
export function integer(value, min, max, field) {
  insist(Number.isSafeInteger(value) && value >= min && value <= max, field);
  return value;
}
export function plain(value, field) {
  insist(value !== null && typeof value === 'object' && !Array.isArray(value)
    && [Object.prototype, null].includes(Object.getPrototypeOf(value)), field);
}
export function keys(value, allowed, required, field) {
  plain(value, field);
  insist(Object.keys(value).every(k => allowed.includes(k))
    && required.every(k => Object.hasOwn(value, k)), field);
}
export function choice(value, options, field) { insist(options.includes(value), field); }
export function identifier(value, field) {
  insist(typeof value === 'string' && /^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$/.test(value), field);
}
export function compare(a, b) { return a < b ? -1 : a > b ? 1 : 0; }
