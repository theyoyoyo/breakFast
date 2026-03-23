import { secondaryColor } from '../styles/common'

export const overlay = {
  position: 'absolute',
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
  marginBottom: 16,
  flexShrink: 0,
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

export const qtyInput = {
  width: 52,
  background: 'var(--surface)',
  border: '1px solid var(--border)',
  borderRadius: 6,
  padding: '4px 6px',
  color: 'var(--text)',
  fontSize: 14,
  textAlign: 'center',
  outline: 'none',
  flexShrink: 0,
  marginRight: 4,
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
  cursor: 'pointer',
}

export const itemActions = {
  display: 'flex',
  gap: 4,
  flexShrink: 0,
}

export const editBtn = {
  background: 'none',
  border: 'none',
  cursor: 'pointer',
  fontSize: 18,
  padding: '4px 6px',
}

export const deleteBtn = {
  background: 'none',
  border: 'none',
  cursor: 'pointer',
  fontSize: 18,
  padding: '4px 6px',
}

export const editInput = {
  flex: 1,
  background: 'var(--surface)',
  border: '1px solid var(--accent)',
  borderRadius: 8,
  padding: '8px 12px',
  color: 'var(--text)',
  fontSize: 15,
  outline: 'none',
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

export const cancelBtn = {
  background: 'var(--surface2)',
  border: '1px solid var(--border)',
  borderRadius: 10,
  padding: '12px 24px',
  color: 'var(--text-muted)',
  fontSize: 15,
  cursor: 'pointer',
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

export const starsRow = {
  display: 'flex',
  justifyContent: 'space-between',
}

export const starCell = {
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'center',
  cursor: 'pointer',
  flex: 1,
  userSelect: 'none',
}

export const starNum = {
  fontSize: 10,
  color: 'var(--text-muted)',
  marginBottom: 2,
}

export const star = (lit) => ({
  fontSize: 22,
  color: lit ? '#f5a623' : 'var(--border)',
  transition: 'color 0.1s',
})
