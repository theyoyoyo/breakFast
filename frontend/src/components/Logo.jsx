import { BRAND_NAME, LOCKUP, MARK_SHAPES, MARK_VIEWBOX, PALETTES, WORDMARK } from '../brand/brand'

function MarkShapes({ palette }) {
  return MARK_SHAPES.map((s, i) => {
    const color = palette[s.role]
    if (s.el === 'rect') return <rect key={i} x={s.x} y={s.y} width={s.width} height={s.height} rx={s.rx} fill={color} />
    if (s.el === 'circle') return <circle key={i} cx={s.cx} cy={s.cy} r={s.r} fill={color} />
    if (s.el === 'path') return <path key={i} d={s.d} fill={color} />
    return <path key={i} d={s.d} fill="none" stroke={color} strokeWidth={s.width} strokeLinecap="round" />
  })
}

// The app's logo, drawn from src/brand/brand.js: the mark alone, or with `withName` the mark and the
// wordmark (outlined, so no font loads). `mode` picks the palette for the background it sits on
// (the app is dark today); the brand colors never follow the accent theme.
export default function Logo({ height = 32, mode = 'dark', withName = false, title = BRAND_NAME, style }) {
  const palette = PALETTES[mode] || PALETTES.dark
  const svgProps = {
    height,
    role: 'img',
    'aria-label': title,
    style: { display: 'block', width: 'auto', flexShrink: 0, ...style },
  }
  if (!withName) {
    return <svg viewBox={MARK_VIEWBOX} {...svgProps}><MarkShapes palette={palette} /></svg>
  }
  const { mark, name } = LOCKUP
  return (
    <svg viewBox={`0 0 ${LOCKUP.width.toFixed(1)} ${LOCKUP.height}`} {...svgProps}>
      <g transform={`translate(${mark.x} ${mark.y})`}><MarkShapes palette={palette} /></g>
      <g transform={`translate(${name.x} ${name.y.toFixed(2)}) scale(${name.scale.toFixed(5)})`}>
        <path d={WORDMARK.first} fill={palette.name} />
        <path d={WORDMARK.second} fill={palette.nameAccent} />
      </g>
    </svg>
  )
}
