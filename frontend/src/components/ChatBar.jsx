import { useState, useEffect, useRef } from 'react'
import SuggestButton from './SuggestButton'
import ate1 from '../assets/chat/today-i-ate@1x.webp'
import ate2 from '../assets/chat/today-i-ate@2x.webp'
import ate3 from '../assets/chat/today-i-ate@3x.webp'

const PILL = 'rounded-3xl border-0 px-5 py-2.5 text-sm font-semibold text-white transition-opacity active:scale-[0.95]'

// How long the mic's "Available soon!" note stays
const SOON_MS = 2000

/**
 * The one bar under the chat: "Today I ate" on the left, the text box, and on the right the
 * Suggest cloche, which turns into Send while the box has text (and Stop while a reply runs).
 * The mic sits inside the box, at its right end, while the box is empty; until voice input is
 * ready, a tap on it says "Available soon!".
 *
 * Props:
 *   input, onInputChange, onKeyDown — the text box
 *   onSend, onStop, busy            — Send / Stop; busy is a reply, analysis or plan running
 *   onSuggest, suggestDisabled      — the Suggest button (mode or nothing)
 *   onTodayIAte                     — opens "Today I ate"
 */
export default function ChatBar({
  input, onInputChange, onKeyDown, onSend, onStop, busy,
  onSuggest, suggestDisabled, onTodayIAte,
}) {
  const typed = input.trim() !== ''
  const [soon, setSoon] = useState(false)
  const soonTimer = useRef(null)
  useEffect(() => () => clearTimeout(soonTimer.current), [])

  const showSoon = () => {
    clearTimeout(soonTimer.current)
    setSoon(true)
    soonTimer.current = setTimeout(() => setSoon(false), SOON_MS)
  }

  return (
    <div className="flex items-center gap-1 border-t border-line bg-surface py-1.5 pl-2 pr-1.5">
      <button
        type="button"
        className="flex h-[64px] w-[54px] flex-none items-center justify-center border-0 bg-transparent p-0 transition-transform active:scale-[0.92] disabled:cursor-not-allowed disabled:opacity-40"
        onClick={onTodayIAte}
        disabled={busy}
        title="Today I ate..."
        aria-label="Today I ate"
      >
        <img src={ate1} srcSet={`${ate1} 1x, ${ate2} 2x, ${ate3} 3x`} alt="" className="block h-[66px] w-auto" draggable={false} />
      </button>

      <div className="relative flex min-w-0 flex-1 items-end rounded-3xl border border-line bg-surface-2 pl-3">
        <textarea
          className="max-h-[120px] min-h-[50px] min-w-0 flex-1 resize-none border-0 bg-transparent py-[15px] pr-1 text-sm text-fg outline-none [field-sizing:content] placeholder:truncate placeholder:text-[13px] placeholder:text-fg-muted"
          value={input}
          onChange={(e) => onInputChange(e.target.value)}
          onKeyDown={onKeyDown}
          placeholder="What are you craving?"
          rows={1}
          disabled={busy}
        />
        {!typed && (
          <button
            type="button"
            className="mb-[6px] mr-0.5 flex h-[36px] w-[34px] flex-none items-center justify-center rounded-full border-0 bg-transparent p-0 text-lg"
            onClick={showSoon}
            title="Voice input"
            aria-label="Voice input"
          >
            🎤
          </button>
        )}
        {soon && (
          <div role="status" className="absolute bottom-full right-0 mb-2 whitespace-nowrap rounded-xl border border-line bg-surface px-3 py-1.5 text-xs font-semibold text-fg shadow-lg motion-safe:animate-pop">
            Available soon!
          </div>
        )}
      </div>

      {/* Stop and Send sit centered where the cloche is; the cloche keeps to the right edge */}
      <div className="relative flex h-[64px] w-[100px] flex-none items-center justify-center">
        {busy ? (
          <button type="button" className={`${PILL} bg-secondary`} onClick={onStop}>Stop</button>
        ) : typed ? (
          <button type="button" className={`${PILL} bg-secondary`} onClick={onSend}>Send</button>
        ) : (
          <SuggestButton onSuggest={onSuggest} disabled={suggestDisabled} />
        )}
      </div>
    </div>
  )
}
