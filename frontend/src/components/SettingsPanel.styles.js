import {
  panelContainer, panelHeader, panelBody,
  section, sectionLabel, input, addRow, addBtn,
  tagX, empty, error, select,
} from '../styles/common'

export { section, sectionLabel, tagX, empty, error, select }

export const container = panelContainer
export const header = panelHeader
export const body = panelBody

export { input, addRow, addBtn }

export const profileGrid = {
  display: 'grid',
  gridTemplateColumns: '1fr 1fr',
  gap: 8,
}

export const profileField = {
  display: 'flex',
  flexDirection: 'column',
  gap: 3,
}

export const profileLabel = {
  fontSize: 10,
  fontWeight: 700,
  textTransform: 'uppercase',
  color: 'var(--text-muted)',
}

export const saveBtn = {
  background: 'var(--accent)',
  border: 'none',
  borderRadius: 8,
  color: '#fff',
  fontWeight: 700,
  fontSize: 12,
  padding: '8px 16px',
  cursor: 'pointer',
  alignSelf: 'flex-end',
}

export const suppRow = {
  display: 'flex',
  alignItems: 'center',
  gap: 6,
  background: 'var(--surface2)',
  border: '1px solid var(--border)',
  borderRadius: 8,
  padding: '6px 10px',
  fontSize: 12,
}

export const suppName = {
  fontWeight: 600,
  color: 'var(--text)',
}

export const suppContents = {
  flex: 1,
  color: 'var(--text-muted)',
  fontSize: 11,
}

export const suppFreq = {
  fontSize: 10,
  fontWeight: 700,
  textTransform: 'uppercase',
  padding: '2px 6px',
  borderRadius: 4,
  background: 'var(--surface)',
  color: 'var(--text-muted)',
  cursor: 'pointer',
  border: 'none',
}

export const ratingsBtn = {
  width: '100%',
  padding: '12px 16px',
  background: '#c4533e',
  border: 'none',
  borderRadius: 8,
  color: '#fff',
  fontWeight: 700,
  fontSize: 14,
  cursor: 'pointer',
  textTransform: 'uppercase',
  letterSpacing: '0.05em',
}

export const healthRulesBtn = {
  width: '100%',
  padding: '12px 16px',
  background: 'var(--accent)',
  border: 'none',
  borderRadius: 8,
  color: '#fff',
  fontWeight: 700,
  fontSize: 14,
  cursor: 'pointer',
  textTransform: 'uppercase',
  letterSpacing: '0.05em',
}

export const ruleRow = {
  display: 'flex',
  flexDirection: 'column',
  gap: 6,
  background: 'var(--surface2)',
  border: '1px solid var(--border)',
  borderRadius: 8,
  padding: '10px 12px',
}

export const ruleTop = {
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
}

export const ruleName = {
  fontWeight: 600,
  fontSize: 13,
  color: 'var(--text)',
  flex: 1,
}

export const priorityRow = {
  display: 'flex',
  gap: 4,
}

const priorityColors = {
  low: { bg: 'var(--surface)', color: 'var(--text-muted)', activeBg: 'var(--text-muted)', activeColor: '#fff' },
  high: { bg: 'var(--surface)', color: 'var(--accent)', activeBg: 'var(--accent)', activeColor: '#fff' },
  critical: { bg: 'var(--surface)', color: '#c4533e', activeBg: '#c4533e', activeColor: '#fff' },
}

export const priorityBtn = (active, level) => {
  const c = priorityColors[level] || priorityColors.high
  return {
    flex: 1,
    padding: '5px 4px',
    borderRadius: 6,
    border: 'none',
    fontSize: 11,
    fontWeight: 600,
    cursor: 'pointer',
    background: active ? c.activeBg : c.bg,
    color: active ? c.activeColor : c.color,
    transition: 'background 0.15s, color 0.15s',
  }
}

