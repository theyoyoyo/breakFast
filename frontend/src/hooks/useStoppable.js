import { useCallback, useEffect, useRef, useState } from 'react'

// How long the small "Stopped" note shows after a Stop
export const STOPPED_NOTE_MS = 2500

/** The running button's text: what it's doing, and that a tap stops it ("Analyzing… (stop)"). */
export const stopLabel = (text) => `${text} (stop)`

/**
 * A model call the user can stop (#288): shopping suggestions, the weekly analysis, a meal's analysis.
 *
 * `run(key, task)` calls `task(signal)` and resolves to `{ value }`, or to `{ stopped: true }` when
 * the user stopped it; other errors are thrown as before. `running` is the running call's key (true
 * when none was given), null when none runs; `stop()` aborts it at once (the fetch, and with it the
 * model call on the server), so the button returns to normal and nothing new shows; `stopped` is the
 * stopped call's key for a short while, for a small "Stopped" note. A new run stops the one before,
 * and leaving the screen stops a running call.
 */
export default function useStoppable() {
  const controllerRef = useRef(null)
  const keyRef = useRef(null)
  const noteTimer = useRef(null)
  const [running, setRunning] = useState(null)
  const [stopped, setStopped] = useState(null)

  useEffect(() => () => {
    controllerRef.current?.abort()
    clearTimeout(noteTimer.current)
  }, [])

  const run = useCallback(async (key, task) => {
    controllerRef.current?.abort()
    const controller = new AbortController()
    controllerRef.current = controller
    clearTimeout(noteTimer.current)
    setStopped(null)
    keyRef.current = key ?? true
    setRunning(keyRef.current)
    try {
      return { value: await task(controller.signal) }
    } catch (err) {
      if (controller.signal.aborted) return { stopped: true }
      throw err
    } finally {
      if (controllerRef.current === controller) {
        controllerRef.current = null
        setRunning(null)
      }
    }
  }, [])

  const stop = useCallback(() => {
    const controller = controllerRef.current
    if (!controller) return
    controllerRef.current = null
    controller.abort()
    setRunning(null)
    setStopped(keyRef.current)
    clearTimeout(noteTimer.current)
    noteTimer.current = setTimeout(() => setStopped(null), STOPPED_NOTE_MS)
  }, [])

  return { running, stopped, run, stop }
}
