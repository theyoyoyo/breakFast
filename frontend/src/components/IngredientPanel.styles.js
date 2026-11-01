import { panelContainer, secondaryColor, colors, brandTitle, deleteBtn } from '../styles/common'

export const container = panelContainer

// ---------------------------------------------------------------------------
// Header with inline add button
// ---------------------------------------------------------------------------

export const headerRow = {
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  padding: '14px 16px',
  borderBottom: '1px solid var(--border)',
}

export const headerText = brandTitle

export const headerBtns = {
  display: 'flex',
  gap: 6,
  alignItems: 'center',
}

const _headerExpiredBase = {
  borderRadius: 6,
  height: 28,
  padding: '0 8px',
  display: 'flex',
  alignItems: 'center',
  gap: 4,
  fontSize: 12,
  fontWeight: 600,
}

export const headerExpiredBtn = {
  ..._headerExpiredBase,
  background: 'rgba(230, 126, 34, 0.15)',
  border: '1px solid rgba(230, 126, 34, 0.3)',
  color: '#e67e22',
  cursor: 'pointer',
}

export const headerExpiredBtnSafe = {
  ..._headerExpiredBase,
  background: 'rgba(46, 204, 113, 0.1)',
  border: '1px solid rgba(46, 204, 113, 0.25)',
  color: '#2ecc71',
  cursor: 'default',
}

export const headerAddBtn = {
  background: secondaryColor,
  border: 'none',
  borderRadius: 6,
  color: '#fff',
  height: 28,
  padding: '0 10px',
  display: 'flex',
  alignItems: 'center',
  gap: 4,
  cursor: 'pointer',
  fontSize: 12,
  fontWeight: 600,
}

// ---------------------------------------------------------------------------
// Add panel (opens below header)
// ---------------------------------------------------------------------------

export const addPanel = {
  padding: '10px 16px',
  borderBottom: '1px solid var(--border)',
  background: 'var(--surface2)',
  display: 'flex',
  flexDirection: 'column',
  gap: 8,
}

export const addInput = {
  background: 'var(--surface)',
  border: '1px solid var(--border)',
  borderRadius: 8,
  padding: '8px 10px',
  color: 'var(--text)',
  fontSize: 13,
  outline: 'none',
  width: '100%',
  boxSizing: 'border-box',
}

export const addPanelRow = {
  display: 'flex',
  gap: 8,
  alignItems: 'center',
}

export const addDateInput = {
  flex: 1,
  background: 'var(--surface)',
  border: '1px solid var(--border)',
  borderRadius: 8,
  padding: '7px 10px',
  color: 'var(--text)',
  fontSize: 12,
  outline: 'none',
  colorScheme: 'dark',
}

export const addPanelBtn = {
  background: secondaryColor,
  border: 'none',
  borderRadius: 8,
  color: '#fff',
  fontWeight: 600,
  fontSize: 13,
  padding: '7px 18px',
  cursor: 'pointer',
}

// ---------------------------------------------------------------------------
// Ingredient list + group sections
// ---------------------------------------------------------------------------

export const list = {
  flex: 1,
  overflowY: 'auto',
  padding: '4px 0',
}

// Each group is a card: a theme-tinted header band (--bubble) over a darker item area,
// with a border, so groups stand apart from each other and from the panel
export const groupSection = {
  margin: '6px 10px',
  borderRadius: 8,
  border: '1px solid var(--border)',
  background: 'var(--bg)',
  overflow: 'hidden',
}

export const groupHeader = {
  display: 'flex',
  alignItems: 'center',
  padding: '8px 14px',
  background: 'var(--bubble)',
  cursor: 'pointer',
  userSelect: 'none',
  gap: 6,
}

export const groupHeaderText = {
  fontWeight: 700,
  fontSize: 12,
  textTransform: 'uppercase',
  letterSpacing: '0.06em',
  color: 'var(--accent)',
  flex: 1,
}

export const groupChevron = {
  color: 'var(--accent)',
  fontSize: 10,
  opacity: 0.8,
  transition: 'transform 0.15s ease',
}

