import { colors } from '../styles/common'

export const overlay = {
  position: 'fixed',
  inset: 0,
  background: 'rgba(0,0,0,0.5)',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  zIndex: 100,
}

export const panel = {
  background: 'var(--surface)',
  borderRadius: 12,
  width: '90%',
  maxWidth: 400,
  maxHeight: '80%',
  display: 'flex',
  flexDirection: 'column',
  overflow: 'hidden',
}

export const header = {
  display: 'flex',
  alignItems: 'center',
  gap: 8,
  padding: '14px 16px',
  borderBottom: '1px solid var(--border)',
  color: 'var(--text)',
}

export const heartIcon = {
  fontSize: 16,
  lineHeight: 1,
}

export const title = {
  flex: 1,
  fontWeight: 700,
  fontSize: 14,
}

export const addAllBtn = {
  background: 'rgba(142, 68, 173, 0.15)',
  border: '1px solid rgba(142, 68, 173, 0.3)',
  color: 'var(--c-purple)',
  borderRadius: 6,
  padding: '4px 10px',
  fontSize: 11,
  fontWeight: 600,
  cursor: 'pointer',
  whiteSpace: 'nowrap',
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

export const list = {
  flex: 1,
  overflowY: 'auto',
  padding: '4px 0',
}

export const row = {
  display: 'flex',
  alignItems: 'center',
  padding: '8px 16px',
  gap: 10,
}

export const itemName = {
  flex: 1,
  fontSize: 13,
  color: 'var(--text)',
}

export const shopBtn = {
  background: 'none',
  border: 'none',
  color: 'var(--text-muted)',
  padding: '3px',
  borderRadius: 4,
  cursor: 'pointer',
  display: 'flex',
  alignItems: 'center',
  opacity: 0.6,
  transition: 'opacity 0.15s',
}

export const shopBtnDone = {
  background: 'none',
  border: 'none',
  color: 'var(--c-green)',
  padding: '3px',
  borderRadius: 4,
  display: 'flex',
  alignItems: 'center',
  opacity: 0.7,
  cursor: 'default',
  fontSize: 11,
  fontWeight: 600,
}

export const removeBtn = {
  background: 'none',
  border: 'none',
  color: 'var(--text-muted)',
  padding: '3px',
  borderRadius: 4,
  opacity: 0.35,
  cursor: 'pointer',
  display: 'flex',
  alignItems: 'center',
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
