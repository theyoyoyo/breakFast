import { secondaryColor } from '../styles/common'

export const container = {
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'center',
  justifyContent: 'center',
  height: '100dvh',
  background: 'var(--bg)',
  gap: 24,
}

export const form = {
  display: 'flex',
  flexDirection: 'column',
  gap: 12,
  width: 280,
}

export const input = {
  background: 'var(--surface2)',
  border: '1px solid var(--border)',
  borderRadius: 12,
  padding: '12px 16px',
  color: 'var(--text)',
  fontSize: 16,
  outline: 'none',
}

export const btn = {
  background: secondaryColor,
  color: '#fff',
  border: 'none',
  borderRadius: 12,
  padding: '12px 18px',
  fontWeight: 600,
  fontSize: 16,
  cursor: 'pointer',
  transition: 'opacity 0.15s',
}

// Information, not an error: muted, so it reads calmly above the form
export const note = {
  color: 'var(--text-muted)',
  fontSize: 14,
  textAlign: 'center',
}

export const error = {
  color: '#e74c3c',
  fontSize: 14,
  textAlign: 'center',
}