export const groupCount = {
  fontSize: 11,
  color: 'var(--accent)',
  opacity: 0.8,
  fontWeight: 500,
}

export const row = {
  display: 'flex',
  alignItems: 'center',
  padding: '6px 16px',
  gap: 8,
}

export const name = {
  flex: 1,
  fontSize: 14,
  color: 'var(--text)',
}

export const expiryBadge = {
  fontSize: 11,
  color: 'var(--text-muted)',
  whiteSpace: 'nowrap',
}

export const iconBtn = {
  background: 'none',
  border: 'none',
  color: 'var(--text-muted)',
  padding: '3px',
  borderRadius: 4,
  opacity: 0.45,
  transition: 'opacity 0.1s',
  cursor: 'pointer',
  display: 'flex',
  alignItems: 'center',
}

// Row trash (shared delete look, icon-sized)
export const rowDeleteBtn = { ...deleteBtn, padding: 3, display: 'flex', alignItems: 'center' }

export const favBtn = {
  background: 'none',
  border: 'none',
  padding: '3px',
  borderRadius: 4,
  cursor: 'pointer',
  display: 'flex',
  alignItems: 'center',
  transition: 'transform 0.15s',
}

// ---------------------------------------------------------------------------
// "Kept" expiry badge
// ---------------------------------------------------------------------------

export const keptBadge = {
  marginLeft: 3,
  fontSize: 10,
  fontWeight: 500,
  opacity: 0.7,
  fontStyle: 'italic',
}

export const keptCountLabel = {
  fontSize: 11,
  fontWeight: 400,
  color: 'var(--text-muted)',
}

// ---------------------------------------------------------------------------
// Delete confirm (inline buttons below delete icon)
// ---------------------------------------------------------------------------

export const deleteConfirm = {
  position: 'absolute',
  top: '100%',
  right: 0,
  display: 'flex',
  gap: 3,
  padding: '4px 0',
  zIndex: 10,
}

const _deleteConfirmBase = {
  width: 26,
  height: 24,
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  borderRadius: 5,
  cursor: 'pointer',
  padding: 0,
  transition: 'all 0.1s',
}

export const deleteConfirmTrash = {
  ..._deleteConfirmBase,
  background: 'rgba(231, 76, 60, 0.2)',
  border: '1px solid rgba(231, 76, 60, 0.45)',
  color: '#e74c3c',
}

export const deleteConfirmShop = {
  ..._deleteConfirmBase,
  background: 'rgba(142, 68, 173, 0.2)',
  border: '1px solid rgba(142, 68, 173, 0.45)',
  color: '#a970c9',
}

// ---------------------------------------------------------------------------
// Edit row (inline)
// ---------------------------------------------------------------------------

export const editRow = {
  display: 'flex',
  alignItems: 'center',
  padding: '4px 12px',
  gap: 6,
  background: 'var(--surface2)',
}

export const editInput = {
  flex: 1,
  background: 'var(--surface)',
  border: '1px solid var(--border)',
  borderRadius: 6,
  padding: '5px 8px',
  color: 'var(--text)',
  fontSize: 13,
  outline: 'none',
  minWidth: 0,
}

export const editDateInput = {
  width: 120,
  background: 'var(--surface)',
  border: '1px solid var(--border)',
  borderRadius: 6,
  padding: '5px 6px',
  color: 'var(--text)',
  fontSize: 11,
  outline: 'none',
  colorScheme: 'dark',
}

export const editSaveBtn = {
  background: secondaryColor,
  border: 'none',
  borderRadius: 6,
  color: '#fff',
  fontWeight: 600,
  fontSize: 12,
  padding: '5px 12px',
  cursor: 'pointer',
  whiteSpace: 'nowrap',
}

export const editGroupSelect = {
  background: 'var(--surface)',
  border: '1px solid var(--border)',
  borderRadius: 6,
  padding: '5px 6px',
  color: 'var(--text)',
  fontSize: 11,
  outline: 'none',
  colorScheme: 'dark',
  maxWidth: 100,
}

