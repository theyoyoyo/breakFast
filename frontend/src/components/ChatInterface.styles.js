export const container = {
  display: 'flex',
  flexDirection: 'column',
  height: '100%',
  background: 'var(--surface)',
  borderRadius: 'var(--radius)',
  overflow: 'hidden',
}

export const header = {
  padding: '16px 20px',
  borderBottom: '1px solid var(--border)',
  fontWeight: 600,
  fontSize: 16,
  color: 'var(--accent)',
  letterSpacing: '0.02em',
}

export const messages = {
  flex: 1,
  overflowY: 'auto',
  padding: '16px',
  display: 'flex',
  flexDirection: 'column',
  gap: 12,
}

export const bubble = (role) => ({
  maxWidth: '80%',
  alignSelf: role === 'user' ? 'flex-end' : 'flex-start',
  background: role === 'user' ? 'var(--accent2)' : 'var(--surface2)',
  color: 'var(--text)',
  borderRadius: role === 'user' ? '18px 18px 4px 18px' : '18px 18px 18px 4px',
  padding: '10px 14px',
  fontSize: 14,
  lineHeight: 1.6,
  whiteSpace: 'pre-wrap',
})

export const inputRow = {
  display: 'flex',
  gap: 8,
  padding: '12px 16px',
  borderTop: '1px solid var(--border)',
  background: 'var(--surface)',
}

export const input = {
  flex: 1,
  background: 'var(--surface2)',
  border: '1px solid var(--border)',
  borderRadius: 24,
  padding: '10px 16px',
  color: 'var(--text)',
  fontSize: 14,
  outline: 'none',
  resize: 'none',
  minHeight: 42,
  maxHeight: 120,
}

export const sendBtn = {
  background: 'var(--accent)',
  color: '#fff',
  border: 'none',
  borderRadius: 24,
  padding: '10px 18px',
  fontWeight: 600,
  fontSize: 14,
  transition: 'opacity 0.15s',
}

export const micBtn = (active) => ({
  background: active ? 'var(--accent2)' : 'var(--surface2)',
  color: 'var(--text)',
  border: '1px solid var(--border)',
  borderRadius: 24,
  padding: '10px 14px',
  fontSize: 16,
  transition: 'background 0.15s',
})

export const thinking = {
  alignSelf: 'flex-start',
  color: 'var(--text-muted)',
  fontSize: 13,
  padding: '6px 4px',
}

export const connStatus = {
  fontSize: 12,
  fontWeight: 400,
  color: 'var(--text-muted)',
}

export const suppMenuWrapper = {
  position: 'relative',
  alignSelf: 'flex-end',
}

export const suppToggleBtn = (active) => ({
  background: active ? 'var(--accent)' : 'var(--surface2)',
  color: active ? '#fff' : 'var(--text-muted)',
  border: '1px solid var(--border)',
  borderRadius: 12,
  padding: '6px 14px',
  fontSize: 12,
  fontWeight: 600,
  cursor: 'pointer',
  transition: 'background 0.15s, color 0.15s',
})

export const suppMenu = {
  position: 'absolute',
  bottom: '100%',
  left: 0,
  marginBottom: 6,
  background: 'var(--surface)',
  border: '1px solid var(--border)',
  borderRadius: 12,
  padding: '10px 12px',
  display: 'flex',
  flexDirection: 'column',
  gap: 6,
  minWidth: 180,
  boxShadow: '0 -4px 16px rgba(0,0,0,0.2)',
  zIndex: 10,
}

export const suppMenuLabel = {
  fontSize: 11,
  fontWeight: 700,
  textTransform: 'uppercase',
  color: 'var(--text-muted)',
  marginBottom: 2,
}

export const suppPill = (taken) => ({
  display: 'inline-flex',
  alignItems: 'center',
  gap: 4,
  padding: '6px 12px',
  borderRadius: 16,
  fontSize: 12,
  border: '1px solid var(--border)',
  background: taken ? 'var(--accent)' : 'var(--surface2)',
  color: taken ? '#fff' : 'var(--text-muted)',
  cursor: 'pointer',
  whiteSpace: 'nowrap',
  transition: 'background 0.15s, color 0.15s',
})

export const actionRow = {
  display: 'flex',
  alignItems: 'flex-end',
  justifyContent: 'space-between',
  gap: 8,
  padding: '6px 16px 0',
  background: 'var(--surface)',
}

export const decideBtn = (active) => ({
  background: active ? 'var(--accent)' : 'var(--surface2)',
  color: active ? '#fff' : 'var(--text)',
  border: '1px solid var(--border)',
  borderRadius: 20,
  padding: '20px 28px',
  fontSize: 42,
  lineHeight: 1,
  cursor: 'pointer',
  transition: 'background 0.15s, color 0.15s',
})

export const stopBtn = {
  background: 'var(--accent)',
  color: '#fff',
  border: 'none',
  borderRadius: 24,
  padding: '10px 18px',
  fontWeight: 600,
  fontSize: 14,
  transition: 'opacity 0.15s',
}

export const newSessionBtn = {
  background: 'none',
  border: '1px solid var(--border)',
  borderRadius: 8,
  padding: '4px 10px',
  fontSize: 12,
  color: 'var(--text-muted)',
  cursor: 'pointer',
  marginLeft: 'auto',
}
