/**
 * Today's supplements in "Today I ate": a 💊 button that reveals them as chips below it.
 * Daily ones start ticked and occasional ones not (the server sends today's state as taken_today);
 * a tap flips one and the caller saves it at once. The caller owns `open`, so a tap elsewhere in
 * the panel can close the list while Confirm keeps it (see DecidePanel).
 *
 * Props:
 *   open, onOpenChange(open)       — whether the chips show
 *   supplements                    — [{ id, name, contents, frequency, taken_today }]
 *   onToggle(id, takenNow)         — flip one, saved at once
 *   containerRef                   — the button and the list, for the panel's "tap elsewhere" check
 */
export default function TodaySupplements({ open, onOpenChange, supplements, onToggle, containerRef }) {
  return (
    <div ref={containerRef} className="absolute right-0 top-1/2 -translate-y-1/2">
      <button
        type="button"
        className={`flex h-10 w-10 items-center justify-center rounded-full border-0 p-0 text-2xl leading-none transition-transform active:scale-[0.92] ${open ? 'bg-surface-2' : 'bg-transparent'}`}
        onClick={() => onOpenChange(!open)}
        title="Supplements"
        aria-label="Supplements"
        aria-expanded={open}
      >
        💊
      </button>
      {open && (
        <div
          className="absolute right-0 top-full z-20 mt-2 flex w-64 max-w-[80vw] flex-wrap justify-end gap-1.5 rounded-xl border border-line bg-surface p-3 text-left text-sm font-normal shadow-lg motion-safe:animate-pop"
          style={{ transformOrigin: 'top right' }}
          role="group"
          aria-label="Today's supplements"
        >
          {supplements.length === 0 ? (
            <span className="w-full text-center text-xs text-fg-muted">None added — Settings → Supplements</span>
          ) : supplements.map(sup => {
            const taken = !!sup.taken_today
            return (
              <button
                key={sup.id}
                type="button"
                className={`rounded-full border px-3 py-1.5 text-xs transition-colors active:scale-[0.95] ${taken
                  ? 'border-transparent bg-secondary font-semibold text-white'
                  : 'border-line bg-surface-2 text-fg-muted'}`}
                onClick={() => onToggle(sup.id, taken)}
                title={sup.contents || sup.name}
                aria-pressed={taken}
              >
                {taken ? '✓ ' : ''}{sup.name}
              </button>
            )
          })}
        </div>
      )}
    </div>
  )
}
