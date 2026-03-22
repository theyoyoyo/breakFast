// Shared styles used across multiple components

// Secondary button color — dark orange-red, used for all action buttons
export const secondaryColor = '#c4533e'

export const panelContainer = {
  background: 'var(--surface)',
  borderRadius: 'var(--radius)',
  display: 'flex',
  flexDirection: 'column',
  height: '100%',
  overflow: 'hidden',
}

export const panelHeader = {
  padding: '14px 16px',
  fontWeight: 700,
  fontSize: 13,
  textTransform: 'uppercase',
  letterSpacing: '0.08em',
  color: 'var(--text-muted)',
  borderBottom: '1px solid var(--border)',
}

export const panelBody = {
  flex: 1,
  overflowY: 'auto',
  padding: '12px 16px',
  display: 'flex',
  flexDirection: 'column',
  gap: 20,
}

export const section = {
  display: 'flex',
  flexDirection: 'column',
  gap: 8,
}

export const sectionLabel = {
  fontSize: 11,
  fontWeight: 700,
  textTransform: 'uppercase',
  letterSpacing: '0.08em',
  color: 'var(--text-muted)',
}

export const input = {
  flex: 1,
  background: 'var(--surface2)',
  border: '1px solid var(--border)',
  borderRadius: 8,
  padding: '6px 10px',
  color: 'var(--text)',
  fontSize: 12,
  outline: 'none',
}

export const addRow = {
  display: 'flex',
  gap: 6,
}

export const addBtn = {
  background: secondaryColor,
  border: 'none',
  borderRadius: 8,
  color: '#fff',
  fontWeight: 700,
  fontSize: 16,
  width: 28,
  height: 28,
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
}

export const tagX = {
  background: 'none',
  border: 'none',
  color: 'var(--text-muted)',
  fontSize: 14,
  cursor: 'pointer',
  padding: 0,
  lineHeight: 1,
}

export const empty = {
  fontSize: 12,
  color: 'var(--text-muted)',
  fontStyle: 'italic',
}

export const error = {
  padding: '8px 0',
  fontSize: 12,
  color: '#e76f51',
}

export const select = {
  background: 'var(--surface2)',
  border: '1px solid var(--border)',
  borderRadius: 8,
  padding: '6px 10px',
  color: 'var(--text)',
  fontSize: 12,
  outline: 'none',
}
