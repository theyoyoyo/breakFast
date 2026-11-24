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
  // Smaller on a phone; 16px at least, so an iPhone doesn't zoom in when it's tapped
  fontSize: 'clamp(16px, 4.2vw, 18px)',
  fontWeight: 700,
  color: 'var(--accent)',
  background: 'var(--surface2)',
  border: '1px solid var(--border)',
  borderRadius: 8,
  padding: '6px 10px',
  outline: 'none',
}

// ☆ left of the meal name: empty until the meal is added to favorites, then a gold ⭐
// (stars are semantic gold, not the theme color)
export const favStar = {
  background: 'none',
  border: 'none',
  padding: 2,
  cursor: 'pointer',
  display: 'flex',
  alignItems: 'center',
  flexShrink: 0,
}

export const favStarOn = { color: colors.goldStar, fill: colors.goldStar }
export const favStarOff = { color: 'var(--text-muted)', fill: 'none' }

// Under the header when ☆ is tapped on a name another favorite has
export const favNote = {
  margin: '-8px 0 12px',
  fontSize: 13,
  lineHeight: 1.5,
  color: 'var(--text-muted)',
}

export const prepTimeGroup = {
  display: 'flex',
  alignItems: 'center',
  gap: 3,
  flexShrink: 0,
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

// The meal's icon at the header's right
export const mealIcon = {
  fontSize: 22,
  lineHeight: 1,
  flexShrink: 0,
}

// ℹ️ between Close and Save: opens how the suggestion meant each dish to be made, above the buttons
export const detailsBtn = (isOpen) => ({
  background: isOpen ? 'var(--surface2)' : 'none',
  border: '1px solid var(--border)',
  borderRadius: 10,
  cursor: 'pointer',
  fontSize: 16,
  padding: '0 12px',
  lineHeight: 1,
  flexShrink: 0,
})

export const detailsBox = {
  display: 'flex',
  flexDirection: 'column',
  gap: 8,
  marginTop: 14,
  padding: '10px 12px',
  background: 'var(--surface2)',
  border: '1px solid var(--border)',
  borderRadius: 10,
  fontSize: 13,
  flexShrink: 0,
}

export const detailsDish = {
  fontWeight: 600,
  color: 'var(--text)',
  marginBottom: 2,
}

// The dish's method reads as its main line; prep words follow in muted text
export const detailsMethod = {
  color: 'var(--text)',
  paddingLeft: 10,
  marginBottom: 2,
}

export const detailsLine = {
  color: 'var(--text-muted)',
  paddingLeft: 10,
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
  padding: '8px 10px',
  background: 'var(--surface2)',
  borderRadius: 10,
  fontSize: 15,
}

// A tap anywhere on a dish row opens or closes its ingredients
export const dishRow = { ...itemRow, cursor: 'pointer' }

// The amount and its ▲ / ▼ stacked beside it: narrow, so the item's name keeps most of the row
export const qtyGroup = {
  display: 'flex',
  alignItems: 'center',
  gap: 2,
  flexShrink: 0,
}

export const stepper = {
  display: 'flex',
  flexDirection: 'column',
  gap: 1,
}

export const qtyInput = {
  width: 34,
  background: 'var(--surface)',
  border: '1px solid var(--border)',
  borderRadius: 6,
  padding: '3px 2px',
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
  fontSize: 8,
  padding: '1px 4px',
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

// Styled to look like the static unitLabel — blends in, no border chrome.
// The plain unit and a chevron; the real select lies invisibly on top.
export const unitPicker = {
  position: 'relative',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  gap: 2,
  fontSize: 13,
  color: 'var(--text-muted)',
  cursor: 'pointer',
  flexShrink: 0,
  minWidth: 30,
  // A long unit wraps on a phone instead of taking the name's room
  maxWidth: 'clamp(44px, 17vw, 110px)',
  marginLeft: 4,
  marginRight: 6,
}

// Two-word units ("tea glass", "yemek kaşığı") take two lines; a long unknown unit breaks instead of overflowing
export const unitText = {
  lineHeight: 1.2,
  overflowWrap: 'anywhere',
}

// Covers the picker so a tap opens the native list, which shows spoon and glass sizes
export const unitSelect = {
  position: 'absolute',
  inset: 0,
  width: '100%',
  opacity: 0,
  fontSize: 13,
  cursor: 'pointer',
}

// minWidth 0: on a narrow phone a long name breaks onto another line instead of pushing the row wider
export const itemText = {
  flex: 1,
  minWidth: 0,
  overflowWrap: 'anywhere',
  color: 'var(--text)',
}

// Underline for ingredients not in the fridge: yellow while missing, green once marked as obtained;
// dotted on a dish whose hidden sub-ingredients are missing
export const missingName = ({ dotted = false, obtained = false } = {}) => ({
  textDecorationLine: 'underline',
  textDecorationStyle: dotted ? 'dotted' : 'solid',
  textDecorationColor: obtained ? colors.successText : colors.goldText,
  textDecorationThickness: 2,
  textUnderlineOffset: 3,
})

// ✱ at the top right of a dish ingredient the review put in for a missing one: small and muted, and
// lineHeight 0 keeps the raised mark from making the row taller
export const replacedMark = {
  fontSize: '0.7em',
  verticalAlign: 'super',
  lineHeight: 0,
  marginLeft: 2,
  color: 'var(--text-muted)',
  cursor: 'default',
}

export const itemActions = {
  display: 'flex',
  gap: 4,
  flexShrink: 0,
}

// Trash on item rows: a small red icon, no box, so the name keeps the row
export const deleteBtn = {
  background: 'none',
  border: 'none',
  padding: 4,
  color: colors.danger,
  cursor: 'pointer',
  display: 'flex',
  alignItems: 'center',
  lineHeight: 1,
}

// ▶ Ingredients: --border nearly matches the row, so the outline is the muted text color at 70%
// (3.5:1 on --surface2, was 1.1:1; text colors are the same in every theme)
export const expandBtn = (isOpen) => ({
  background: 'none',
  border: '1px solid color-mix(in srgb, var(--text-muted) 70%, transparent)',
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
  padding: '6px 8px',
  background: 'var(--surface)',
  borderRadius: 8,
  fontSize: 13,
}

// Add rows wrap instead of overflowing at phone width
export const subAddRow = {
  display: 'flex',
  flexWrap: 'wrap',
  gap: 6,
  marginTop: 2,
}

export const addRow = {
  display: 'flex',
  flexWrap: 'wrap',
  gap: 8,
  marginTop: 12,
  flexShrink: 0,
}

// ＋ Item and ＋ Dish stay together: on a narrow phone they move under the name box, kept at the right
export const addBtns = {
  display: 'flex',
  gap: 8,
  marginLeft: 'auto',
}

// Shrinks below its native width (minWidth 0) down to 6em, then gets a line of its own
export const addInput = {
  flex: '1 1 6em',
  minWidth: 0,
  background: 'var(--surface2)',
  border: '1px solid var(--border)',
  borderRadius: 10,
  // Slimmer than an item row: the box needs no more room than its text
  padding: '6px 12px',
  color: 'var(--text)',
  fontSize: 15,
  outline: 'none',
}

export const addBtn = {
  background: 'var(--surface2)',
  border: '1px solid var(--border)',
  borderRadius: 10,
  padding: '6px 12px',
  color: 'var(--text)',
  // Smaller on a phone
  fontSize: 'clamp(14px, 3.8vw, 16px)',
  fontWeight: 600,
  cursor: 'pointer',
  flexShrink: 0,
  whiteSpace: 'nowrap',
}

export const actions = {
  display: 'flex',
  flexWrap: 'wrap', // "Today I ate" has four buttons; wrap instead of overflowing at phone width
  justifyContent: 'space-between',
  marginTop: 16,
  gap: 10,
  flexShrink: 0,
}

// Close: an outlined button in the theme color, like Save in "Today I ate"
export const closeBtn = {
  background: 'transparent',
  border: `1px solid ${secondaryColor}`,
  borderRadius: 10,
  padding: '12px 24px',
  color: 'var(--text)',
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


