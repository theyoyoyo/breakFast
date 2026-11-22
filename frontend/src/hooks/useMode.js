import { useSyncExternalStore } from 'react'
import { currentMode, subscribeMode } from '../utils/appearance'

/** The mode on screen ('light' / 'dark'); re-renders when the Appearance setting or the device changes it. */
export function useMode() {
  return useSyncExternalStore(subscribeMode, currentMode)
}
