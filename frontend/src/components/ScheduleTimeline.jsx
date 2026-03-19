const RESOURCE_COLORS = {
  air_fryer: '#f4a261',
  toaster: '#e76f51',
  stove: '#e9c46a',
  hands: '#90be6d',
  none: '#aaa',
}

const RESOURCE_LABELS = {
  air_fryer: 'Air Fryer',
  toaster: 'Toaster',
  stove: 'Stove',
  hands: 'Hands',
  none: '',
}

const s = {
  container: {
    background: 'var(--surface2)',
    borderRadius: 'var(--radius)',
    padding: 20,
    display: 'flex',
    flexDirection: 'column',
    gap: 12,
  },
  header: {
    fontSize: 13,
    fontWeight: 700,
    textTransform: 'uppercase',
    letterSpacing: '0.08em',
    color: 'var(--text-muted)',
  },
  entry: {
    display: 'flex',
    alignItems: 'flex-start',
    gap: 10,
  },
  time: {
    minWidth: 38,
    fontSize: 12,
    color: 'var(--text-muted)',
    fontVariantNumeric: 'tabular-nums',
    paddingTop: 2,
  },
  dot: (resource) => ({
    width: 10,
    height: 10,
    borderRadius: '50%',
    background: RESOURCE_COLORS[resource] || '#aaa',
    marginTop: 4,
    flexShrink: 0,
  }),
  label: {
    fontSize: 13,
    color: 'var(--text)',
  },
  resource: (resource) => ({
    fontSize: 11,
    color: RESOURCE_COLORS[resource] || '#aaa',
    fontWeight: 600,
  }),
  note: {
    fontSize: 11,
    color: 'var(--text-muted)',
    fontStyle: 'italic',
  },
  makespan: {
    fontSize: 13,
    fontWeight: 700,
    color: 'var(--accent)',
    borderTop: '1px solid var(--border)',
    paddingTop: 10,
    marginTop: 4,
  },
}

function formatTime(minutes) {
  const m = Math.floor(minutes)
  const s = Math.round((minutes - m) * 60)
  return `${m}:${String(s).padStart(2, '0')}`
}

export default function ScheduleTimeline({ schedule }) {
  if (!schedule?.timeline?.length) return null

  return (
    <div style={s.container}>
      <div style={s.header}>Cooking Schedule</div>

      {schedule.timeline.map((entry) => (
        <div key={`${entry.time}-${entry.label}`} style={s.entry}>
          <div style={s.time}>{formatTime(entry.time)}</div>
          <div style={s.dot(entry.resource)} />
          <div>
            <div style={s.label}>{entry.label}</div>
            {entry.resource && entry.resource !== 'none' && (
              <div style={s.resource(entry.resource)}>
                {RESOURCE_LABELS[entry.resource] || entry.resource}
              </div>
            )}
            {entry.note && <div style={s.note}>{entry.note}</div>}
          </div>
        </div>
      ))}

      <div style={s.makespan}>
        Total: {Math.ceil(schedule.makespan_min)} min
      </div>
    </div>
  )
}
