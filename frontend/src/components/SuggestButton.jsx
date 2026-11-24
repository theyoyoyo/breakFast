import { useState, useRef, useCallback } from 'react'
import suggest1 from '../assets/chat/suggest@1x.webp'
import suggest2 from '../assets/chat/suggest@2x.webp'
import suggest3 from '../assets/chat/suggest@3x.webp'
import favorites1 from '../assets/chat/favorites@1x.webp'
import favorites2 from '../assets/chat/favorites@2x.webp'
import favorites3 from '../assets/chat/favorites@3x.webp'
import explore1 from '../assets/chat/explore@1x.webp'
import explore2 from '../assets/chat/explore@2x.webp'
import explore3 from '../assets/chat/explore@3x.webp'

const LONG_PRESS_MS = 1000

// A long press opens the modes, not the phone's callout, text selection or context menu
const NO_CALLOUT = { WebkitTouchCallout: 'none', WebkitUserSelect: 'none', userSelect: 'none' }
const preventMenu = (e) => e.preventDefault()

const srcSet = (a, b, c) => `${a} 1x, ${b} 2x, ${c} 3x`

// The two Suggest modes a long press reveals. Their pictures share one canvas and scale,
// so the plates sit on one line and the domes come out the same size.
const MODES = [
  { mode: 'favorites', label: 'Suggest from favorites', src: favorites1, set: srcSet(favorites1, favorites2, favorites3) },
  { mode: 'explore', label: 'Explore world cuisines', src: explore1, set: srcSet(explore1, explore2, explore3) },
]

/**
 * The Suggest button at the right of the chat bar: the gold cloche right on the surface, no frame.
 * A tap suggests a breakfast and plays the dash; a long press (1s) reveals Favorites and
 * Explore side by side above it, with the app dimmed behind; a tap outside closes them.
 */
export default function SuggestButton({ onSuggest, disabled }) {
  const [panelOpen, setPanelOpen] = useState(false)
  // Bumped on every tap, so the dash plays again
  const [dashKey, setDashKey] = useState(0)
  const timerRef = useRef(null)
  const longPressedRef = useRef(false)

  const handlePointerDown = useCallback(() => {
    if (disabled) return
    longPressedRef.current = false
    timerRef.current = setTimeout(() => {
      longPressedRef.current = true
      setPanelOpen(prev => !prev)
    }, LONG_PRESS_MS)
  }, [disabled])

  const tap = useCallback(() => {
    if (panelOpen) {
      setPanelOpen(false)
      return
    }
    setDashKey(k => k + 1)
    onSuggest()
  }, [panelOpen, onSuggest])

  const handlePointerUp = useCallback(() => {
    clearTimeout(timerRef.current)
    if (!longPressedRef.current && !disabled) tap()
  }, [disabled, tap])

  const handlePointerLeave = useCallback(() => {
    clearTimeout(timerRef.current)
  }, [])

  // Enter or Space on the focused button (a click with no pointer behind it) suggests too
  const handleClick = useCallback((e) => {
    if (e.detail === 0 && !disabled) tap()
  }, [disabled, tap])

  const handleMode = useCallback((mode) => {
    setPanelOpen(false)
    onSuggest(mode)
  }, [onSuggest])

  return (
    <div className="relative flex h-full w-full items-center justify-center">
      {panelOpen && (
        <>
          <div
            className="fixed inset-0 z-40 bg-black/40"
            onClick={() => setPanelOpen(false)}
            data-testid="suggest-backdrop"
          />
          <div className="absolute bottom-full left-1/2 z-50 mb-1 flex -translate-x-[62%] gap-2">
            {MODES.map(({ mode, label, src, set }, i) => (
              <button
                key={mode}
                type="button"
                className="border-0 bg-transparent p-0 drop-shadow-lg transition-transform active:scale-[0.92] disabled:opacity-40 motion-safe:animate-pop"
                style={{ animationDelay: `${i * 60}ms` }}
                onClick={() => handleMode(mode)}
                disabled={disabled}
                title={label}
                aria-label={label}
              >
                <img src={src} srcSet={set} alt="" className="block h-[92px] w-auto" draggable={false} />
              </button>
            ))}
          </div>
        </>
      )}
      <button
        type="button"
        className="flex touch-none select-none items-center justify-center border-0 bg-transparent p-0 transition-transform active:scale-[0.92] disabled:cursor-not-allowed disabled:opacity-40"
        onPointerDown={handlePointerDown}
        onPointerUp={handlePointerUp}
        onPointerLeave={handlePointerLeave}
        onContextMenu={preventMenu}
        onClick={handleClick}
        disabled={disabled}
        style={NO_CALLOUT}
        title="Suggest breakfast (hold: modes)"
        aria-label="Suggest breakfast"
      >
        <img
          key={dashKey}
          src={suggest1}
          srcSet={srcSet(suggest1, suggest2, suggest3)}
          alt=""
          className={`pointer-events-none block h-[64px] w-auto ${dashKey ? 'motion-safe:animate-dash' : ''}`}
          draggable={false}
        />
      </button>
    </div>
  )
}
