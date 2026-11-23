import { useEffect, useLayoutEffect, useRef } from 'react'

// App-wide sync notices. The chat socket is open while the app is (every tab stays mounted),
// so ChatInterface passes the server's small notices ({ type: 'supplements_updated' }, …)
// to every panel as one window event, plus { type: 'sync_connected' } when the socket opens,
// so a panel can catch up on what it missed while disconnected.
export const SYNC_NOTICE_EVENT = 'bf:sync-notice'

/** Pass a notice to every panel listening for its type. */
export function emitSyncNotice(notice) {
  window.dispatchEvent(new CustomEvent(SYNC_NOTICE_EVENT, { detail: notice }))
}

/** Call `handler(notice)` on every notice whose type is `types` (a string or a list). */
export function useSyncNotice(types, handler) {
  const handlerRef = useRef(handler)
  // The latest handler, set after each render (not during it) and before any effect can emit a notice.
  useLayoutEffect(() => {
    handlerRef.current = handler
  })
  const key = [].concat(types).join(' ')
  useEffect(() => {
    const wanted = new Set(key.split(' '))
    const listener = (e) => {
      if (wanted.has(e.detail?.type)) handlerRef.current(e.detail)
    }
    window.addEventListener(SYNC_NOTICE_EVENT, listener)
    return () => window.removeEventListener(SYNC_NOTICE_EVENT, listener)
  }, [key])
}