export const addGroupSelect = {
  flex: 1,
  background: 'var(--surface)',
  border: '1px solid var(--border)',
  borderRadius: 8,
  padding: '7px 10px',
  color: 'var(--text)',
  fontSize: 12,
  outline: 'none',
  colorScheme: 'dark',
}

export const editCancelBtn = {
  background: 'none',
  border: 'none',
  color: 'var(--text-muted)',
  padding: '3px',
  cursor: 'pointer',
  display: 'flex',
  alignItems: 'center',
}

// ---------------------------------------------------------------------------
// Empty / error states
// ---------------------------------------------------------------------------

export const empty = {
  padding: 20,
  color: 'var(--text-muted)',
  fontSize: 13,
  textAlign: 'center',
}

export const error = {
  padding: '8px 16px',
  fontSize: 12,
  color: colors.error,
}

// ---------------------------------------------------------------------------
// Expiry widget + panel
// ---------------------------------------------------------------------------

export const expiryPanel = {
  borderTop: '1px solid var(--border)',
  background: 'var(--surface)',
  padding: '8px 0',
  maxHeight: '40%',
  display: 'flex',
  flexDirection: 'column',
}

export const expiryPanelHeader = {
  display: 'flex',
  justifyContent: 'space-between',
  alignItems: 'center',
  padding: '4px 12px 8px',
}

export const expiryPanelTitle = {
  fontSize: 14,
  fontWeight: 600,
  color: 'var(--text)',
  textAlign: 'center',
}

export const closeBtn = {
  background: 'none',
  border: 'none',
  color: 'var(--text-muted)',
  cursor: 'pointer',
  padding: '2px',
  display: 'flex',
  alignItems: 'center',
}

export const expiryPanelList = {
  flex: 1,
  overflowY: 'auto',
  padding: '0 8px',
}

export const expiryRow = {
  display: 'flex',
  alignItems: 'center',
  padding: '6px 8px',
  gap: 8,
}

export const checkbox = {
  accentColor: secondaryColor,
  width: 16,
  height: 16,
  cursor: 'pointer',
}

// 3-way action buttons for expired items
export const expiryActionGroup = {
  display: 'flex',
  gap: 2,
  flexShrink: 0,
}

const _expiryActionBase = {
  width: 26,
  height: 24,
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  borderRadius: 4,
  border: '1px solid var(--border)',
  background: 'none',
  color: 'var(--text-muted)',
  cursor: 'pointer',
  fontSize: 12,
  fontWeight: 700,
  padding: 0,
  transition: 'all 0.1s',
}

export const expiryActionBtn = {
  ..._expiryActionBase,
  opacity: 0.5,
}

export const expiryActionDeleteActive = {
  ..._expiryActionBase,
  background: 'rgba(231, 76, 60, 0.2)',
  border: '1px solid rgba(231, 76, 60, 0.5)',
  color: '#e74c3c',
  opacity: 1,
}

export const expiryActionKeepActive = {
  ..._expiryActionBase,
  background: 'rgba(46, 204, 113, 0.15)',
  border: '1px solid rgba(46, 204, 113, 0.4)',
  color: '#2ecc71',
  opacity: 1,
}

export const expiryActionShoppingActive = {
  ..._expiryActionBase,
  background: 'rgba(142, 68, 173, 0.2)',
  border: '1px solid rgba(142, 68, 173, 0.5)',
  color: '#a970c9',
  opacity: 1,
}

export const expiryConfirmBtn = {
  margin: '8px 16px',
  padding: '8px 16px',
  background: secondaryColor,
  color: '#fff',
  border: 'none',
  borderRadius: 8,
  fontSize: 13,
  fontWeight: 600,
  textAlign: 'center',
  cursor: 'pointer',
}

// ---------------------------------------------------------------------------
// Favorites button in header
// ---------------------------------------------------------------------------

export const headerFavBtn = {
  borderRadius: 6,
  height: 28,
  width: 28,
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  background: 'rgba(231, 76, 60, 0.12)',
  border: '1px solid rgba(231, 76, 60, 0.25)',
  color: '#e74c3c',
  cursor: 'pointer',
}

