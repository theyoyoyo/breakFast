/**
 * Generic star rating component.
 *
 * Props:
 *   value     — current rating (1-based)
 *   max       — number of stars (default 10)
 *   onChange  — (newValue) => void
 *   size      — star font size (default 22)
 *   numSize   — number label font size (default 10)
 *   activeColor — color for lit stars (default 'var(--c-star)')
 *   style     — optional container style override
 */
export default function StarRating({
  value = 0,
  max = 10,
  onChange,
  size = 22,
  numSize = 10,
  activeColor = 'var(--c-star)',
  style,
}) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', ...style }}>
      {Array.from({ length: max }, (_, i) => i + 1).map(n => (
        <div
          key={n}
          style={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            cursor: onChange ? 'pointer' : 'default',
            flex: 1,
            userSelect: 'none',
          }}
          onClick={() => onChange?.(n)}
        >
          <span style={{ fontSize: numSize, color: 'var(--text-muted)', marginBottom: 2 }}>{n}</span>
          <span style={{
            fontSize: size,
            color: n <= value ? activeColor : 'var(--border)',
            transition: 'color 0.1s',
          }}>★</span>
        </div>
      ))}
    </div>
  )
}
