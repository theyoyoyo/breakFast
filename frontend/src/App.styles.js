export const app = {
  display: 'grid',
  height: '100vh',
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

export const tab = (active) => ({
  padding: '8px 18px',
  background: active ? 'var(--surface2)' : 'none',
  border: 'none',
  borderRadius: '8px 8px 0 0',
  color: active ? 'var(--accent)' : 'var(--text-muted)',
  fontWeight: active ? 700 : 400,
  fontSize: 14,
  cursor: 'pointer',
  transition: 'color 0.15s',
})

export const main = {
  display: 'grid',
  gridTemplateColumns: '1fr 320px',
  gap: 12,
  padding: 12,
  overflow: 'hidden',
  height: '100%',
}

export const mainFull = {
  padding: 12,
  height: '100%',
  overflow: 'hidden',
}

export const sidebar = {
  display: 'flex',
  flexDirection: 'column',
  gap: 12,
  overflowY: 'auto',
}

export const userInfo = {
  marginLeft: 'auto',
  display: 'flex',
  alignItems: 'center',
  gap: 8,
  fontSize: 13,
  color: 'var(--text-muted)',
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
