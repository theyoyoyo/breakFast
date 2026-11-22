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

  // Light mode (#235): each theme's light accent passes WCAG AA on the page, the panels and its bubble,
  // its dishes on the bubble, the light text on every surface, and white text on the secondary buttons
  it('defines readable light colors for every theme', async () => {
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
    const light = block(':root[data-mode="light"]')
    const surfaces = ['bg', 'surface', 'surface2'].map(n => color(light, n))
    for (const name of ['text', 'text-muted']) {
      for (const bg of surfaces) expect(contrast(color(light, name), bg), name).toBeGreaterThanOrEqual(4.5)
    }
    for (const { key } of THEMES) {
      const text = key === 'orange' ? light : block(`:root[data-mode="light"][data-theme="${key}"]`)
      const dark = block(key === 'orange' ? ':root' : `:root[data-theme="${key}"]`)
      const accent = color(text, 'accent')
      const bubble = color(text, 'bubble')
      for (const bg of [...surfaces, bubble]) expect(contrast(accent, bg), `${key} accent`).toBeGreaterThanOrEqual(4.5)
      expect(contrast(color(light, 'text'), bubble), `${key} text on bubble`).toBeGreaterThanOrEqual(4.5)
      const dishes = [1, 2, 3, 4].map(n => color(text, `dish-${n}`))
      expect(new Set(dishes).size, key).toBe(4)
      expect(dishes[0], key).toBe(accent)
      for (const dish of dishes) expect(contrast(dish, bubble), `${key} ${dish}`).toBeGreaterThanOrEqual(4.5)
      expect(contrast('#ffffff', color(dark, 'secondary')), `${key} secondary`).toBeGreaterThanOrEqual(4.5)
    }
  })

  // Semantic text colors (red, yellow, green …) stay readable on the light surfaces
  it('keeps semantic colors readable in light mode', async () => {
    const fs = await import('node:fs')
    const path = await import('node:path')
    const css = fs.readFileSync(path.resolve(process.cwd(), 'src/index.css'), 'utf8')
    const light = css.slice(css.indexOf(':root[data-mode="light"] {')).split('}')[0]
    const color = (name) => light.match(new RegExp(`--${name}:\\s*(#[0-9a-f]{6})`, 'i'))?.[1]
    const luminance = (hex) => {
      const [r, g, b] = [1, 3, 5].map(i => parseInt(hex.slice(i, i + 2), 16) / 255)
        .map(c => (c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4))
      return 0.2126 * r + 0.7152 * g + 0.0722 * b
    }
    const contrast = (a, b) => {
      const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x)
      return (hi + 0.05) / (lo + 0.05)
    }
    for (const name of ['c-success-text', 'c-gold-text', 'c-error', 'c-danger', 'c-red', 'c-warn', 'c-green',
      'c-purple', 'c-purple-soft', 'c-sometimes-text', 'c-score-mid', 'c-priority-top', 'c-edit-text']) {
      for (const bg of ['surface', 'surface2']) expect(contrast(color(name), color(bg)), name).toBeGreaterThanOrEqual(4.5)
    }
    expect(contrast(color('c-success-text'), color('c-success'))).toBeGreaterThanOrEqual(4.5)
    expect(contrast(color('c-gold-text'), color('c-gold'))).toBeGreaterThanOrEqual(4.5)
    for (const fill of ['c-danger-strong', 'c-green-strong', 'c-success-text', 'c-gold-text']) {
      expect(contrast('#ffffff', color(fill)), fill).toBeGreaterThanOrEqual(4.5)
    }
  })

  // Each swatch in Settings is the theme's accent in that mode
  it('matches the swatches to the accents', async () => {
    const fs = await import('node:fs')
    const path = await import('node:path')
    const css = fs.readFileSync(path.resolve(process.cwd(), 'src/index.css'), 'utf8')
    const accent = (selector) => css.slice(css.indexOf(`${selector} {`)).split('}')[0].match(/--accent:\s*(#[0-9a-f]{6})/i)[1]
    for (const t of THEMES) {
      const dark = t.key === 'orange' ? ':root' : `:root[data-theme="${t.key}"]`
      const light = t.key === 'orange' ? ':root[data-mode="light"]' : `:root[data-mode="light"][data-theme="${t.key}"]`
      expect(t.swatch, t.key).toBe(accent(dark))
      expect(t.lightSwatch, t.key).toBe(accent(light))
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
