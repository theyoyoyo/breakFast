import { secondaryColor, colors } from '../styles/common'

export const container = {
  display: 'flex',
  flexDirection: 'column',
  height: '100%',
  background: 'var(--surface)',
  borderRadius: 'var(--radius)',
  overflow: 'hidden',
}

export const header = {
  padding: '16px 20px',
  borderBottom: '1px solid var(--border)',
  fontWeight: 700,
  fontSize: 16,
  color: 'var(--accent)',
}

export const empty = {
  padding: 20,
  color: 'var(--text-muted)',
  fontSize: 14,
  textAlign: 'center',
}

export const list = {
  flex: 1,
  overflowY: 'auto',
  padding: 12,
  display: 'flex',
  flexDirection: 'column',
  gap: 8,
}

export const card = {
  background: 'var(--surface2)',
  border: '1px solid var(--border)',
  borderRadius: 12,
  overflow: 'hidden',
  flexShrink: 0,
}

export const cardHeader = {
  display: 'flex',
  justifyContent: 'space-between',
  alignItems: 'center',
  padding: '12px 14px',
  cursor: 'pointer',
}

export const cardName = {
  fontWeight: 600,
  fontSize: 14,
  color: 'var(--text)',
}

export const cardMeta = {
  fontSize: 12,
  color: 'var(--text-muted)',
}

export const cardBody = {
  padding: '0 14px 12px',
  display: 'flex',
  flexDirection: 'column',
  gap: 10,
}

export const description = {
  fontSize: 13,
  color: 'var(--text-muted)',
  lineHeight: 1.4,
}

export const ingredientList = {
  display: 'flex',
  flexWrap: 'wrap',
  gap: 6,
}

export const ingredientChip = {
  fontSize: 11,
  background: 'var(--surface)',
  border: '1px solid var(--border)',
  borderRadius: 8,
  padding: '3px 8px',
  color: 'var(--text)',
}

export const cardActions = {
  display: 'flex',
  justifyContent: 'space-between',
  alignItems: 'center',
  gap: 8,
  marginTop: 4,
}

export const sendBtn = {
  background: secondaryColor,
  color: '#fff',
  border: 'none',
  borderRadius: 8,
  padding: '8px 14px',
  fontSize: 12,
  fontWeight: 600,
  cursor: 'pointer',
}

export const editBtn = {
  background: colors.editBg,
  border: `1px solid ${colors.editBorder}`,
  borderRadius: 8,
  padding: '8px 14px',
  fontSize: 12,
  fontWeight: 600,
  color: colors.editText,
  cursor: 'pointer',
}

export const overlay = {
  position: 'fixed',
  inset: 0,
  background: 'rgba(0,0,0,0.5)',
  zIndex: 30,
  display: 'flex',
  flexDirection: 'column',
  justifyContent: 'center',
  padding: 16,
}

export const overlayPanel = {
  background: 'var(--surface)',
  border: '1px solid var(--border)',
  borderRadius: 16,
  padding: '20px',
  boxShadow: '0 8px 32px rgba(0,0,0,0.3)',
  overflowY: 'auto',
  maxHeight: '80vh',
  display: 'flex',
  flexDirection: 'column',
}

export const removeBtn = {
  background: 'none',
  border: '1px solid var(--border)',
  borderRadius: 8,
  padding: '6px 10px',
  fontSize: 14,
  color: 'var(--text-muted)',
  cursor: 'pointer',
}
