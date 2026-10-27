import { useSyncExternalStore } from 'react'
import { currentLanguage, subscribeLanguage } from '../utils/language'

/** The AI response language ('en' / 'tr'); re-renders when Settings switches it. */
export function useLanguage() {
  return useSyncExternalStore(subscribeLanguage, currentLanguage)
}
