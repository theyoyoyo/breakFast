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

// Header helpers like the Fridge's suggestions list: select all, and Delete all in red
export const headerHelpers = {
  display: 'flex',
  gap: 6,
}

export const helperBtn = {
  background: 'var(--surface2)',
  border: 'none',
  borderRadius: 6,
  color: 'var(--text)',
  width: 26,
  height: 22,
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  cursor: 'pointer',
  padding: 0,
}

export const clearAllBtn = {
  ...helperBtn,
  color: colors.danger,
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
  gap: 8,
}

// The checkbox and the name: a tap anywhere on them checks the item
export const rowLabel = {
  display: 'flex',
  alignItems: 'center',
  gap: 10,
  flex: 1,
  minWidth: 0,
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
  minWidth: 0,
  overflowWrap: 'anywhere',
  fontSize: 13,
  color: 'var(--text)',
  transition: 'all 0.15s',
}

// × removes an item, red like every remove (the Fridge's suggestions use the same)
export const removeBtn = {
  background: 'none',
  border: 'none',
  color: colors.danger,
  fontSize: 18,
  lineHeight: 1,
  cursor: 'pointer',
  padding: '0 4px',
  flexShrink: 0,
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

// Best before date, inline on a checked item's row
export const bbd = {
  display: 'flex',
  alignItems: 'center',
  gap: 4,
  flexShrink: 0,
}

export const bbdLabel = {
  fontSize: 11,
  color: 'var(--text-muted)',
}

export const bbdInput = {
  width: 118,
  background: 'var(--surface2)',
  border: '1px solid var(--border)',
  borderRadius: 6,
  padding: '3px 6px',
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
