import { useState } from 'react'
import { BREAKFAST_EMOJIS } from '../utils/emoji'

// A favorite's icon and, on a tap, the app's breakfast emojis to change it (#244): the list only, no free text
export default function EmojiPicker({ value, onChange }) {
  const [open, setOpen] = useState(false)
  return (
    <div className="mb-2">
      <button
        type="button"
        className="flex cursor-pointer items-center gap-2 rounded-lg border border-line bg-surface px-2.5 py-1 text-xs text-fg-muted"
        onClick={() => setOpen(o => !o)}
        aria-expanded={open}
        title="Change this favorite's icon"
      >
        <span className="text-lg leading-none">{value}</span>
        Icon {open ? '▼' : '▲'}
      </button>
      {open && (
        <div className="mt-1.5 grid grid-cols-8 gap-1 rounded-lg border border-line bg-surface p-1.5" role="group" aria-label="Icons">
          {BREAKFAST_EMOJIS.map(e => (
            <button
              key={e}
              type="button"
              aria-label={`Icon ${e}`}
              aria-pressed={e === value}
              className={`flex h-8 cursor-pointer items-center justify-center rounded-md border-2 bg-transparent p-0 text-lg leading-none ${e === value ? 'border-accent' : 'border-transparent'}`}
              onClick={() => { onChange(e); setOpen(false) }}
            >
              {e}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
