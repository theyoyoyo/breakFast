import {
  panelContainer, panelHeader, panelBody, error, secondaryColor,
} from '../styles/common'

export const container = panelContainer
export const header = panelHeader
export const body = panelBody
export { error }

export const backBtn = {
  background: 'none',
  border: 'none',
  fontSize: 18,
  color: 'var(--accent)',
  cursor: 'pointer',
  padding: '0 4px',
}

export const grid = {
  display: 'grid',
  gridTemplateColumns: 'repeat(auto-fill, minmax(100px, 1fr))',
  gap: 10,
}

export const tile = (enabled) => ({
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'center',
  justifyContent: 'center',
  gap: 6,
  padding: '16px 8px',
  borderRadius: 12,
  border: enabled ? `2px solid ${secondaryColor}` : '2px solid var(--border)',
  background: enabled ? secondaryColor + '22' : 'var(--surface2)',
  cursor: 'pointer',
  transition: 'background 0.15s, border-color 0.15s, opacity 0.15s',
  opacity: enabled ? 1 : 0.5,
  userSelect: 'none',
})

export const tileName = {
  fontSize: 12,
  fontWeight: 600,
  color: 'var(--text)',
  textAlign: 'center',
  lineHeight: 1.3,
}
