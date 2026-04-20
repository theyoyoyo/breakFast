import { secondaryColor, colors } from '../styles/common'

export const editorContainer = {
  display: 'flex',
  flexDirection: 'column',
  gap: 0,
}

export const editorHeader = {
  display: 'flex',
  alignItems: 'center',
  gap: 8,
  marginBottom: 16,
  flexShrink: 0,
  flexWrap: 'wrap',
}

export const nameInput = {
  flex: 1,
  minWidth: 120,
  fontSize: 18,
  fontWeight: 700,
  color: 'var(--accent)',
  background: 'var(--surface2)',
  border: '1px solid var(--border)',
  borderRadius: 8,
  padding: '6px 10px',
  outline: 'none',
}

export const mealId = {
  fontSize: 9,
  color: 'var(--text-muted)',
  opacity: 0.5,
  flexShrink: 0,
  whiteSpace: 'nowrap',
}

export const prepTimeGroup = {
  display: 'flex',
  alignItems: 'center',
  gap: 3,
  flexShrink: 0,
}

export const prepTimeLabel = {
  fontSize: 14,
}

export const prepTimeInput = {
  width: 36,
  background: 'var(--surface2)',
  border: '1px solid var(--border)',
  borderRadius: 6,
  padding: '4px 4px',
  color: 'var(--text)',
  fontSize: 13,
  textAlign: 'center',
  outline: 'none',
}

export const prepTimeValue = {
  fontSize: 13,
  color: 'var(--text-muted)',
}

export const prepTimeUnit = {
  fontSize: 12,
  color: 'var(--text-muted)',
}

export const itemList = {
  display: 'flex',
  flexDirection: 'column',
  gap: 6,
  flex: 1,
  overflowY: 'auto',
  maxHeight: '35vh',
}

export const itemRow = {
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  padding: '10px 12px',
  background: 'var(--surface2)',
  borderRadius: 10,
  fontSize: 15,
}

export const qtyGroup = {
  display: 'flex',
  alignItems: 'center',
  gap: 2,
  flexShrink: 0,
}

export const qtyInput = {
  width: 46,
  background: 'var(--surface)',
  border: '1px solid var(--border)',
  borderRadius: 6,
  padding: '4px 4px',
  color: 'var(--text)',
  fontSize: 14,
  textAlign: 'center',
  outline: 'none',
}

export const arrowBtn = {
  background: 'none',
  border: '1px solid var(--border)',
  borderRadius: 4,
  cursor: 'pointer',
  fontSize: 10,
  padding: '2px 5px',
  color: 'var(--text-muted)',
  lineHeight: 1,
}

export const unitLabel = {
  fontSize: 13,
  color: 'var(--text-muted)',
  flexShrink: 0,
  minWidth: 30,
  marginRight: 8,
}

// Styled to look like the static unitLabel — blends in, no border chrome
export const unitSelect = {
  fontSize: 13,
  color: 'var(--text-muted)',
  background: 'none',
  border: 'none',
  outline: 'none',
  cursor: 'pointer',
  flexShrink: 0,
  minWidth: 30,
  maxWidth: 110,
  marginRight: 8,
  padding: 0,
}

export const itemText = {
  flex: 1,
  color: 'var(--text)',
}

export const itemActions = {
  display: 'flex',
  gap: 4,
  flexShrink: 0,
}

export const deleteBtn = {
  background: 'none',
  border: 'none',
  cursor: 'pointer',
  fontSize: 18,
  padding: '4px 6px',
}

export const dishBadge = {
  fontSize: 16,
  flexShrink: 0,
  marginRight: 6,
}

export const expandBtn = (isOpen) => ({
  background: 'none',
  border: '1px solid var(--border)',
  borderRadius: 4,
  cursor: 'pointer',
  fontSize: 10,
  padding: '2px 6px',
  color: isOpen ? 'var(--accent)' : 'var(--text-muted)',
  lineHeight: 1,
})

export const subList = {
  marginLeft: 16,
  marginTop: 2,
  marginBottom: 4,
  borderLeft: '2px solid var(--border)',
  paddingLeft: 10,
  display: 'flex',
  flexDirection: 'column',
  gap: 4,
}

export const subRow = {
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  padding: '6px 10px',
  background: 'var(--surface)',
  borderRadius: 8,
  fontSize: 13,
}

export const subAddRow = {
  display: 'flex',
  gap: 6,
  marginTop: 2,
}

export const addRow = {
  display: 'flex',
  gap: 8,
  marginTop: 12,
  flexShrink: 0,
}

export const addInput = {
  flex: 1,
  background: 'var(--surface2)',
  border: '1px solid var(--border)',
  borderRadius: 10,
  padding: '10px 14px',
  color: 'var(--text)',
  fontSize: 15,
  outline: 'none',
}

export const addBtn = {
  background: 'var(--surface2)',
  border: '1px solid var(--border)',
  borderRadius: 10,
  padding: '10px 16px',
  color: 'var(--text)',
  fontSize: 18,
  fontWeight: 600,
  cursor: 'pointer',
}

export const actions = {
  display: 'flex',
  justifyContent: 'space-between',
  marginTop: 16,
  gap: 10,
  flexShrink: 0,
}

export const closeBtn = {
  background: 'var(--surface2)',
  border: '1px solid var(--border)',
  borderRadius: 10,
  padding: '12px 24px',
  color: 'var(--text-muted)',
  fontSize: 15,
  cursor: 'pointer',
}

export const saveBtn = {
  background: secondaryColor,
  border: 'none',
  borderRadius: 10,
  padding: '12px 24px',
  color: '#fff',
  fontSize: 15,
  fontWeight: 600,
  cursor: 'pointer',
}

export const copyToFavBtn = {
  background: colors.gold,
  border: `1px solid ${colors.goldBorder}`,
  borderRadius: 10,
  padding: '12px 16px',
  fontSize: 13,
  fontWeight: 600,
  color: colors.goldText,
  cursor: 'pointer',
  transition: 'background 0.15s',
  whiteSpace: 'nowrap',
}

export const copyToFavBtnDone = {
  background: colors.success,
  border: `1px solid ${colors.successBorder}`,
  borderRadius: 10,
  padding: '12px 16px',
  fontSize: 13,
  fontWeight: 600,
  color: colors.successText,
  cursor: 'default',
  opacity: 0.8,
  whiteSpace: 'nowrap',
}
