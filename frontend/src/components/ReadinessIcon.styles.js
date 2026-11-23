import { colors } from '../styles/common'

// Meal icon on a neutral tile whose ring doubles as a readiness badge: green = ready, yellow = something
// missing (#244). No tinted fill, so a yellow food stays clear; the ring colors follow light and dark mode.
const RING = {
  ready: colors.successText,
  missing: colors.goldText,
}

export const icon = (readiness) => ({
  fontSize: 14,
  lineHeight: 1,
  flexShrink: 0,
  borderRadius: 6,
  padding: '2px 3px',
  background: 'var(--surface)',
  border: `2px solid ${RING[readiness] || 'transparent'}`,
  transition: 'border-color 0.2s',
})
