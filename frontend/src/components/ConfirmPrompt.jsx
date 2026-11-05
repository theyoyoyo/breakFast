import * as s from './ConfirmPrompt.styles'

/**
 * An inline "Are you sure?" box for an action that can't be undone in one tap: the question,
 * then Cancel and the action (last, like Confirm elsewhere). A delete's action is red.
 *
 * Props:
 *   label        — the box's accessible name
 *   message      — the question
 *   confirmLabel — the action button's text ("Delete", "Allow")
 *   danger       — true for a delete: the action button is red
 *   onConfirm    — the action
 *   onCancel     — closes the box
 */
export default function ConfirmPrompt({ label, message, confirmLabel, danger = false, onConfirm, onCancel }) {
  return (
    <div style={s.prompt} role="alertdialog" aria-label={label} onClick={(e) => e.stopPropagation()}>
      <span style={s.text}>{message}</span>
      <button style={s.cancelBtn} onClick={onCancel}>Cancel</button>
      <button style={danger ? s.dangerBtn : s.confirmBtn} onClick={onConfirm}>{confirmLabel}</button>
    </div>
  )
}
