import {
  panelContainer, panelHeader, panelBody,
  section, sectionLabel, input, addRow, addBtn,
  tagX, empty, error,
} from '../styles/common'

export { section, sectionLabel, tagX, empty, error }

export const container = panelContainer
export const header = panelHeader
export const body = panelBody

export { input, addRow, addBtn }

export const tag = {
  display: 'inline-flex',
  alignItems: 'center',
  gap: 6,
  background: 'var(--surface2)',
  border: '1px solid var(--border)',
  borderRadius: 20,
  padding: '4px 12px',
  fontSize: 12,
  color: 'var(--text)',
}

export const tagList = {
  display: 'flex',
  flexWrap: 'wrap',
  gap: 6,
}
