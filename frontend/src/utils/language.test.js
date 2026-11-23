/**
 * Tests for the AI language store: remembering the language on the device and notifying subscribers.
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { applyLanguage, currentLanguage, subscribeLanguage } from './language'

describe('language', () => {
  beforeEach(() => {
    applyLanguage('en')
    localStorage.clear()
  })

  // Turkish becomes the current language and is cached on the device for the next start
  it('switches to Turkish and remembers it on the device', () => {
    expect(applyLanguage('tr')).toBe('tr')
    expect(currentLanguage()).toBe('tr')
    expect(localStorage.getItem('bf_language')).toBe('tr')
  })

  // Only English and Turkish exist, so anything else resets to English
  it('falls back to English for missing or unknown values', () => {
    applyLanguage('tr')
    expect(applyLanguage(undefined)).toBe('en')
    expect(applyLanguage('de')).toBe('en')
    expect(currentLanguage()).toBe('en')
  })

  // Setting the same language again doesn't re-render listeners, and an unsubscribed one hears nothing
  it('notifies subscribers only when the language changes', () => {
    const listener = vi.fn()
    const unsubscribe = subscribeLanguage(listener)
    applyLanguage('en')
    expect(listener).not.toHaveBeenCalled()
    applyLanguage('tr')
    expect(listener).toHaveBeenCalledTimes(1)
    unsubscribe()
    applyLanguage('en')
    expect(listener).toHaveBeenCalledTimes(1)
  })
})
