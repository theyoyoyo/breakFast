/**
 * Tests for the theme helpers: applying a theme to the page and remembering it on the device.
 */

import { describe, it, expect, beforeEach } from 'vitest'
import { applyTheme, storedTheme, THEMES } from './theme'

describe('theme', () => {
  beforeEach(() => {
    localStorage.clear()
    delete document.documentElement.dataset.theme
  })

  it('offers orange, purple and green', () => {
    expect(THEMES.map(t => t.key)).toEqual(['orange', 'purple', 'green'])
  })

  it('sets data-theme for purple and green and remembers the choice', () => {
    expect(applyTheme('purple')).toBe('purple')
    expect(document.documentElement.dataset.theme).toBe('purple')
    expect(storedTheme()).toBe('purple')
  })

  it('uses the default stylesheet for orange (no data-theme)', () => {
    applyTheme('green')
    applyTheme('orange')
    expect(document.documentElement.dataset.theme).toBeUndefined()
    expect(storedTheme()).toBe('orange')
  })

  it('falls back to orange for missing or unknown values', () => {
    expect(storedTheme()).toBe('orange')
    expect(applyTheme(undefined)).toBe('orange')
    expect(applyTheme('neon')).toBe('orange')
    localStorage.setItem('bf_theme', 'neon')
    expect(storedTheme()).toBe('orange')
  })
})
