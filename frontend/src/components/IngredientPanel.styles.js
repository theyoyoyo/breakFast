import { panelContainer, panelHeader, secondaryColor, colors } from '../styles/common'

export const container = panelContainer

export const header = panelHeader

export const list = {
  flex: 1,
  overflowY: 'auto',
  padding: '8px 0',
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

export const deleteBtn = {
  background: 'none',
  border: 'none',
  color: 'var(--text-muted)',
  fontSize: 14,
  padding: '2px 4px',
  borderRadius: 4,
  opacity: 0.5,
  transition: 'opacity 0.1s',
  cursor: 'pointer',
}

export const addRow = {
  display: 'flex',
  gap: 6,
  padding: '10px 12px',
  borderTop: '1px solid var(--border)',
}

export const input = {
  flex: 1,
  background: 'var(--surface2)',
  border: '1px solid var(--border)',
  borderRadius: 8,
  padding: '6px 10px',
  color: 'var(--text)',
  fontSize: 13,
  outline: 'none',
}

export const dateInput = {
  width: 110,
  background: 'var(--surface2)',
  border: '1px solid var(--border)',
  borderRadius: 8,
  padding: '6px 6px',
  color: 'var(--text)',
  fontSize: 11,
  outline: 'none',
}

export const addBtn = {
  background: secondaryColor,
  border: 'none',
  borderRadius: 8,
  color: '#fff',
  fontWeight: 700,
  fontSize: 18,
  width: 32,
  height: 32,
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  cursor: 'pointer',
}

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

export const expiryWidgetCovered = {
  color: 'var(--text-muted)',
  background: 'rgba(46, 204, 113, 0.08)',
  cursor: 'default',
  fontWeight: 400,
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
  padding: '4px 16px 8px',
  fontSize: 14,
  fontWeight: 600,
  color: 'var(--text)',
}

export const closeBtn = {
  background: 'none',
  border: 'none',
  fontSize: 18,
  color: 'var(--text-muted)',
  cursor: 'pointer',
  padding: '0 4px',
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
  gap: 8,
}

export const thrownBtn = {
  margin: '8px 16px',
  padding: '8px 16px',
  background: '#e74c3c',
  color: '#fff',
  border: 'none',
  borderRadius: 8,
  fontSize: 13,
  fontWeight: 600,
  cursor: 'pointer',
  textAlign: 'center',
}
