import { useEffect, useId, useRef } from 'react'
import { createPortal } from 'react-dom'

const BUTTON = 'cursor-pointer rounded-lg px-4 py-2 text-sm'

/**
 * A pop-up "Are you sure?" window over the page: the question, then Cancel and the action (last,
 * like Confirm elsewhere; red with `danger`, for a delete). Cancel has the focus when it opens, so
 * a stray Enter doesn't delete; Tab stays inside, Esc, Cancel or a tap outside closes it, and the
 * focus goes back to what had it before.
 *
 * Props:
 *   open         — shows the window
 *   title        — its heading (also its accessible name)
 *   message      — the question
 *   confirmLabel — the action button's text ("Delete")
 *   danger       — true for a delete: the action button is red
 *   onConfirm    — the action
 *   onCancel     — closes the window
 *   notice       — true for a note with nothing to decide: only the action button (its OK), which
 *                  has the focus; Esc and a tap outside still close it
 */
export default function ConfirmDialog({
  open, title, message, confirmLabel, danger = false, notice = false, onConfirm, onCancel,
}) {
  const titleId = useId()
  const messageId = useId()
  const cancelRef = useRef(null)
  const confirmRef = useRef(null)
  const panelRef = useRef(null)
  const onCancelRef = useRef(onCancel)
  useEffect(() => { onCancelRef.current = onCancel }, [onCancel])

  useEffect(() => {
    if (!open) return undefined
    const opener = document.activeElement
    ;(cancelRef.current ?? confirmRef.current)?.focus()
    const handleKey = (e) => {
      if (e.key === 'Escape') {
        e.preventDefault()
        onCancelRef.current?.()
      } else if (e.key === 'Tab') {
        // Keep the focus on the window's own buttons
        const buttons = panelRef.current?.querySelectorAll('button') ?? []
        if (!buttons.length) return
        const first = buttons[0]
        const last = buttons[buttons.length - 1]
        if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus() }
        else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus() }
      }
    }
    document.addEventListener('keydown', handleKey)
    return () => {
      document.removeEventListener('keydown', handleKey)
      if (opener instanceof HTMLElement && opener.isConnected) opener.focus()
    }
  }, [open])

  if (!open) return null

  return createPortal(
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
      onClick={onCancel}
    >
      <div
        ref={panelRef}
        role="alertdialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={messageId}
        className="w-full max-w-sm rounded-2xl border border-solid border-line bg-surface p-5 text-fg shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 id={titleId} className="m-0 mb-2 text-base font-semibold">{title}</h2>
        <p id={messageId} className="m-0 mb-5 text-sm text-fg-muted">{message}</p>
        <div className="flex justify-end gap-2">
          {!notice && (
            <button
              ref={cancelRef}
              type="button"
              className={`${BUTTON} border border-solid border-line bg-transparent text-fg-muted`}
              onClick={onCancel}
            >
              Cancel
            </button>
          )}
          <button
            ref={confirmRef}
            type="button"
            className={`${BUTTON} border-0 font-semibold text-white ${danger ? 'bg-danger-strong' : 'bg-secondary'}`}
            onClick={onConfirm}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>,
    document.body,
  )
}
