// The UI is English only (the language setting changes AI replies), so dates read in English
// whatever the device or browser locale.
const LOCALE = 'en-GB'

/** A 'YYYY-MM-DD' date (an expiry date) as a short English day and month: "5 Mar". */
export function formatShortDate(dateStr) {
  if (!dateStr) return null
  const d = new Date(dateStr + 'T00:00:00')
  if (Number.isNaN(d.getTime())) return dateStr
  return d.toLocaleDateString(LOCALE, { day: 'numeric', month: 'short' })
}

/** A timestamp (a logged meal) as an English day, month, year and time: "5 Mar 2026, 08:30". */
export function formatDateTime(value) {
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return ''
  return d.toLocaleDateString(LOCALE, { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' })
}
