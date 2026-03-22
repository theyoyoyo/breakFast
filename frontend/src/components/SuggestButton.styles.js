export const wrapper = {
  position: 'relative',
  display: 'inline-flex',
  flexDirection: 'column',
  alignItems: 'center',
  marginLeft: 'auto',
}

export const button = (disabled) => ({
  display: 'inline-flex',
  alignItems: 'center',
  justifyContent: 'center',
  background: 'none',
  border: '1px solid var(--border)',
  borderRadius: 16,
  padding: '8px 20px',
  cursor: disabled ? 'not-allowed' : 'pointer',
  opacity: disabled ? 0.4 : 1,
  transition: 'opacity 0.15s',
  userSelect: 'none',
  touchAction: 'none',
})

export const logo = {
  height: 168,
  width: 'auto',
  display: 'block',
  pointerEvents: 'none',
}

export const panel = {
  position: 'absolute',
  bottom: '100%',
  right: 0,
  marginBottom: 6,
  background: 'var(--surface)',
  border: '1px solid var(--border)',
  borderRadius: 12,
  padding: '8px',
  display: 'flex',
  flexDirection: 'column',
  gap: 6,
  minWidth: 170,
  boxShadow: '0 -4px 16px rgba(0,0,0,0.2)',
  zIndex: 10,
}

export const modeBtn = {
  display: 'flex',
  alignItems: 'center',
  gap: 8,
  padding: '10px 14px',
  background: 'var(--surface2)',
  border: '1px solid var(--border)',
  borderRadius: 10,
  color: 'var(--text)',
  fontSize: 13,
  fontWeight: 500,
  cursor: 'pointer',
  transition: 'background 0.15s',
  whiteSpace: 'nowrap',
}
