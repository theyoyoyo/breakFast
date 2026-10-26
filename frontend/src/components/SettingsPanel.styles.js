import {
  panelContainer, panelHeader, brandHeader, panelBody,
  section, sectionLabel, input, addRow, addBtn,
  tagX, empty, error, select, secondaryColor, colors,
} from '../styles/common'

export { section, sectionLabel, tagX, empty, error, select }

export const container = panelContainer
export const header = panelHeader
export { brandHeader }
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

export const profileInputRow = {
  display: 'flex',
  alignItems: 'center',
  gap: 4,
}

export const clearFieldBtn = {
  background: 'none',
  border: 'none',
  fontSize: 16,
  color: 'var(--text-muted)',
  cursor: 'pointer',
  padding: '0 2px',
  lineHeight: 1,
  flexShrink: 0,
}

export const saveBtn = {
  background: secondaryColor,
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

export const suppFreq = (freq) => ({
  fontSize: 10,
  fontWeight: 700,
  textTransform: 'uppercase',
  padding: '3px 8px',
  borderRadius: 6,
  cursor: 'pointer',
  border: 'none',
  transition: 'background 0.15s, color 0.15s',
  ...(freq === 'daily'
    ? { background: colors.daily, color: colors.dailyText }
    : { background: colors.sometimes, color: colors.sometimesText }
  ),
})

// Generic sub-page navigation button
export const navBtn = {
  width: '100%',
  padding: '12px 16px',
  background: secondaryColor,
  border: 'none',
  borderRadius: 8,
  color: '#fff',
  fontWeight: 700,
  fontSize: 14,
  cursor: 'pointer',
  textTransform: 'uppercase',
  letterSpacing: '0.05em',
}

// Aliases for backward compatibility (same as navBtn)
export const ratingsBtn = navBtn
export const healthRulesBtn = navBtn

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
  high: { bg: 'var(--surface)', color: secondaryColor, activeBg: secondaryColor, activeColor: '#fff' },
  critical: { bg: 'var(--surface)', color: secondaryColor, activeBg: secondaryColor, activeColor: '#fff' },
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
  border: `1px solid ${secondaryColor}`,
  borderRadius: 8,
  color: secondaryColor,
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

// --- Meal History styles ---

export const mealCard = {
  background: 'var(--surface2)',
  border: '1px solid var(--border)',
  borderRadius: 8,
  overflow: 'hidden',
  flexShrink: 0,
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

export const deleteMealBtn = {
  background: 'none',
  border: 'none',
  cursor: 'pointer',
  fontSize: 16,
  padding: '2px 4px',
}

export const editMealBtn = {
  background: 'none',
  border: 'none',
  cursor: 'pointer',
  fontSize: 15,
  padding: '2px 4px',
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
  maxHeight: '80dvh',
  display: 'flex',
  flexDirection: 'column',
}

export const analysisDropdown = {
  borderTop: '1px solid var(--border)',
  padding: '10px 12px',
  display: 'flex',
  flexDirection: 'column',
  gap: 6,
}

export const analysisMacroRow = {
  display: 'flex',
  flexWrap: 'wrap',
  gap: 4,
}

export const analysisMacroTag = {
  background: 'var(--surface)',
  border: '1px solid var(--border)',
  borderRadius: 6,
  padding: '3px 8px',
  fontSize: 11,
  color: secondaryColor,
  fontWeight: 600,
}

export const analysisNarrative = {
  fontSize: 12,
  color: 'var(--text-muted)',
  lineHeight: 1.5,
}


// Theme picker: one pill per theme with a color dot
export const themeRow = {
  display: 'flex',
  flexWrap: 'wrap',
  gap: 8,
  marginTop: 8,
}

export const themeBtn = (active) => ({
  display: 'flex',
  alignItems: 'center',
  gap: 6,
  padding: '6px 12px',
  borderRadius: 20,
  border: `1px solid ${active ? 'var(--accent)' : 'var(--border)'}`,
  background: active ? 'var(--surface2)' : 'transparent',
  color: active ? 'var(--text)' : 'var(--text-muted)',
  fontSize: 13,
  cursor: 'pointer',
})

export const themeSwatch = (color) => ({
  width: 12,
  height: 12,
  borderRadius: 6,
  background: color,
})
