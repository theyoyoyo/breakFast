import { panelContainer, secondaryColor, colors } from '../styles/common'

export const container = panelContainer

// ---------------------------------------------------------------------------
// Header with inline add button
// ---------------------------------------------------------------------------

export const headerRow = {
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  padding: '14px 16px',
  borderBottom: '1px solid var(--border)',
}

export const headerText = {
  fontWeight: 700,
  fontSize: 13,
  textTransform: 'uppercase',
  letterSpacing: '0.08em',
  color: 'var(--text-muted)',
}

export const headerAddBtn = {
  background: secondaryColor,
  border: 'none',
  borderRadius: 6,
  color: '#fff',
  width: 26,
  height: 26,
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  cursor: 'pointer',
}

// ---------------------------------------------------------------------------
// Add panel (opens below header)
// ---------------------------------------------------------------------------

export const addPanel = {
  padding: '10px 16px',
  borderBottom: '1px solid var(--border)',
  background: 'var(--surface2)',
  display: 'flex',
  flexDirection: 'column',
  gap: 8,
}

export const addInput = {
  background: 'var(--surface)',
  border: '1px solid var(--border)',
  borderRadius: 8,
  padding: '8px 10px',
  color: 'var(--text)',
  fontSize: 13,
  outline: 'none',
  width: '100%',
  boxSizing: 'border-box',
}

export const addPanelRow = {
  display: 'flex',
  gap: 8,
  alignItems: 'center',
}

export const addDateInput = {
  flex: 1,
  background: 'var(--surface)',
  border: '1px solid var(--border)',
  borderRadius: 8,
  padding: '7px 10px',
  color: 'var(--text)',
  fontSize: 12,
  outline: 'none',
  colorScheme: 'dark',
}

export const addPanelBtn = {
  background: secondaryColor,
  border: 'none',
  borderRadius: 8,
  color: '#fff',
  fontWeight: 600,
  fontSize: 13,
  padding: '7px 18px',
  cursor: 'pointer',
}

// ---------------------------------------------------------------------------
// Ingredient list
// ---------------------------------------------------------------------------

export const list = {
  flex: 1,
  overflowY: 'auto',
  padding: '4px 0',
}

export const row = {
  display: 'flex',
  alignItems: 'center',
  padding: '6px 16px',
  gap: 8,
}

export const name = {
  flex: 1,
  fontSize: 13,
  color: 'var(--text)',
}

export const expiryBadge = {
  fontSize: 11,
  color: 'var(--text-muted)',
  whiteSpace: 'nowrap',
}

export const iconBtn = {
  background: 'none',
  border: 'none',
  color: 'var(--text-muted)',
  padding: '3px',
  borderRadius: 4,
  opacity: 0.45,
  transition: 'opacity 0.1s',
  cursor: 'pointer',
  display: 'flex',
  alignItems: 'center',
}

// ---------------------------------------------------------------------------
// Edit row (inline)
// ---------------------------------------------------------------------------

export const editRow = {
  display: 'flex',
  alignItems: 'center',
  padding: '4px 12px',
  gap: 6,
  background: 'var(--surface2)',
}

export const editInput = {
  flex: 1,
  background: 'var(--surface)',
  border: '1px solid var(--border)',
  borderRadius: 6,
  padding: '5px 8px',
  color: 'var(--text)',
  fontSize: 13,
  outline: 'none',
  minWidth: 0,
}

export const editDateInput = {
  width: 120,
  background: 'var(--surface)',
  border: '1px solid var(--border)',
  borderRadius: 6,
  padding: '5px 6px',
  color: 'var(--text)',
  fontSize: 11,
  outline: 'none',
  colorScheme: 'dark',
}

export const editSaveBtn = {
  background: secondaryColor,
  border: 'none',
  borderRadius: 6,
  color: '#fff',
  fontWeight: 600,
  fontSize: 12,
  padding: '5px 12px',
  cursor: 'pointer',
  whiteSpace: 'nowrap',
}

export const editCancelBtn = {
  background: 'none',
  border: 'none',
  color: 'var(--text-muted)',
  padding: '3px',
  cursor: 'pointer',
  display: 'flex',
  alignItems: 'center',
}

// ---------------------------------------------------------------------------
// Empty / error states
// ---------------------------------------------------------------------------

export const empty = {
  padding: 20,
  color: 'var(--text-muted)',
  fontSize: 13,
  textAlign: 'center',
}

export const error = {
  padding: '8px 16px',
  fontSize: 12,
  color: colors.error,
}

// ---------------------------------------------------------------------------
// Expiry widget + panel
// ---------------------------------------------------------------------------

export const expiryWidget = {
  padding: '8px 16px',
  fontSize: 13,
  color: '#e67e22',
  background: 'rgba(230, 126, 34, 0.08)',
  borderTop: '1px solid var(--border)',
  cursor: 'pointer',
  textAlign: 'center',
  fontWeight: 600,
  transition: 'all 0.2s',
}

export const expiryPanel = {
  borderTop: '1px solid var(--border)',
  background: 'var(--surface)',
  padding: '8px 0',
  maxHeight: '40%',
  display: 'flex',
  flexDirection: 'column',
}

export const expiryPanelHeader = {
  display: 'flex',
  justifyContent: 'space-between',
  alignItems: 'center',
  padding: '4px 12px 8px',
}

export const expiryPanelTitle = {
  fontSize: 14,
  fontWeight: 600,
  color: 'var(--text)',
  textAlign: 'center',
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

export const expiryPanelList = {
  flex: 1,
  overflowY: 'auto',
  padding: '0 8px',
}

export const expiryRow = {
  display: 'flex',
  alignItems: 'center',
  padding: '6px 8px',
  gap: 10,
  cursor: 'pointer',
}

export const checkbox = {
  accentColor: secondaryColor,
  width: 16,
  height: 16,
  cursor: 'pointer',
}

export const discardBtn = {
  margin: '8px 16px',
  padding: '8px 16px',
  background: '#e74c3c',
  color: '#fff',
  border: 'none',
  borderRadius: 8,
  fontSize: 13,
  fontWeight: 600,
  textAlign: 'center',
}
