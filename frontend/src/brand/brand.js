// The break FAST brand: the mark's shapes and colors, in one place.
// The Logo component and the icon script (scripts/render-icons.mjs) both draw from this file,
// so a color or shape change here reaches the app and, after `npm run icons`, every icon file.
// A version under another name and colors only needs its own copy of this file (see brand/README.md).

export const BRAND_NAME = 'break FAST'

// The mark: a cloche with three speed lines, drawn in a 1024 x 605 box.
// Each shape has a role, and the role picks its color from a palette below.
export const MARK_VIEWBOX = '0 0 1024 605'
export const MARK_SHAPES = [
  { el: 'rect', role: 'lines', line: true, x: 160, y: 178, width: 195, height: 55, rx: 27.5 },
  { el: 'rect', role: 'lines', line: true, x: 113, y: 270, width: 172, height: 38, rx: 19 },
  { el: 'rect', role: 'lines', line: true, x: 25, y: 340, width: 215, height: 55, rx: 27.5 },
  { el: 'circle', role: 'outline', cx: 630, cy: 72, r: 58 },
  { el: 'path', role: 'outline', d: 'M190,433 C262,428 296,388 328,322 C388,196 508,127 640,127 C832,127 952,262 962,433 Z' },
  { el: 'rect', role: 'outline', x: 100, y: 432, width: 865, height: 58, rx: 29 },
  { el: 'path', role: 'dome', d: 'M326,433 C352,392 376,346 404,300 C458,216 542,179 640,179 C792,179 896,282 910,433 Z' },
  { el: 'stroke', role: 'hl', d: 'M401,407 C424,312 497,237 604,210', width: 40 },
  { el: 'rect', role: 'outline', x: 270, y: 520, width: 655, height: 55, rx: 27.5 },
]

// The drawn area of the mark, with and without the speed lines (used to center it in icons).
export const MARK_BOUNDS = { x: 25, y: 14, width: 940, height: 561 }
export const CLOCHE_BOUNDS = { x: 100, y: 14, width: 865, height: 561 }

// Palettes. Brand colors are fixed: they don't follow the app's accent theme.
export const PALETTES = {
  // On light backgrounds: a dark green outline
  light: { outline: '#15241B', dome: '#FBA35E', lines: '#FF6A13', hl: '#FFF3E6' },
  // On dark backgrounds (and the app icon): a cream outline
  dark: { outline: '#F4F1EA', dome: '#FBA35E', lines: '#FF6A13', hl: '#FFF3E6' },
}

// The app icon's background, also the PWA splash and browser bar color (vite.config.js, index.html).
export const ICON_BACKGROUND = '#0E1A13'

// Plain SVG text of the mark, for the icon script. Options:
//   palette: a PALETTES entry; mono: true draws one color (`color`) with the dome cut out
//   lines: false leaves out the speed lines (small favicons)
export function markSvgInner({ palette = PALETTES.dark, lines = true, mono = false, color = '#FFFFFF' } = {}) {
  const shapes = MARK_SHAPES.filter((s) => lines || !s.line)
  const fill = (role) => (mono ? color : palette[role])
  const parts = shapes.map((s) => {
    if (mono && s.role === 'dome') return '' // cut out through the mask below
    if (s.el === 'rect') return `<rect x="${s.x}" y="${s.y}" width="${s.width}" height="${s.height}" rx="${s.rx}" fill="${fill(s.role)}"/>`
    if (s.el === 'circle') return `<circle cx="${s.cx}" cy="${s.cy}" r="${s.r}" fill="${fill(s.role)}"/>`
    if (s.el === 'path') return `<path d="${s.d}" fill="${fill(s.role)}"/>`
    return `<path d="${s.d}" fill="none" stroke="${fill(s.role)}" stroke-width="${s.width}" stroke-linecap="round"/>`
  })
  if (!mono) return parts.join('')
  // One color: the dome becomes a hole in the outline, the highlight stays inside it
  const dome = MARK_SHAPES.find((s) => s.role === 'dome')
  const hl = MARK_SHAPES.find((s) => s.role === 'hl')
  return `<defs><mask id="domeCut" maskUnits="userSpaceOnUse" x="0" y="0" width="1024" height="605">`
    + `<rect width="1024" height="605" fill="#fff"/><path d="${dome.d}" fill="#000"/></mask></defs>`
    + `<g mask="url(#domeCut)">${parts.filter((p, i) => shapes[i].role !== 'hl').join('')}</g>`
    + `<path d="${hl.d}" fill="none" stroke="${color}" stroke-width="${hl.width}" stroke-linecap="round"/>`
}
