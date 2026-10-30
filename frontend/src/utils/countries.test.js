/**
 * Tests for the Settings → Profile country list.
 */

import { describe, it, expect } from 'vitest'
import { COUNTRIES } from './countries'

describe('COUNTRIES', () => {
  it('is alphabetical with no duplicates, so the dropdown is easy to scan', () => {
    const sorted = [...COUNTRIES].sort((a, b) => a.localeCompare(b, 'en'))
    expect(COUNTRIES).toEqual(sorted)
    expect(new Set(COUNTRIES).size).toBe(COUNTRIES.length)
  })

  it('names Turkey the way the UN does', () => {
    expect(COUNTRIES).toContain('Türkiye')
  })
})
