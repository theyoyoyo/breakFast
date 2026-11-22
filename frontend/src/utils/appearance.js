// Appearance setting: Auto (follows the device, default), Light or Dark.
// Saved as the `appearance` preference and cached on the device, like the theme, so the right mode
// paints before the first render. The page's mode is data-mode="light" | "dark" on <html> (index.css).

export const APPEARANCES = [
  { key: 'auto', label: 'Auto' },
  { key: 'light', label: 'Light' },
  { key: 'dark', label: 'Dark' },
]

export const DEFAULT_APPEARANCE = 'auto'
const STORAGE_KEY = 'bf_appearance'

const isAppearance = (key) => APPEARANCES.some(a => a.key === key)
const listeners = new Set()
let appearance = DEFAULT_APPEARANCE
let deviceQuery = null

// The device's own setting, read through prefers-color-scheme; dark when the browser can't tell
function deviceMode() {
  try {
    return window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark'
  } catch {
    return 'dark'
  }
}

// The mode on screen now: the setting, or the device's mode for Auto
export function currentMode() {
  return appearance === 'auto' ? deviceMode() : appearance
}

function paint() {
  document.documentElement.dataset.mode = currentMode()
  listeners.forEach(listener => listener())
}

// Auto follows the device live: a phone switching to dark at sunset switches the app too
function watchDevice() {
  if (deviceQuery) return
  try {
    deviceQuery = window.matchMedia('(prefers-color-scheme: light)')
    deviceQuery.addEventListener?.('change', () => { if (appearance === 'auto') paint() })
  } catch { /* no matchMedia (old browser, tests) — Auto stays on the first reading */ }
}

// Last appearance used on this device
export function storedAppearance() {
  try {
    const key = localStorage.getItem(STORAGE_KEY)
    return isAppearance(key) ? key : DEFAULT_APPEARANCE
  } catch {
    return DEFAULT_APPEARANCE
  }
}

// Apply an appearance to the page and remember it on this device; unknown keys fall back to Auto
export function applyAppearance(key) {
  appearance = isAppearance(key) ? key : DEFAULT_APPEARANCE
  try { localStorage.setItem(STORAGE_KEY, appearance) } catch { /* private mode — fine */ }
  watchDevice()
  paint()
  return appearance
}

export function subscribeMode(listener) {
  listeners.add(listener)
  return () => listeners.delete(listener)
}
