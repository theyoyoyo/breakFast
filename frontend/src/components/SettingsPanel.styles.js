import {
  panelContainer, brandHeaderRow, tabName, subPageHeader, subPageBackBtn, panelBody,
  section, sectionLabel, input, addRow, addBtn,
  tagX, empty, error, select, secondaryColor, colors, deleteBtn,
} from '../styles/common'

export { section, sectionLabel, tagX, empty, error, select }

export const container = panelContainer
export { brandHeaderRow, tabName, subPageHeader }
export const body = panelBody

export { input, addRow, addBtn }

// Age + Gender and Height + Weight are two pairs: side by side (four in a row) where both fit,
// one under the other (two by two) on a phone. Columns shrink (minmax 0), so the boxes, sized
// for their content, never push the page wider than the screen.
export const profileRow = {
  display: 'flex',
  flexWrap: 'wrap',
  gap: 8,
}

export const profilePair = {
  flex: '1 1 200px',
  minWidth: 0,
  display: 'grid',
  gridTemplateColumns: 'repeat(2, minmax(0, 1fr))',
  gap: 8,
}

export const profileField = {
  display: 'flex',
  flexDirection: 'column',
  gap: 3,
  minWidth: 0,
}

// Activity Level fills the row, Country (a code once chosen) sits beside it
export const profileWideRow = {
  display: 'flex',
  gap: 8,
}

export const profileWideField = {
  ...profileField,
  flex: 1,
}

// A compact box `chars` characters wide (padding and border included)
export const profileNumber = (chars) => ({
  ...input,
  flex: '0 1 auto',
  width: `calc(${chars}ch + 22px)`,
  minWidth: 0,
  textAlign: 'center',
})

export const profileSelect = {
  ...select,
  maxWidth: '100%',
  minWidth: 0,
  alignSelf: 'flex-start',
}

export const profileWideSelect = {
  ...select,
  width: '100%',
  minWidth: 0,
}

// Country: the code (or "—") with ▾ over a transparent native select, so a tap opens the
// phone's list of full names ("Germany (DE)") while the closed box stays narrow
export const countryPicker = {
  ...select,
  position: 'relative',
  display: 'flex',
  alignItems: 'center',
  gap: 6,
  cursor: 'pointer',
  maxWidth: '12ch',
}

export const countryText = {
  minWidth: '2ch',
  overflow: 'hidden',
  textOverflow: 'ellipsis',
  whiteSpace: 'nowrap',
}

export const countrySelect = {
  position: 'absolute',
  inset: 0,
  width: '100%',
  opacity: 0,
  fontSize: 12,
  cursor: 'pointer',
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

// × that clears a profile field — red like every other ×
export const clearFieldBtn = {
  background: 'none',
  border: 'none',
  fontSize: 16,
  color: colors.danger,
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

// ✏️ on a supplement row, between the frequency and the ×
export const editBtn = {
  background: 'none',
  border: 'none',
  cursor: 'pointer',
  fontSize: 13,
  padding: '0 2px',
  lineHeight: 1,
  flexShrink: 0,
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

// Traffic-light priorities: green = don't really care, yellow = care a lot, red = top priority
const priorityColors = {
  low: { bg: 'var(--surface)', color: colors.successText, activeBg: colors.successText, activeColor: '#1a1a2e' },
  high: { bg: 'var(--surface)', color: colors.goldText, activeBg: colors.goldText, activeColor: '#1a1a2e' },
  critical: { bg: 'var(--surface)', color: '#f1948a', activeBg: colors.dangerStrong, activeColor: '#fff' },
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

// Bulk delete ("Delete meals older than 1 year") — shared delete look, full width
export const dangerBtn = {
  ...deleteBtn,
  width: '100%',
  padding: '10px 16px',
  borderRadius: 8,
  fontWeight: 600,
  fontSize: 13,
  cursor: 'pointer',
}

export const backBtn = subPageBackBtn

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

// Meal history trash (shared delete look)
export const deleteMealBtn = { ...deleteBtn, fontSize: 16 }

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

// Small overlay editor (a supplement's name and contents): title, fields, Close / Save
export const overlayTitle = {
  fontSize: 18,
  fontWeight: 700,
  color: 'var(--accent)',
  textAlign: 'center',
  marginBottom: 16,
}

export const overlayForm = {
  display: 'flex',
  flexDirection: 'column',
  gap: 6,
}

export const overlayActions = {
  display: 'flex',
  justifyContent: 'space-between',
  gap: 10,
  marginTop: 16,
}

export const overlayCloseBtn = {
  background: 'var(--surface2)',
  border: '1px solid var(--border)',
  borderRadius: 10,
  padding: '12px 24px',
  color: 'var(--text-muted)',
  fontSize: 15,
  cursor: 'pointer',
}

export const overlaySaveBtn = {
  background: secondaryColor,
  border: 'none',
  borderRadius: 10,
  padding: '12px 24px',
  color: '#fff',
  fontSize: 15,
  fontWeight: 600,
  cursor: 'pointer',
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

// AI settings → Removed shopping suggestions: a row like the toggles above it, with a small
// Bring back button (muted while there's nothing to bring back), then an "Are you sure?" prompt
export const aiRow = {
  display: 'flex',
  alignItems: 'center',
  gap: 12,
  marginTop: 12,
}

export const aiRowLabel = {
  fontSize: 13,
  color: 'var(--text-muted)',
  flex: 1,
}

export const bringBackBtn = (active) => ({
  padding: '4px 10px',
  borderRadius: 12,
  border: '1px solid var(--border)',
  background: active ? 'var(--surface2)' : 'transparent',
  color: active ? 'var(--text)' : 'var(--text-muted)',
  fontSize: 12,
  whiteSpace: 'nowrap',
  cursor: active ? 'pointer' : 'default',
  opacity: active ? 1 : 0.6,
})

export const bringBackPrompt = {
  display: 'flex',
  flexWrap: 'wrap',
  alignItems: 'center',
  justifyContent: 'flex-end',
  gap: 8,
  marginTop: 8,
  padding: '8px 10px',
  borderRadius: 8,
  background: 'var(--surface2)',
  border: '1px solid var(--border)',
}

export const bringBackPromptText = {
  flex: '1 1 180px',
  fontSize: 13,
  color: 'var(--text)',
}

export const bringBackCancelBtn = {
  padding: '5px 12px',
  borderRadius: 8,
  border: '1px solid var(--border)',
  background: 'transparent',
  color: 'var(--text-muted)',
  fontSize: 12,
  cursor: 'pointer',
}

export const bringBackAllowBtn = {
  ...bringBackCancelBtn,
  border: 'none',
  background: secondaryColor,
  color: '#fff',
  fontWeight: 600,
}
