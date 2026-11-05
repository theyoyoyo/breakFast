import { secondaryColor, colors } from '../styles/common'

// The "Are you sure?" box: the question wraps above the buttons on a narrow screen
export const prompt = {
  display: 'flex',
  flexWrap: 'wrap',
  alignItems: 'center',
  justifyContent: 'flex-end',
  gap: 8,
  padding: '8px 10px',
  borderRadius: 8,
  background: 'var(--surface2)',
  border: '1px solid var(--border)',
}

export const text = {
  flex: '1 1 180px',
  fontSize: 13,
  color: 'var(--text)',
}

export const cancelBtn = {
  padding: '5px 12px',
  borderRadius: 8,
  border: '1px solid var(--border)',
  background: 'transparent',
  color: 'var(--text-muted)',
  fontSize: 12,
  cursor: 'pointer',
}

export const confirmBtn = {
  ...cancelBtn,
  border: 'none',
  background: secondaryColor,
  color: '#fff',
  fontWeight: 600,
}

// A delete's action: red like every delete, never themed
export const dangerBtn = {
  ...confirmBtn,
  background: colors.dangerStrong,
}
