/** Calendar date in the user's local timezone (YYYY-MM-DD). */
export function formatLocalDate(d: Date): string {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

const HAS_TIMEZONE_SUFFIX = /[zZ]$|[+-]\d{2}:\d{2}$/

/**
 * Parse datetimes from the API. Backend stores UTC but often serializes without a `Z` suffix;
 * treat those naive ISO strings as UTC so local display is correct (e.g. CST = UTC+8).
 */
export function parseApiDateTime(value: string): Date {
  const trimmed = value.trim()
  if (!trimmed) return new Date(NaN)
  if (/^\d{4}-\d{2}-\d{2}$/.test(trimmed)) {
    return new Date(`${trimmed}T00:00:00`)
  }
  if (HAS_TIMEZONE_SUFFIX.test(trimmed)) {
    return new Date(trimmed)
  }
  return new Date(`${trimmed}Z`)
}

export function formatApiDateTime(value: string | undefined | null): string {
  if (!value) return ''
  const d = parseApiDateTime(value)
  if (Number.isNaN(d.getTime())) return value
  return d.toLocaleString('zh-CN', { hour12: false })
}
