import { colors } from '../styles/common'

// Meal icon whose background doubles as a readiness badge: green = ready, yellow = something missing
const READINESS = {
  ready: { background: 'rgba(139, 197, 154, 0.6)', border: colors.successText },
  missing: { background: 'rgba(232, 200, 74, 0.6)', border: colors.goldText },
}

export const icon = (readiness) => ({
  fontSize: 14,
  flexShrink: 0,
  borderRadius: 6,
  padding: '1px 4px',
  transition: 'background 0.2s, border-color 0.2s',
  background: READINESS[readiness]?.background || 'transparent',
  border: `1px solid ${READINESS[readiness]?.border || 'transparent'}`,
})
