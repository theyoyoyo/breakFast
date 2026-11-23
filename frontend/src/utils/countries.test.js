/**
 * Tests for the Settings → Profile country list and its ISO codes.
 */

import { describe, it, expect } from 'vitest'
import { COUNTRIES, countryCode } from './countries'

describe('COUNTRIES', () => {
  // The country list is sorted and each name appears once
  it('is alphabetical with no duplicates, so the dropdown is easy to scan', () => {
    const names = COUNTRIES.map(c => c.name)
    const sorted = [...names].sort((a, b) => a.localeCompare(b, 'en'))
    expect(names).toEqual(sorted)
    expect(new Set(names).size).toBe(names.length)
  })

  // The saved country name for Turkey is its official one, with its ISO code
  it('names Turkey the way the UN does', () => {
    expect(COUNTRIES).toContainEqual({ name: 'Türkiye', code: 'TR' })
  })

  // Every country has its own two-letter code, so the closed selector can show it
  it('gives every country a distinct two-letter code', () => {
    for (const { code } of COUNTRIES) expect(code).toMatch(/^[A-Z]{2}$/)
    expect(new Set(COUNTRIES.map(c => c.code)).size).toBe(COUNTRIES.length)
  })

  // A saved name maps to its code, and a name that isn't listed has none
  it('looks up a code by the saved name', () => {
    expect(countryCode('Germany')).toBe('DE')
    expect(countryCode('United Kingdom')).toBe('GB')
    expect(countryCode('Atlantis')).toBeNull()
  })
})