export const dangerBtn = {
  width: '100%',
  padding: '10px 16px',
  background: 'var(--surface2)',
  border: '1px solid #c4533e',
  borderRadius: 8,
  color: '#c4533e',
  fontWeight: 600,
  fontSize: 13,
  cursor: 'pointer',
}

export const backBtn = {
  background: 'none',
  border: 'none',
  fontSize: 18,
  color: 'var(--accent)',
  cursor: 'pointer',
  padding: '0 4px',
}

export const ratingRow = {
  display: 'flex',
  flexDirection: 'column',
  gap: 4,
  background: 'var(--surface2)',
  border: '1px solid var(--border)',
  borderRadius: 8,
  padding: '8px 10px',
}

export const ratingTop = {
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
}

export const ratingName = {
  fontWeight: 600,
  fontSize: 13,
  color: 'var(--text)',
}

export const starsRow = {
  display: 'flex',
  justifyContent: 'space-between',
}

export const starCell = {
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'center',
  cursor: 'pointer',
  flex: 1,
  userSelect: 'none',
}

export const starNum = {
  fontSize: 9,
  color: 'var(--text-muted)',
  marginBottom: 1,
}

export const star = (lit) => ({
  fontSize: 18,
  color: lit ? '#f5a623' : 'var(--border)',
  transition: 'color 0.1s',
})

// --- Meal History styles ---

export const mealCard = {
  background: 'var(--surface2)',
  border: '1px solid var(--border)',
  borderRadius: 8,
  overflow: 'hidden',
}

export const mealHeader = {
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  padding: '10px 12px',
  cursor: 'pointer',
}

export const mealInfo = {
  display: 'flex',
  flexDirection: 'column',
  gap: 3,
  flex: 1,
  minWidth: 0,
}

export const mealName = {
  fontWeight: 600,
  fontSize: 13,
  color: 'var(--text)',
}

export const mealDate = {
  fontSize: 11,
  color: 'var(--text-muted)',
}

export const mealActions = {
  display: 'flex',
  alignItems: 'center',
  gap: 4,
  flexShrink: 0,
}

export const expandIcon = {
  fontSize: 12,
  color: 'var(--text-muted)',
  padding: '2px 4px',
}

export const editMealBtn = {
  background: 'none',
  border: 'none',
  cursor: 'pointer',
  fontSize: 16,
  padding: '2px 4px',
}

export const deleteMealBtn = {
  background: 'none',
  border: 'none',
  cursor: 'pointer',
  fontSize: 16,
  padding: '2px 4px',
}

export const mealExpanded = {
  padding: '0 12px 12px',
  display: 'flex',
  flexDirection: 'column',
  gap: 6,
  borderTop: '1px solid var(--border)',
  paddingTop: 10,
}

export const mealNameEdit = {
  display: 'flex',
  flexDirection: 'column',
  gap: 3,
}

export const mealFieldLabel = {
  fontSize: 10,
  fontWeight: 700,
  textTransform: 'uppercase',
  color: 'var(--text-muted)',
}

export const mealItemList = {
  display: 'flex',
  flexDirection: 'column',
  gap: 4,
}

export const mealItemRow = {
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  padding: '6px 8px',
  background: 'var(--surface)',
  borderRadius: 6,
  fontSize: 13,
}

export const mealItemText = {
  flex: 1,
  color: 'var(--text)',
}

export const mealItemInput = {
  flex: 1,
  background: 'var(--surface2)',
  border: '1px solid var(--accent)',
  borderRadius: 6,
  padding: '4px 8px',
  color: 'var(--text)',
  fontSize: 13,
  outline: 'none',
}

export const mealItemActions = {
  display: 'flex',
  gap: 2,
  flexShrink: 0,
}

export const cancelEditBtn = {
  background: 'var(--surface2)',
  border: '1px solid var(--border)',
  borderRadius: 8,
  color: 'var(--text-muted)',
  fontWeight: 600,
  fontSize: 12,
  padding: '8px 16px',
  cursor: 'pointer',
}
