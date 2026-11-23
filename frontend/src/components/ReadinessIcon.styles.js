// Meal icon on a neutral tile whose ring doubles as a readiness badge: green = ready, yellow = something
// missing (#244). No tinted fill, so a yellow food stays clear; the ring colors follow light and dark mode.
const RING = {
  ready: 'var(--c-ring-ready)',
  missing: 'var(--c-ring-missing)',
}

export const icon = (readiness) => ({
  fontSize: 14,
  lineHeight: 1,
  flexShrink: 0,
  borderRadius: 6,
  padding: 'calc(4px - var(--ring-w)) calc(5px - var(--ring-w))',
  background: 'var(--surface)',
  border: `var(--ring-w) solid ${RING[readiness] || 'transparent'}`,
  transition: 'border-color 0.2s',
})
