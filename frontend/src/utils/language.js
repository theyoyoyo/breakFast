// AI response language: English (default) or Turkish. AI replies and units follow it; the UI stays English.
// Saved as the response_language preference and cached on the device, like the theme.

export const DEFAULT_LANGUAGE = 'en'
const LANGUAGES = ['en', 'tr']
const STORAGE_KEY = 'bf_language'

const isLanguage = (key) => LANGUAGES.includes(key)
const listeners = new Set()

function storedLanguage() {
  try {
    const key = localStorage.getItem(STORAGE_KEY)
    return isLanguage(key) ? key : DEFAULT_LANGUAGE
  } catch {
    return DEFAULT_LANGUAGE
  }
}

let current = storedLanguage()

export function currentLanguage() {
  return current
}

// Set the language, remember it on this device and re-render subscribers; unknown keys fall back to English
export function applyLanguage(key) {
  const language = isLanguage(key) ? key : DEFAULT_LANGUAGE
  try { localStorage.setItem(STORAGE_KEY, language) } catch { /* private mode — fine */ }
  if (language !== current) {
    current = language
    listeners.forEach(listener => listener())
  }
  return language
}

export function subscribeLanguage(listener) {
  listeners.add(listener)
  return () => listeners.delete(listener)
}
