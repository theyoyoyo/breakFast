import { secondaryColor, colors } from '../styles/common'

export const overlay = {
  position: 'fixed',
  inset: 0,
  background: 'rgba(0,0,0,0.5)',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  zIndex: 100,
}

export const panel = {
  background: 'var(--surface)',
  borderRadius: 12,
  width: '90%',
  maxWidth: 400,
  maxHeight: '80%',
  display: 'flex',
  flexDirection: 'column',
  overflow: 'hidden',
}

export const header = {
  display: 'flex',
  alignItems: 'center',
  gap: 8,
  padding: '14px 16px',
  borderBottom: '1px solid var(--border)',
  color: 'var(--text)',
}

export const title = {
  flex: 1,
  fontWeight: 700,
  fontSize: 14,
}

export const closeBtn = {
  background: 'none',
  border: 'none',
  color: 'var(--text-muted)',
  cursor: 'pointer',
  padding: '2px',
  display: 'flex',
  alignItems: 'center',
}

export const list = {
  flex: 1,
  overflowY: 'auto',
  padding: '4px 0',
}

export const row = {
  display: 'flex',
  alignItems: 'center',
  padding: '8px 16px',
  gap: 10,
  cursor: 'pointer',
}

export const checkbox = {
  accentColor: secondaryColor,
  width: 16,
  height: 16,
  cursor: 'pointer',
}

export const itemName = {
  flex: 1,
  fontSize: 13,
  color: 'var(--text)',
  transition: 'all 0.15s',
}

export const deleteBtn = {
  background: 'none',
  border: 'none',
  color: 'var(--text-muted)',
  padding: '3px',
  borderRadius: 4,
  opacity: 0.45,
  cursor: 'pointer',
  display: 'flex',
  alignItems: 'center',
}

export const addRow = {
  display: 'flex',
  gap: 6,
  padding: '8px 12px',
  borderTop: '1px solid var(--border)',
}

export const addInput = {
  flex: 1,
  background: 'var(--surface2)',
  border: '1px solid var(--border)',
  borderRadius: 8,
  padding: '6px 10px',
  color: 'var(--text)',
  fontSize: 13,
  outline: 'none',
}

export const addBtn = {
  background: secondaryColor,
  border: 'none',
  borderRadius: 8,
  color: '#fff',
  width: 32,
  height: 32,
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  cursor: 'pointer',
}

export const doneBtn = {
  margin: '8px 16px 12px',
  padding: '10px 16px',
  background: '#27ae60',
  color: '#fff',
  border: 'none',
  borderRadius: 8,
  fontSize: 13,
  fontWeight: 600,
  textAlign: 'center',
}

export const empty = {
  padding: 20,
  color: 'var(--text-muted)',
  fontSize: 13,
  textAlign: 'center',
}

export const expiryDateRow = {
  display: 'flex',
  alignItems: 'center',
  gap: 6,
  padding: '2px 16px 6px 42px',
}

export const expiryDateLabel = {
  fontSize: 11,
  color: 'var(--text-muted)',
}

export const expiryDateInput = {
  flex: 1,
  background: 'var(--surface2)',
  border: '1px solid var(--border)',
  borderRadius: 6,
  padding: '4px 8px',
  color: 'var(--text)',
  fontSize: 11,
  outline: 'none',
  colorScheme: 'dark',
}

export const error = {
  padding: '8px 16px',
  fontSize: 12,
  color: colors.error,
}
