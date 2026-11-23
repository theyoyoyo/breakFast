import * as s from './ReadinessIcon.styles'

// A meal's emoji on a neutral tile with a yellow (missing) or green (ready) ring; no ring until the check answers
export default function ReadinessIcon({ emoji, readiness, stillMissing }) {
  const title = readiness === 'missing'
    ? `Not ready — missing: ${stillMissing.join(', ')}`
    : readiness === 'ready' ? 'Ready — everything is in your fridge' : undefined
  return <span style={s.icon(readiness)} title={title}>{emoji}</span>
}
