import { panelContainer, panelHeader } from '../styles/common'

export const container = panelContainer

export const header = panelHeader

export const list = {
  flex: 1,
  overflowY: 'auto',
  padding: '8px 0',
}

export const row = {
  display: 'flex',
  alignItems: 'center',
  padding: '6px 16px',
  gap: 8,
}

export const name = {
  flex: 1,
  fontSize: 13,
  color: 'var(--text)',
}

export const qty = {
  fontSize: 12,
  color: 'var(--text-muted)',
}

export const deleteBtn = {
  background: 'none',
  border: 'none',
  color: 'var(--text-muted)',
  fontSize: 14,
  padding: '2px 4px',
  borderRadius: 4,
  opacity: 0.5,
  transition: 'opacity 0.1s',
}

export const addRow = {
  display: 'flex',
  gap: 6,
  padding: '10px 12px',
  borderTop: '1px solid var(--border)',
}

export const input = {
  flex: 1,
  background: 'var(--surface2)',
  border: '1px solid var(--border)',
  borderRadius: 8,
  padding: '6px 10px',
  color: 'var(--text)',
  fontSize: 13,
  outline: 'none',
}

export const addBtn = {
  background: 'var(--accent)',
  border: 'none',
  borderRadius: 8,
  color: '#fff',
  fontWeight: 700,
  fontSize: 18,
  width: 32,
  height: 32,
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
}

export const empty = {
  padding: 20,
  color: 'var(--text-muted)',
  fontSize: 13,
  textAlign: 'center',
}

export const error = {
  padding: '8px 16px',
  fontSize: 12,
  color: '#e76f51',
}
