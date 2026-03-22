export const container = {
  background: 'var(--surface2)',
  borderRadius: 'var(--radius)',
  padding: 20,
  display: 'flex',
  flexDirection: 'column',
  gap: 12,
}

export const header = {
  fontSize: 13,
  fontWeight: 700,
  textTransform: 'uppercase',
  letterSpacing: '0.08em',
  color: 'var(--text-muted)',
}

export const entry = {
  display: 'flex',
  alignItems: 'flex-start',
  gap: 10,
}

export const time = {
  minWidth: 38,
  fontSize: 12,
  color: 'var(--text-muted)',
  fontVariantNumeric: 'tabular-nums',
  paddingTop: 2,
}

export const dot = (resource, colors) => ({
  width: 10,
  height: 10,
  borderRadius: '50%',
  background: colors[resource] || '#aaa',
  marginTop: 4,
  flexShrink: 0,
})

export const label = {
  fontSize: 13,
  color: 'var(--text)',
}

export const resource = (res, colors) => ({
  fontSize: 11,
  color: colors[res] || '#aaa',
  fontWeight: 600,
})

export const note = {
  fontSize: 11,
  color: 'var(--text-muted)',
  fontStyle: 'italic',
}

export const makespan = {
  fontSize: 13,
  fontWeight: 700,
  color: 'var(--accent)',
  borderTop: '1px solid var(--border)',
  paddingTop: 10,
  marginTop: 4,
}
