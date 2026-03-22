import { secondaryColor } from '../styles/common'

export const card = {
  background: 'var(--surface2)',
  borderRadius: 'var(--radius)',
  padding: 20,
  display: 'flex',
  flexDirection: 'column',
  gap: 14,
}

export const title = {
  fontSize: 18,
  fontWeight: 700,
  color: 'var(--accent)',
}

export const description = {
  color: 'var(--text-muted)',
  fontSize: 13,
}

export const section = {
  display: 'flex',
  flexDirection: 'column',
  gap: 6,
}

export const sectionLabel = {
  fontSize: 11,
  fontWeight: 700,
  textTransform: 'uppercase',
  letterSpacing: '0.08em',
  color: 'var(--text-muted)',
}

export const list = {
  listStyle: 'none',
  display: 'flex',
  flexDirection: 'column',
  gap: 4,
}

export const listItem = {
  fontSize: 13,
  color: 'var(--text)',
  paddingLeft: 12,
  position: 'relative',
}

export const bullet = {
  position: 'absolute',
  left: 0,
  color: 'var(--accent)',
}

export const prepTime = {
  fontSize: 13,
  color: 'var(--text-muted)',
}

export const nutritionNote = {
  fontSize: 13,
  color: '#7ec8a4',
  fontStyle: 'italic',
}

export const ratingRow = {
  display: 'flex',
  gap: 8,
  alignItems: 'center',
}

export const ratingBtn = (active) => ({
  background: active ? secondaryColor : 'var(--surface)',
  border: '1px solid var(--border)',
  borderRadius: 8,
  padding: '6px 14px',
  color: 'var(--text)',
  fontSize: 16,
  transition: 'background 0.15s',
})
