import { useState, useRef, useCallback } from 'react'
import u2Logo from '../assets/u2.png'
import * as s from './SuggestButton.styles'

const LONG_PRESS_MS = 2000

export default function SuggestButton({ onSuggest, disabled }) {
  const [panelOpen, setPanelOpen] = useState(false)
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

  const handlePointerUp = useCallback(() => {
    clearTimeout(timerRef.current)
    if (!longPressedRef.current && !disabled) {
      // Short press — only fire if panel is closed
      if (!panelOpen) {
        onSuggest()
      } else {
        setPanelOpen(false)
      }
    }
  }, [disabled, panelOpen, onSuggest])

  const handlePointerLeave = useCallback(() => {
    clearTimeout(timerRef.current)
  }, [])

  const handleMode = useCallback((mode) => {
    setPanelOpen(false)
    onSuggest(mode)
  }, [onSuggest])

  return (
    <div style={s.wrapper}>
      {panelOpen && (
        <div style={s.panel}>
          <button
            style={s.modeBtn}
            onClick={() => handleMode('favorites')}
            disabled={disabled}
          >
            Sevdiklerimden
          </button>
          <button
            style={s.modeBtn}
            onClick={() => handleMode('explore')}
            disabled={disabled}
          >
            Kesfet
          </button>
        </div>
      )}
      <button
        style={s.button(disabled)}
        onPointerDown={handlePointerDown}
        onPointerUp={handlePointerUp}
        onPointerLeave={handlePointerLeave}
        disabled={disabled}
        title="Kahvaltı Öner (basılı tut: modlar)"
      >
        <img
          src={u2Logo}
          alt="Kahvaltı Öner"
          style={s.logo}
          draggable={false}
        />
      </button>
    </div>
  )
}
