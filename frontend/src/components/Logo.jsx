import { BRAND_NAME, MARK_SHAPES, MARK_VIEWBOX, PALETTES } from '../brand/brand'

// The app's mark, drawn from src/brand/brand.js. `mode` picks the palette for the background
// it sits on (the app is dark today); the brand colors never follow the accent theme.
export default function Logo({ height = 32, mode = 'dark', title = BRAND_NAME, style }) {
  const palette = PALETTES[mode] || PALETTES.dark
  return (
    <svg
      viewBox={MARK_VIEWBOX}
      height={height}
      role="img"
      aria-label={title}
      style={{ display: 'block', width: 'auto', flexShrink: 0, ...style }}
    >
      {MARK_SHAPES.map((s, i) => {
        const color = palette[s.role]
        if (s.el === 'rect') return <rect key={i} x={s.x} y={s.y} width={s.width} height={s.height} rx={s.rx} fill={color} />
        if (s.el === 'circle') return <circle key={i} cx={s.cx} cy={s.cy} r={s.r} fill={color} />
        if (s.el === 'path') return <path key={i} d={s.d} fill={color} />
        return <path key={i} d={s.d} fill="none" stroke={color} strokeWidth={s.width} strokeLinecap="round" />
      })}
    </svg>
  )
}
