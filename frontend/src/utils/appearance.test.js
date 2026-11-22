/**
 * Tests for the Appearance setting (#235): Auto, Light or Dark on the page, remembered on the device.
 */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'

// A fresh module per test: the app watches the device query once per page load
let APPEARANCES, applyAppearance, currentMode, storedAppearance, subscribeMode

// A fake prefers-color-scheme query whose answer a test can change, like a phone switching at sunset
function fakeDevice(light) {
  const listeners = new Set()
  const query = {
    get matches() { return light },
    addEventListener: (_, fn) => listeners.add(fn),
  }
  window.matchMedia = vi.fn(() => query)
  return { set: (value) => { light = value; listeners.forEach(fn => fn()) } }
}

describe('appearance', () => {
  beforeEach(async () => {
    vi.resetModules()
    ;({ APPEARANCES, applyAppearance, currentMode, storedAppearance, subscribeMode } = await import('./appearance'))
    localStorage.clear()
    delete document.documentElement.dataset.mode
  })
  afterEach(() => {
    delete window.matchMedia
  })

  // The three choices, Auto first as the default
  it('offers Auto, Light and Dark', () => {
    expect(APPEARANCES.map(a => a.key)).toEqual(['auto', 'light', 'dark'])
    expect(storedAppearance()).toBe('auto')
  })

  // Light and Dark set data-mode on the page and are remembered on the device
  it('applies and remembers Light and Dark', () => {
    fakeDevice(false)
    expect(applyAppearance('light')).toBe('light')
    expect(document.documentElement.dataset.mode).toBe('light')
    expect(storedAppearance()).toBe('light')
    applyAppearance('dark')
    expect(document.documentElement.dataset.mode).toBe('dark')
    expect(currentMode()).toBe('dark')
  })

  // Auto follows the device, also when the device switches while the app is open
  it('follows the device on Auto', () => {
    const device = fakeDevice(true)
    applyAppearance('auto')
    expect(document.documentElement.dataset.mode).toBe('light')
    const listener = vi.fn()
    const unsubscribe = subscribeMode(listener)
    device.set(false)
    expect(document.documentElement.dataset.mode).toBe('dark')
    expect(listener).toHaveBeenCalled()
    unsubscribe()
  })

  // A fixed choice ignores the device switching
  it('keeps a fixed choice when the device switches', () => {
    const device = fakeDevice(true)
    applyAppearance('dark')
    device.set(true)
    expect(document.documentElement.dataset.mode).toBe('dark')
  })

  // Unknown values fall back to Auto; without matchMedia Auto is dark, today's look
  it('falls back to Auto, and dark without a device reading', () => {
    expect(applyAppearance('neon')).toBe('auto')
    expect(document.documentElement.dataset.mode).toBe('dark')
    localStorage.setItem('bf_appearance', 'neon')
    expect(storedAppearance()).toBe('auto')
  })
})
