/**
 * Display formatting.
 *
 * Money is formatted with Intl using the store's currency; the fallback is a
 * plain grouped number rather than a wrong currency symbol.
 */

let currencyCode = 'INR';

export function setCurrency(code) {
  if (code) currencyCode = code;
}

const numberFormat = new Intl.NumberFormat('en-IN');

export function currency(value, { compact = false } = {}) {
  const amount = Number(value ?? 0);
  if (!Number.isFinite(amount)) return '—';
  try {
    return new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency: currencyCode,
      maximumFractionDigits: compact && Math.abs(amount) >= 1000 ? 0 : 2,
      minimumFractionDigits: compact && Math.abs(amount) >= 1000 ? 0 : 2,
      notation: compact && Math.abs(amount) >= 100000 ? 'compact' : 'standard',
    }).format(amount);
  } catch {
    return numberFormat.format(amount);
  }
}

export function number(value) {
  const amount = Number(value ?? 0);
  return Number.isFinite(amount) ? numberFormat.format(amount) : '—';
}

export function decimal(value, places = 1) {
  const amount = Number(value ?? 0);
  return Number.isFinite(amount) ? amount.toFixed(places) : '—';
}

/** A percentage, or an em dash when it is genuinely undefined rather than zero. */
export function percent(value, places = 1) {
  if (value === null || value === undefined) return '—';
  const amount = Number(value);
  return Number.isFinite(amount) ? `${amount.toFixed(places)}%` : '—';
}

export function date(value, options = {}) {
  if (!value) return '—';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return '—';
  return parsed.toLocaleDateString('en-IN', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    ...options,
  });
}

export function dateTime(value) {
  if (!value) return '—';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return '—';
  return parsed.toLocaleString('en-IN', {
    day: 'numeric',
    month: 'short',
    hour: 'numeric',
    minute: '2-digit',
  });
}

export function time(value) {
  if (!value) return '—';
  return new Date(value).toLocaleTimeString('en-IN', { hour: 'numeric', minute: '2-digit' });
}

export function relativeTime(value) {
  if (!value) return '—';
  const then = new Date(value).getTime();
  if (Number.isNaN(then)) return '—';

  const seconds = Math.round((Date.now() - then) / 1000);
  if (seconds < 60) return 'just now';

  const units = [
    ['minute', 60],
    ['hour', 60],
    ['day', 24],
    ['month', 30],
    ['year', 12],
  ];

  let amount = seconds / 60;
  let unit = 'minute';
  for (let index = 0; index < units.length - 1; index += 1) {
    if (amount < units[index + 1][1]) {
      unit = units[index][0];
      break;
    }
    amount /= units[index + 1][1];
    unit = units[index + 1][0];
  }

  const rounded = Math.round(amount);
  return `${rounded} ${unit}${rounded === 1 ? '' : 's'} ago`;
}

/** Today's date as YYYY-MM-DD in local time, for date inputs. */
export function today() {
  const now = new Date();
  const offset = now.getTimezoneOffset() * 60000;
  return new Date(now.getTime() - offset).toISOString().slice(0, 10);
}

export function initials(name) {
  if (!name) return '?';
  return name
    .trim()
    .split(/\s+/)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() || '')
    .join('');
}

export function titleCase(value) {
  if (!value) return '';
  return value
    .toString()
    .replace(/_/g, ' ')
    .toLowerCase()
    .replace(/\b\w/g, (character) => character.toUpperCase());
}
