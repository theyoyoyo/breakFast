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
})

export const logo = {
  height: 168,
  width: 'auto',
  display: 'block',
}
