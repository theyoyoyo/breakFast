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

import * as s from './ScheduleTimeline.styles'

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
          <div style={s.dot(entry.resource, RESOURCE_COLORS)} />
          <div>
            <div style={s.label}>{entry.label}</div>
            {entry.resource && entry.resource !== 'none' && (
              <div style={s.resource(entry.resource, RESOURCE_COLORS)}>
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
