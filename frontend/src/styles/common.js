// Shared styles used across multiple components

// Secondary button color, used for all action buttons. A CSS variable so the
// theme setting can change it (index.css); use --secondary-soft for a tinted background.
export const secondaryColor = 'var(--secondary)'

// Semantic color palette — use these instead of hardcoded hex values
export const colors = {
  // Status
  success: '#2d4a35',
  successBorder: '#4a7c59',
  successText: '#8bc59a',
  gold: '#4a3a10',
  goldBorder: '#b8922a',
  goldText: '#e8c84a',
  goldStar: '#f5a623',
  error: '#e76f51',
  // Danger (delete / remove / top priority) — semantic, never themed
  danger: '#ec7063',
  dangerSoft: 'rgba(231, 76, 60, 0.15)',
  dangerBorder: 'rgba(231, 76, 60, 0.45)',
  dangerStrong: '#b83b30',
  // Supplements
  daily: '#2d4a35',
  dailyText: '#8bc59a',
  sometimes: '#4a3d20',
  sometimesText: '#d4a94a',
  // Edit button (muted blue-gray)
  editBg: '#2a3a4a',
  editBorder: '#3d5060',
  editText: '#c0d0e0',
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
