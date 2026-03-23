import { secondaryColor } from '../styles/common'

// --- Inline block in chat ---

export const blockRow = {
  display: 'flex',
  alignItems: 'center',
  gap: 8,
  alignSelf: 'flex-end',
  maxWidth: '80%',
  minWidth: 0,
  overflow: 'hidden',
}

export const checkbox = (checked) => ({
  background: 'none',
  border: 'none',
  fontSize: 22,
  cursor: 'pointer',
  color: checked ? 'var(--accent)' : 'var(--text-muted)',
  padding: 0,
  lineHeight: 1,
  flexShrink: 0,
})

export const block = {
  display: 'flex',
  alignItems: 'center',
  gap: 8,
  background: 'var(--surface2)',
  border: '1px solid var(--border)',
  borderRadius: 12,
  padding: '10px 14px',
  cursor: 'pointer',
  transition: 'border-color 0.15s',
  flex: 1,
  minWidth: 0,
  overflow: 'hidden',
}

export const blockIcon = {
  fontSize: 18,
  flexShrink: 0,
}

export const blockText = {
  fontSize: 13,
  color: 'var(--text)',
  flex: 1,
  minWidth: 0,
  overflowWrap: 'break-word',
  wordBreak: 'break-word',
}

export const analyzeBtn = (analyzing) => ({
  background: 'none',
  border: 'none',
  fontSize: 20,
  cursor: analyzing ? 'default' : 'pointer',
  opacity: analyzing ? 0.5 : 1,
  padding: '2px 4px',
  flexShrink: 0,
  transition: 'opacity 0.15s',
})

export const prepBadge = {
  fontSize: 11,
  color: 'var(--text-muted)',
  background: 'var(--surface)',
  borderRadius: 8,
  padding: '2px 8px',
  flexShrink: 0,
  whiteSpace: 'nowrap',
}

export const mealId = {
  fontSize: 9,
  color: 'var(--text-muted)',
  opacity: 0.5,
  flexShrink: 0,
  whiteSpace: 'nowrap',
}

// --- Overlay panel (same style as DecidePanel) ---

export const overlay = {
  position: 'fixed',
  inset: 0,
  background: 'rgba(0,0,0,0.5)',
  zIndex: 30,
  display: 'flex',
  flexDirection: 'column',
  justifyContent: 'center',
  padding: 16,
}

export const panel = {
  background: 'var(--surface)',
  border: '1px solid var(--border)',
  borderRadius: 16,
  padding: '20px',
  boxShadow: '0 8px 32px rgba(0,0,0,0.3)',
  overflowY: 'auto',
  maxHeight: '80vh',
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

export const cancelBtn = {
  background: 'var(--surface2)',
  border: '1px solid var(--border)',
  borderRadius: 10,
  padding: '12px 24px',
  color: 'var(--text-muted)',
  fontSize: 15,
  cursor: 'pointer',
}

export const favBtn = (isFav) => ({
  background: 'none',
  border: '1px solid var(--border)',
  borderRadius: 10,
  padding: '10px 16px',
  fontSize: 20,
  cursor: 'pointer',
  opacity: isFav ? 1 : 0.4,
  transition: 'opacity 0.15s',
})

export const saveBtn = {
  background: secondaryColor,
  border: 'none',
  borderRadius: 10,
  padding: '12px 24px',
  color: '#fff',
  fontSize: 15,
  fontWeight: 600,
  cursor: 'pointer',
}
