import { panelContainer, panelBody, secondaryColor } from '../styles/common'

export const container = panelContainer

export const header = {
  fontSize: 18,
  fontWeight: 700,
  color: 'var(--accent)',
  padding: '16px 16px 8px',
  display: 'flex',
  alignItems: 'center',
  gap: 8,
}

export const backBtn = {
  background: 'none',
  border: 'none',
  cursor: 'pointer',
  fontSize: 18,
  color: 'var(--text-muted)',
  padding: '2px 6px',
}

export const body = panelBody

export const empty = {
  color: 'var(--text-muted)',
  fontSize: 13,
  textAlign: 'center',
  padding: 20,
}

export const mealCard = {
  background: 'var(--surface2)',
  borderRadius: 10,
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
  alignItems: 'center',
  gap: 10,
  flex: 1,
  minWidth: 0,
}

export const mealDate = {
  fontSize: 11,
  color: 'var(--text-muted)',
  flexShrink: 0,
  minWidth: 70,
}

export const mealName = {
  fontSize: 14,
  fontWeight: 600,
  color: 'var(--text)',
  overflow: 'hidden',
  textOverflow: 'ellipsis',
  whiteSpace: 'nowrap',
}

export const analyzeBtn = {
  background: 'var(--surface)',
  border: '1px solid var(--border)',
  borderRadius: 6,
  padding: '3px 10px',
  fontSize: 11,
  color: 'var(--text)',
  cursor: 'pointer',
}

export const expandIcon = {
  fontSize: 12,
  color: 'var(--text-muted)',
}

export const ingredientList = {
  display: 'flex',
  flexWrap: 'wrap',
  gap: 4,
}

// --- Weekly Review styles ---

export const reviewSection = {
  display: 'flex',
  flexDirection: 'column',
  gap: 12,
}

export const narrative = {
  fontSize: 14,
  color: 'var(--text)',
  lineHeight: 1.6,
  padding: '10px 12px',
  background: 'var(--surface2)',
  borderRadius: 10,
}

export const scoreGrid = {
  display: 'grid',
  gridTemplateColumns: '1fr 1fr',
  gap: 8,
}

export const scoreCard = (score) => ({
  background: 'var(--surface2)',
  borderRadius: 10,
  padding: '12px 12px 10px',
  display: 'flex',
  flexDirection: 'column',
  gap: 4,
})

export const scoreLabel = {
  fontSize: 11,
  color: 'var(--text-muted)',
  fontWeight: 600,
  textTransform: 'uppercase',
  letterSpacing: '0.03em',
}

export const scoreValue = (score) => ({
  fontSize: 28,
  fontWeight: 800,
  color: score >= 80 ? 'var(--accent)' : score >= 60 ? '#f0a500' : '#e74c3c',
  lineHeight: 1,
})

export const scoreNote = {
  fontSize: 12,
  color: 'var(--text-muted)',
  lineHeight: 1.4,
  marginTop: 2,
}

export const reviewActions = {
  display: 'flex',
  justifyContent: 'flex-end',
  gap: 8,
}

export const refreshBtn = {
  background: 'var(--surface2)',
  border: '1px solid var(--border)',
  borderRadius: 8,
  padding: '6px 14px',
  fontSize: 13,
  color: 'var(--text)',
  cursor: 'pointer',
}

export const weekLabel = {
  fontSize: 12,
  color: 'var(--text-muted)',
  alignSelf: 'center',
}

export const noDataCard = {
  background: 'var(--surface2)',
  borderRadius: 10,
  padding: '20px 16px',
  textAlign: 'center',
  color: 'var(--text-muted)',
  fontSize: 13,
  lineHeight: 1.5,
}
