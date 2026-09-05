/** Formatting helpers. Money arrives as a string, so no cent is lost. */

export function formatMoney(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === '') return '—'
  const amount = typeof value === 'number' ? value : Number.parseFloat(value)
  if (Number.isNaN(amount)) return '—'
  return `$${amount.toLocaleString('en-AU', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '—'
  return date.toLocaleDateString('en-AU', { day: 'numeric', month: 'short', year: 'numeric' })
}

export function relativeTime(value: string | null | undefined): string {
  if (!value) return 'never'
  const then = new Date(value).getTime()
  if (Number.isNaN(then)) return 'never'
  const seconds = Math.round((Date.now() - then) / 1000)
  if (seconds < 60) return 'just now'
  if (seconds < 3600) return `${Math.round(seconds / 60)} min ago`
  if (seconds < 86400) return `${Math.round(seconds / 3600)} h ago`
  return `${Math.round(seconds / 86400)} d ago`
}

export function daysUntil(value: string | null | undefined): number | null {
  if (!value) return null
  const target = new Date(`${value}T00:00:00`).getTime()
  if (Number.isNaN(target)) return null
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  return Math.round((target - today.getTime()) / 86400000)
}

/** Return "1 change" or "3 changes". */
export function plural(count: number, one: string, many?: string): string {
  return `${count} ${count === 1 ? one : (many ?? `${one}s`)}`
}

/** Write a byte count the way a download dialogue does: "1.02 GB". */
export function formatBytes(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes <= 0) return '0 MB'
  const mb = bytes / 1_000_000
  if (mb < 1) return `${Math.round(bytes / 1000)} kB`
  if (mb < 1000) return `${mb < 10 ? mb.toFixed(1) : Math.round(mb)} MB`
  return `${(mb / 1000).toFixed(2)} GB`
}

/** Write a wait the way a person says it: "3 min 20 s", "45 s". */
export function formatWait(seconds: number | null): string {
  if (seconds === null || !Number.isFinite(seconds) || seconds < 0) return '—'
  const whole = Math.round(seconds)
  if (whole < 60) return `${whole} s`
  const minutes = Math.floor(whole / 60)
  if (minutes < 60) {
    const rest = whole % 60
    return rest ? `${minutes} min ${rest} s` : `${minutes} min`
  }
  const hours = Math.floor(minutes / 60)
  return `${hours} h ${minutes % 60} min`
}
