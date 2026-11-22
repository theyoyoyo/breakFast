// Theme setting: orange (default) plus green, teal, blue and purple, in color-wheel order.
// The colors live in index.css under :root[data-theme=…] (and [data-mode="light"] for light mode);
// only the accents change. Each swatch is the theme's accent in dark and in light mode.

export const THEMES = [
  { key: 'orange', label: 'Orange', swatch: '#f4a261', lightSwatch: '#9d5300' },
  { key: 'green', label: 'Green', swatch: '#c3c96b', lightSwatch: '#696c02' },
  { key: 'teal', label: 'Teal', swatch: '#8fd3c1', lightSwatch: '#127663' },
  { key: 'blue', label: 'Blue', swatch: '#a7b6f2', lightSwatch: '#57649c' },
  { key: 'purple', label: 'Purple', swatch: '#e0a3d6', lightSwatch: '#8b5483' },
]

export const DEFAULT_THEME = 'orange'
const STORAGE_KEY = 'bf_theme'

const isTheme = (key) => THEMES.some(t => t.key === key)

// Last theme used on this device, so it applies before the first paint
export function storedTheme() {
  try {
    const key = localStorage.getItem(STORAGE_KEY)
    return isTheme(key) ? key : DEFAULT_THEME
  } catch {
    return DEFAULT_THEME
  }
}

// Apply a theme to the page and remember it on this device; unknown keys fall back to orange
export function applyTheme(key) {
  const theme = isTheme(key) ? key : DEFAULT_THEME
  if (theme === DEFAULT_THEME) delete document.documentElement.dataset.theme
  else document.documentElement.dataset.theme = theme
  try { localStorage.setItem(STORAGE_KEY, theme) } catch { /* private mode — fine */ }
  return theme
}
