import { describe, it, expect } from 'vitest'
import { formatShortDate, formatDateTime } from './date'

describe('date formatting', () => {
  // An expiry date reads with an English month name, never a Turkish one
  it('formats an expiry date in English', () => {
    expect(formatShortDate('2026-03-05')).toBe('5 Mar')
    expect(formatShortDate('2026-05-01')).not.toMatch(/May[ıi]s/)
  })

  // A missing date gives nothing and one that can't be read is shown as written
  it('handles a missing or unreadable date', () => {
    expect(formatShortDate('')).toBeNull()
    expect(formatShortDate('soon')).toBe('soon')
  })

  // A logged meal's time reads with an English month name and the year
  it('formats a logged time in English', () => {
    const text = formatDateTime('2026-03-05T08:30:00')
    expect(text).toContain('5 Mar 2026')
    expect(text).toContain('08:30')
    expect(formatDateTime('nope')).toBe('')
  })
})
