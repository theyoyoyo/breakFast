import SuggestButton from './SuggestButton'
import ate1 from '../assets/chat/today-i-ate@1x.webp'
import ate2 from '../assets/chat/today-i-ate@2x.webp'
import ate3 from '../assets/chat/today-i-ate@3x.webp'

const PILL = 'rounded-3xl border-0 px-5 py-2.5 text-sm font-semibold text-white transition-opacity active:scale-[0.95]'

/**
 * The one bar under the chat: "Today I ate" on the left, the text box, and on the right the
 * Suggest cloche, which turns into Send while the box has text (and Stop while a reply runs).
 * The mic sits inside the box, at its right end, while the box is empty.
 *
 * Props:
 *   input, onInputChange, onKeyDown — the text box
 *   onSend, onStop, busy            — Send / Stop; busy is a reply, analysis or plan running
 *   onSuggest, suggestDisabled      — the Suggest button (mode or nothing)
 *   onTodayIAte                     — opens "Today I ate"
 *   voice                           — { supported, listening, onMic }
 */
export default function ChatBar({
  input, onInputChange, onKeyDown, onSend, onStop, busy,
  onSuggest, suggestDisabled, onTodayIAte, voice,
}) {
  const typed = input.trim() !== ''
  const showMic = voice.supported && (!typed || voice.listening)

  return (
    <div className="flex items-center gap-1.5 border-t border-line bg-surface py-2.5 pl-2 pr-5">
      <button
        type="button"
        className="-my-2 flex h-[60px] w-[58px] flex-none items-center justify-center border-0 bg-transparent p-0 transition-transform active:scale-[0.92] disabled:cursor-not-allowed disabled:opacity-40"
        onClick={onTodayIAte}
        disabled={busy}
        title="Today I ate..."
        aria-label="Today I ate"
      >
        <img src={ate1} srcSet={`${ate1} 1x, ${ate2} 2x, ${ate3} 3x`} alt="" className="block h-[70px] w-auto" draggable={false} />
      </button>

      <div className="flex min-w-0 flex-1 items-end rounded-3xl border border-line bg-surface-2 pl-3.5">
        <textarea
          className="max-h-[120px] min-h-[44px] min-w-0 flex-1 resize-none border-0 bg-transparent py-3 pr-3 text-sm text-fg outline-none [field-sizing:content] placeholder:truncate placeholder:text-fg-muted"
          value={input}
          onChange={(e) => onInputChange(e.target.value)}
          onKeyDown={onKeyDown}
          placeholder="What are you craving?"
          rows={1}
          disabled={busy}
        />
        {showMic && (
          <button
            type="button"
            className="mb-[3px] mr-1 flex h-[38px] w-[38px] flex-none items-center justify-center rounded-full border-0 bg-transparent p-0 text-lg"
            onClick={voice.onMic}
            title="Voice input"
            aria-label={voice.listening ? 'Stop voice input' : 'Voice input'}
          >
            {voice.listening ? '🔴' : '🎤'}
          </button>
        )}
      </div>

      <div className="relative -my-2 flex h-[60px] w-[122px] flex-none items-center justify-center">
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
