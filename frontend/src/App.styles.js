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

// Logged-in user: a chip with an initial avatar in the theme's button color (avatar only on phones)
export const userChip = (narrow) => ({
  display: 'flex',
  alignItems: 'center',
  gap: 6,
  padding: narrow ? 2 : '2px 10px 2px 2px',
  borderRadius: 999,
  background: 'var(--surface2)',
  border: '1px solid var(--border)',
})

export const userAvatar = {
  width: 22,
  height: 22,
  borderRadius: '50%',
  background: 'var(--secondary)',
  color: '#fff',
  fontSize: 12,
  fontWeight: 700,
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  flexShrink: 0,
}

export const userName = {
  color: 'var(--text)',
  fontWeight: 600,
  fontSize: 13,
  maxWidth: 120,
  overflow: 'hidden',
  textOverflow: 'ellipsis',
  whiteSpace: 'nowrap',
}

export const offlineBanner = {
  background: '#e74c3c',
  color: '#fff',
  textAlign: 'center',
  padding: '6px 12px',
  fontSize: 13,
  fontWeight: 600,
}

// Quiet by default; turns soft red on hover (.logout-btn:hover in index.css)
export const logoutBtn = {
  background: 'none',
  border: '1px solid var(--border)',
  borderRadius: 8,
  padding: '4px 10px',
  color: 'var(--text-muted)',
  fontSize: 12,
  cursor: 'pointer',
  transition: 'background 0.15s, color 0.15s, border-color 0.15s',
}
