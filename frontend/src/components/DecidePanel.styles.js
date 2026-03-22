export const panel = {
  position: 'absolute',
  bottom: '100%',
  left: 0,
  right: 0,
  marginBottom: 6,
  background: 'var(--surface)',
  border: '1px solid var(--border)',
  borderRadius: 12,
  padding: '12px',
  boxShadow: '0 -4px 16px rgba(0,0,0,0.2)',
  zIndex: 10,
  maxHeight: 360,
  overflowY: 'auto',
}

export const panelHeader = {
  fontSize: 14,
  fontWeight: 600,
  color: 'var(--accent)',
  marginBottom: 10,
}

export const itemList = {
  display: 'flex',
  flexDirection: 'column',
  gap: 4,
}

export const itemRow = {
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  padding: '6px 8px',
  background: 'var(--surface2)',
  borderRadius: 8,
  fontSize: 13,
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

export const editBtn = {
  background: 'none',
  border: 'none',
  cursor: 'pointer',
  fontSize: 14,
  padding: '2px 4px',
}

export const deleteBtn = {
  background: 'none',
  border: 'none',
  cursor: 'pointer',
  fontSize: 14,
  padding: '2px 4px',
}

export const editInput = {
  flex: 1,
  background: 'var(--surface)',
  border: '1px solid var(--accent)',
  borderRadius: 6,
  padding: '4px 8px',
  color: 'var(--text)',
  fontSize: 13,
  outline: 'none',
}

export const addRow = {
  display: 'flex',
  gap: 6,
  marginTop: 8,
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
  background: 'var(--surface2)',
  border: '1px solid var(--border)',
  borderRadius: 8,
  padding: '6px 12px',
  color: 'var(--text)',
  fontSize: 14,
  fontWeight: 600,
  cursor: 'pointer',
}

export const actions = {
  display: 'flex',
  justifyContent: 'space-between',
  marginTop: 10,
  gap: 8,
}

export const cancelBtn = {
  background: 'var(--surface2)',
  border: '1px solid var(--border)',
  borderRadius: 8,
  padding: '8px 16px',
  color: 'var(--text-muted)',
  fontSize: 13,
  cursor: 'pointer',
}

export const backBtn = {
  background: 'var(--surface2)',
  border: '1px solid var(--border)',
  borderRadius: 8,
  padding: '8px 16px',
  color: 'var(--text-muted)',
  fontSize: 13,
  cursor: 'pointer',
}

export const confirmBtn = {
  background: 'var(--accent)',
  border: 'none',
  borderRadius: 8,
  padding: '8px 16px',
  color: '#fff',
  fontSize: 13,
  fontWeight: 600,
  cursor: 'pointer',
}

export const rateRow = {
  display: 'flex',
  alignItems: 'center',
  gap: 8,
  padding: '6px 8px',
  background: 'var(--surface2)',
  borderRadius: 8,
}

export const rateLabel = {
  flex: 1,
  fontSize: 13,
  color: 'var(--text)',
}

export const slider = {
  width: 100,
  accentColor: 'var(--accent)',
}

export const rateValue = {
  fontSize: 13,
  fontWeight: 600,
  color: 'var(--accent)',
  minWidth: 20,
  textAlign: 'center',
}