// ---------------------------------------------------------------------------
// Shopping button in header
// ---------------------------------------------------------------------------

export const headerShoppingBtn = {
  borderRadius: 6,
  height: 28,
  width: 28,
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  background: 'rgba(142, 68, 173, 0.15)',
  border: '1px solid rgba(142, 68, 173, 0.3)',
  color: '#a970c9',
  cursor: 'pointer',
}

// ---------------------------------------------------------------------------
// Shopping suggestions
// ---------------------------------------------------------------------------

export const suggestSection = {
  padding: '8px 16px',
  borderTop: '1px solid var(--border)',
}

export const suggestBtn = {
  width: '100%',
  padding: '9px 16px',
  background: secondaryColor, // follows the theme
  color: '#fff',
  border: 'none',
  borderRadius: 8,
  fontSize: 13,
  fontWeight: 600,
  cursor: 'pointer',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  gap: 6,
}

export const lyricBanner = {
  marginTop: 6,
  padding: '6px 10px',
  background: 'rgba(155, 89, 182, 0.1)',
  border: '1px solid rgba(155, 89, 182, 0.2)',
  borderRadius: 6,
  fontSize: 12,
  color: '#b07cc8',
  textAlign: 'center',
  fontStyle: 'italic',
}

export const suggestNote = {
  marginTop: 6,
  fontSize: 12,
  color: 'var(--text-muted)',
  textAlign: 'center',
}

export const suggestionsPanel = {
  borderTop: '1px solid var(--border)',
  background: 'var(--surface)',
  display: 'flex',
  flexDirection: 'column',
  maxHeight: '45%',
}

// The whole header is the ▲/▼ toggle, so it's an easy tap on a phone
export const suggestionsPanelHeader = {
  display: 'flex',
  justifyContent: 'space-between',
  alignItems: 'center',
  padding: '8px 12px 4px',
  background: 'none',
  border: 'none',
  width: '100%',
  cursor: 'pointer',
  textAlign: 'left',
}

export const collapseIcon = {
  fontSize: 11,
  color: 'var(--text-muted)',
}

export const suggestionsPanelTitle = {
  fontSize: 12,
  fontWeight: 700,
  textTransform: 'uppercase',
  letterSpacing: '0.06em',
  color: 'var(--text-muted)',
}

export const suggestionsList = {
  flex: 1,
  overflowY: 'auto',
  padding: '0 8px',
}

export const suggestionRow = {
  display: 'flex',
  alignItems: 'flex-start',
  padding: '6px 8px',
  gap: 10,
}

// Checkbox and text: tapping either toggles the check
export const suggestionLabel = {
  display: 'flex',
  alignItems: 'flex-start',
  gap: 10,
  flex: 1,
  minWidth: 0,
  cursor: 'pointer',
}

// × at the end of a row — red, since it removes the item
export const suggestionRemoveBtn = {
  background: 'none',
  border: 'none',
  color: colors.danger,
  fontSize: 18,
  lineHeight: 1,
  cursor: 'pointer',
  padding: '0 4px',
  flexShrink: 0,
}

export const suggestionName = {
  fontSize: 13,
  color: 'var(--text)',
  fontWeight: 500,
}

export const suggestionReason = {
  fontSize: 11,
  color: 'var(--text-muted)',
  marginTop: 2,
  lineHeight: 1.3,
}

// Send to List and Suggest More side by side under the list
export const suggestionsActions = {
  display: 'flex',
  gap: 8,
  padding: '6px 12px 10px',
}

export const sendToListBtn = {
  flex: 1,
  minWidth: 0,
  padding: '8px 12px',
  background: secondaryColor, // follows the theme
  color: '#fff',
  border: 'none',
  borderRadius: 8,
  fontSize: 13,
  fontWeight: 600,
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  gap: 6,
}

export const suggestMoreBtn = { ...sendToListBtn }

export const suggestionsNotes = {
  padding: '0 12px 8px',
}
