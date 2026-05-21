const NEW_YORK_TIME_ZONE = 'America/New_York';

const timeFormatter = new Intl.DateTimeFormat('en-US', {
  timeZone: NEW_YORK_TIME_ZONE,
  hour: 'numeric',
  minute: '2-digit',
  hour12: true,
});

const dateTimeFormatter = new Intl.DateTimeFormat('en-US', {
  timeZone: NEW_YORK_TIME_ZONE,
  month: 'short',
  day: 'numeric',
  hour: 'numeric',
  minute: '2-digit',
  hour12: true,
});

function parseDashboardDate(value?: string | Date | null): Date | null {
  if (!value) return null;
  if (value instanceof Date) {
    return Number.isNaN(value.getTime()) ? null : value;
  }

  const trimmed = value.trim();
  if (!trimmed) return null;

  const looksLikeIsoDate = /^\d{4}-\d{2}-\d{2}/.test(trimmed);
  const hasTimeZone = /(?:Z|[+-]\d{2}:?\d{2})$/.test(trimmed);
  const normalized = looksLikeIsoDate && !hasTimeZone ? `${trimmed}Z` : trimmed;
  const date = new Date(normalized);

  return Number.isNaN(date.getTime()) ? null : date;
}

export function formatNewYorkTime(value?: string | Date | null): string {
  const date = parseDashboardDate(value);
  return date ? timeFormatter.format(date) : typeof value === 'string' ? value : '—';
}

export function formatNewYorkDateTime(value?: string | Date | null): string {
  const date = parseDashboardDate(value);
  return date ? dateTimeFormatter.format(date) : typeof value === 'string' ? value : '—';
}
