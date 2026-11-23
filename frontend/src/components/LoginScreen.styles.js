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

// The PIN box with its show/hide button inside, at the right
export const pinField = {
  position: 'relative',
  display: 'flex',
}

export const pinInput = {
  flex: 1,
  minWidth: 0,
  paddingRight: 44,
}

export const revealBtn = {
  position: 'absolute',
  right: 6,
  top: '50%',
  transform: 'translateY(-50%)',
  width: 34,
  height: 34,
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  background: 'none',
  border: 'none',
  borderRadius: 8,
  color: 'var(--text-muted)',
  cursor: 'pointer',
}

// Information, not an error: a calm box the width of the form, so it reads as part of it
export const note = {
  background: 'var(--surface2)',
  border: '1px solid var(--border)',
  borderRadius: 12,
  padding: '10px 14px',
  color: 'var(--text-muted)',
  fontSize: 14,
  lineHeight: 1.4,
  textAlign: 'center',
}

export const error = {
  color: 'var(--c-red)',
  fontSize: 14,
  textAlign: 'center',
}
