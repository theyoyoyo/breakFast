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

  it('offers five themes in color-wheel order, orange first', () => {
    expect(THEMES.map(t => t.key)).toEqual(['orange', 'green', 'teal', 'blue', 'purple'])
  })

  it('has a stylesheet block for every theme except the default', async () => {
    const fs = await import('node:fs')
    const path = await import('node:path')
    const css = fs.readFileSync(path.resolve(process.cwd(), 'src/index.css'), 'utf8')
    for (const { key } of THEMES.slice(1)) {
      expect(css).toContain(`:root[data-theme="${key}"]`)
    }
  })

  // Every theme has four prep-plan dish colors, the first its accent, each passing WCAG AA on its bubble
  it('defines four readable dish colors for every theme', async () => {
    const fs = await import('node:fs')
    const path = await import('node:path')
    const css = fs.readFileSync(path.resolve(process.cwd(), 'src/index.css'), 'utf8')
    const block = (selector) => css.slice(css.indexOf(`${selector} {`)).split('}')[0]
    const color = (text, name) => text.match(new RegExp(`--${name}:\\s*(#[0-9a-f]{6})`, 'i'))?.[1]
    const luminance = (hex) => {
      const [r, g, b] = [1, 3, 5].map(i => parseInt(hex.slice(i, i + 2), 16) / 255)
        .map(c => (c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4))
      return 0.2126 * r + 0.7152 * g + 0.0722 * b
    }
    const contrast = (a, b) => {
      const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x)
      return (hi + 0.05) / (lo + 0.05)
    }
    for (const { key } of THEMES) {
      const text = block(key === 'orange' ? ':root' : `:root[data-theme="${key}"]`)
      const dishes = [1, 2, 3, 4].map(n => color(text, `dish-${n}`))
      expect(dishes.every(Boolean), key).toBe(true)
      expect(new Set(dishes).size, key).toBe(4)
      expect(dishes[0], key).toBe(color(text, 'accent'))
      for (const dish of dishes) expect(contrast(dish, color(text, 'bubble')), `${key} ${dish}`).toBeGreaterThanOrEqual(4.5)
    }
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
