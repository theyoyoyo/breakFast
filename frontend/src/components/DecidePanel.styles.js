import { secondaryColor, colors } from '../styles/common'

export const overlay = {
  position: 'fixed',
  inset: 0,
  background: 'rgba(0,0,0,0.5)',
  zIndex: 20,
  display: 'flex',
  flexDirection: 'column',
  justifyContent: 'flex-end',
  padding: 16,
}

export const panel = {
  background: 'var(--surface)',
  border: '1px solid var(--border)',
  borderRadius: 16,
  padding: '20px',
  boxShadow: '0 -8px 32px rgba(0,0,0,0.3)',
  overflowY: 'auto',
  flex: 1,
  display: 'flex',
  flexDirection: 'column',
}

export const panelHeader = {
  fontSize: 18,
  fontWeight: 700,
  color: 'var(--accent)',
  textAlign: 'center',
  marginBottom: 16,
  flexShrink: 0,
}

export const prepTimeLabel = {
  fontSize: 14,
}

export const prepTimeInput = {
  width: 40,
  background: 'var(--surface2)',
  border: '1px solid var(--border)',
  borderRadius: 6,
  padding: '4px 4px',
  color: 'var(--text)',
  fontSize: 13,
  textAlign: 'center',
  outline: 'none',
}

export const prepTimeUnit = {
  fontSize: 12,
  color: 'var(--text-muted)',
}

export const itemList = {
  display: 'flex',
  flexDirection: 'column',
  gap: 6,
  flex: 1,
  overflowY: 'auto',
}

export const itemRow = {
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  padding: '10px 12px',
  background: 'var(--surface2)',
  borderRadius: 10,
  fontSize: 15,
}

export const qtyGroup = {
  display: 'flex',
  alignItems: 'center',
  gap: 2,
  flexShrink: 0,
}

export const qtyInput = {
  width: 46,
  background: 'var(--surface)',
  border: '1px solid var(--border)',
  borderRadius: 6,
  padding: '4px 4px',
  color: 'var(--text)',
  fontSize: 14,
  textAlign: 'center',
  outline: 'none',
}

export const arrowBtn = {
  background: 'none',
  border: '1px solid var(--border)',
  borderRadius: 4,
  cursor: 'pointer',
  fontSize: 10,
  padding: '2px 5px',
  color: 'var(--text-muted)',
  lineHeight: 1,
}

export const unitLabel = {
  fontSize: 13,
  color: 'var(--text-muted)',
  flexShrink: 0,
  minWidth: 30,
  marginRight: 8,
}

export const itemText = {
  flex: 1,
  color: 'var(--text)',
}

export const itemActions = {
  display: 'flex',
  gap: 4,
  flexShrink: 0,
}

export const deleteBtn = {
  background: 'none',
  border: 'none',
  cursor: 'pointer',
  fontSize: 18,
  padding: '4px 6px',
}

export const addRow = {
  display: 'flex',
  gap: 8,
  marginTop: 12,
  flexShrink: 0,
}

export const addInput = {
  flex: 1,
  background: 'var(--surface2)',
  border: '1px solid var(--border)',
  borderRadius: 10,
  padding: '10px 14px',
  color: 'var(--text)',
  fontSize: 15,
  outline: 'none',
}

export const addBtn = {
  background: 'var(--surface2)',
  border: '1px solid var(--border)',
  borderRadius: 10,
  padding: '10px 16px',
  color: 'var(--text)',
  fontSize: 18,
  fontWeight: 600,
  cursor: 'pointer',
}

export const actions = {
  display: 'flex',
  justifyContent: 'space-between',
  marginTop: 16,
  gap: 10,
  flexShrink: 0,
}

export const backBtn = {
  background: 'var(--surface2)',
  border: '1px solid var(--border)',
  borderRadius: 10,
  padding: '12px 24px',
  color: 'var(--text-muted)',
  fontSize: 15,
  cursor: 'pointer',
}

export const confirmBtn = {
  background: secondaryColor,
  border: 'none',
  borderRadius: 10,
  padding: '12px 24px',
  color: '#fff',
  fontSize: 15,
  fontWeight: 600,
  cursor: 'pointer',
}

export const ateOutBtn = {
  ...confirmBtn,
  padding: '12px 16px',
  background: 'transparent',
  border: `1px solid ${secondaryColor}`,
  color: 'var(--text)',
}

// Ate out has nothing to do when no item is missing
export const ateOutBtnIdle = {
  ...ateOutBtn,
  opacity: 0.45,
  cursor: 'default',
}

export const confirmBtnBlocked = {
  ...confirmBtn,
  opacity: 0.45,
  cursor: 'not-allowed',
}

export const missingNote = {
  marginTop: 10,
  fontSize: 13,
  lineHeight: 1.5,
  color: colors.goldText,
}

export const rateRow = {
  display: 'flex',
  flexDirection: 'column',
  gap: 6,
  padding: '10px 12px',
  background: 'var(--surface2)',
  borderRadius: 10,
}

export const rateLabel = {
  fontSize: 15,
  fontWeight: 600,
  color: 'var(--text)',
}

