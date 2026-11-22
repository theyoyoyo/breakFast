// Shared styles used across multiple components

// Secondary button color, used for all action buttons. A CSS variable so the
// theme setting can change it (index.css); use --secondary-soft for a tinted background.
export const secondaryColor = 'var(--secondary)'

// Semantic color palette — use these instead of hardcoded hex values. Each is a CSS variable
// (index.css, --c-*) with a value for dark and one for light; none follows the accent theme.
export const colors = {
  // Status
  success: 'var(--c-success)',
  successBorder: 'var(--c-success-border)',
  successText: 'var(--c-success-text)',
  gold: 'var(--c-gold)',
  goldBorder: 'var(--c-gold-border)',
  goldText: 'var(--c-gold-text)',
  goldStar: 'var(--c-star)',
  error: 'var(--c-error)',
  // Danger (delete / remove / top priority) — semantic, never themed
  danger: 'var(--c-danger)',
  dangerSoft: 'rgba(231, 76, 60, 0.15)',
  dangerBorder: 'rgba(231, 76, 60, 0.45)',
  dangerStrong: 'var(--c-danger-strong)',
  // Expired / required (red), expiring soon (orange), fresh (green), staples (purple)
  red: 'var(--c-red)',
  warn: 'var(--c-warn)',
  green: 'var(--c-green)',
  greenStrong: 'var(--c-green-strong)',
  purple: 'var(--c-purple)',
  purpleSoft: 'var(--c-purple-soft)',
  scoreMid: 'var(--c-score-mid)',
  priorityTop: 'var(--c-priority-top)',
  // Text on a filled green or yellow chip
  onStatus: 'var(--c-on-status)',
  // Supplements
  daily: 'var(--c-success)',
  dailyText: 'var(--c-success-text)',
  sometimes: 'var(--c-sometimes)',
  sometimesText: 'var(--c-sometimes-text)',
  // Edit button (muted blue-gray)
  editBg: 'var(--c-edit-bg)',
  editBorder: 'var(--c-edit-border)',
  editText: 'var(--c-edit-text)',
}

export const panelContainer = {
  background: 'var(--surface)',
  borderRadius: 'var(--radius)',
  display: 'flex',
  flexDirection: 'column',
  height: '100%',
  overflow: 'hidden',
}

export const panelHeader = {
  padding: '14px 16px',
  fontWeight: 700,
  fontSize: 13,
  textTransform: 'uppercase',
  letterSpacing: '0.08em',
  color: 'var(--text-muted)',
  borderBottom: '1px solid var(--border)',
}

// Main tab title: the app name in the theme's accent color, the same on every tab (like Chat)
export const brandTitle = {
  fontWeight: 600,
  fontSize: 16,
  letterSpacing: '0.02em',
  textTransform: 'none',
  color: 'var(--accent)',
}

export const brandHeader = { ...panelHeader, ...brandTitle }

// Preferences, Favorites and Settings: the app name at the left and the tab's name at the right,
// so a phone (icons only in the tab bar) shows which tab is open
export const brandHeaderRow = {
  ...brandHeader,
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  gap: 8,
}

export const tabName = {
  fontSize: 12,
  fontWeight: 700,
  textTransform: 'uppercase',
  letterSpacing: '0.08em',
  color: 'var(--text-muted)',
}

// Sub-page header (← back + page name), the Weekly Summary look, shared by every sub-page
export const subPageHeader = {
  fontSize: 18,
  fontWeight: 700,
  color: 'var(--accent)',
  padding: '16px 16px 8px',
  display: 'flex',
  alignItems: 'center',
  gap: 8,
}

export const subPageBackBtn = {
  background: 'none',
  border: 'none',
  cursor: 'pointer',
  fontSize: 18,
  color: 'var(--text-muted)',
  padding: '2px 6px',
}

export const panelBody = {
  flex: 1,
  overflowY: 'auto',
  padding: '12px 16px',
  display: 'flex',
  flexDirection: 'column',
  gap: 20,
}

export const section = {
  display: 'flex',
  flexDirection: 'column',
  gap: 8,
}

// Section titles inside a tab (Preferences, Settings): accent colored with a thin rule
// so sections separate clearly from their content
export const sectionLabel = {
  fontSize: 12,
  fontWeight: 700,
  textTransform: 'uppercase',
  letterSpacing: '0.08em',
  color: 'var(--accent)',
  paddingBottom: 4,
  borderBottom: '1px solid var(--border)',
}

export const input = {
  flex: 1,
  background: 'var(--surface2)',
  border: '1px solid var(--border)',
  borderRadius: 8,
  padding: '6px 10px',
  color: 'var(--text)',
  fontSize: 12,
  outline: 'none',
}

export const addRow = {
  display: 'flex',
  gap: 6,
}

export const addBtn = {
  background: secondaryColor,
  border: 'none',
  borderRadius: 8,
  color: '#fff',
  fontWeight: 700,
  fontSize: 16,
  width: 28,
  height: 28,
  flexShrink: 0,
  padding: 0,
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
}

// Delete / remove buttons — one look everywhere (trash cans, Del): soft red background,
// red border and text. Callers may only change size (padding, fontSize, radius).
export const deleteBtn = {
  background: colors.dangerSoft,
  border: `1px solid ${colors.dangerBorder}`,
  borderRadius: 6,
  color: colors.danger,
  cursor: 'pointer',
  fontSize: 14,
  padding: '2px 6px',
  lineHeight: 1.2,
}

// × remove button on tags and list rows — red, since it deletes
export const tagX = {
  background: 'none',
  border: 'none',
  color: colors.danger,
  fontSize: 14,
  cursor: 'pointer',
  padding: 0,
  lineHeight: 1,
}

export const empty = {
  fontSize: 12,
  color: 'var(--text-muted)',
  fontStyle: 'italic',
}

export const error = {
  padding: '8px 0',
  fontSize: 12,
  color: colors.error,
}

export const select = {
  background: 'var(--surface2)',
  border: '1px solid var(--border)',
  borderRadius: 8,
  padding: '6px 10px',
  color: 'var(--text)',
  fontSize: 12,
  outline: 'none',
}
