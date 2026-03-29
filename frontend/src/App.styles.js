export const app = {
  display: 'grid',
  height: '100dvh',
  gridTemplateRows: 'auto 1fr',
  maxWidth: 1200,
  margin: '0 auto',
  padding: 0,
}

export const nav = {
  display: 'flex',
  gap: 4,
  padding: '12px 16px 0',
  borderBottom: '1px solid var(--border)',
  background: 'var(--surface)',
  alignItems: 'center',
}

export const tab = (active, narrow) => ({
  padding: narrow ? '8px 10px' : '8px 18px',
  background: active ? 'var(--surface2)' : 'none',
  border: 'none',
  borderRadius: '8px 8px 0 0',
  color: active ? 'var(--accent)' : 'var(--text-muted)',
  fontWeight: active ? 700 : 400,
  fontSize: 14,
  cursor: 'pointer',
  transition: 'color 0.15s',
})

export const mainFull = {
  padding: 12,
  height: '100%',
  overflow: 'hidden',
}

export const userInfo = {
  marginLeft: 'auto',
  display: 'flex',
  alignItems: 'center',
  gap: 8,
  fontSize: 13,
  color: 'var(--text-muted)',
}

export const offlineBanner = {
  background: '#e74c3c',
  color: '#fff',
  textAlign: 'center',
  padding: '6px 12px',
  fontSize: 13,
  fontWeight: 600,
}

export const logoutBtn = {
  background: 'none',
  border: '1px solid var(--border)',
  borderRadius: 8,
  padding: '4px 10px',
  color: 'var(--text-muted)',
  fontSize: 12,
  cursor: 'pointer',
}
