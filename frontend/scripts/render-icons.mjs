// Renders every icon file from src/brand/brand.js: run `npm run icons` after changing the brand.
// Writes the outlined wordmark (src/brand/wordmark.js), the PNG and SVG icons into public/
// and the master SVGs into brand/. Nothing runs at build time.
import { mkdirSync, writeFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { Resvg } from '@resvg/resvg-js'
import { writeWordmark } from './outline-wordmark.mjs'

// The wordmark first: brand.js reads the file it writes
writeWordmark()
const {
  CLOCHE_BOUNDS, ICON_BACKGROUND, MARK_BOUNDS, MARK_VIEWBOX, PALETTES, lockupSvg, markSvgInner,
} = await import('../src/brand/brand.js')

const root = join(dirname(fileURLToPath(import.meta.url)), '..')
const publicDir = join(root, 'public')
const brandDir = join(root, 'brand')
mkdirSync(publicDir, { recursive: true })
mkdirSync(brandDir, { recursive: true })

// A square icon: the mark scaled to `fill` of the width and centered, on an optional background
function iconSvg({ size, fill, bounds = MARK_BOUNDS, background, radius = 0, mark }) {
  const k = (fill * size) / bounds.width
  const tx = (size - bounds.width * k) / 2 - bounds.x * k
  const ty = (size - bounds.height * k) / 2 - bounds.y * k
  const bg = background ? `<rect width="${size}" height="${size}" rx="${radius}" fill="${background}"/>` : ''
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}" viewBox="0 0 ${size} ${size}">`
    + `${bg}<g transform="translate(${tx.toFixed(2)} ${ty.toFixed(2)}) scale(${k.toFixed(5)})">${mark}</g></svg>\n`
}

function writePng(file, svg) {
  writeFileSync(join(publicDir, file), new Resvg(svg).render().asPng())
  console.log('wrote public/' + file)
}

function writeSvg(dir, file, svg) {
  writeFileSync(join(dir, file), svg)
  console.log(`wrote ${dir === publicDir ? 'public' : 'brand'}/${file}`)
}

const colorMark = markSvgInner({ palette: PALETTES.dark })
const clocheMark = markSvgInner({ palette: PALETTES.dark, lines: false })
const monoMark = markSvgInner({ mono: true, color: '#FFFFFF' })

// Home screen icons: the whole square, the mark at about 80% of the width
writePng('icon-192.png', iconSvg({ size: 192, fill: 0.8, background: ICON_BACKGROUND, mark: colorMark }))
writePng('icon-512.png', iconSvg({ size: 512, fill: 0.8, background: ICON_BACKGROUND, mark: colorMark }))
// iPhones: no transparency, iOS rounds the corners itself
writePng('apple-touch-icon.png', iconSvg({ size: 180, fill: 0.78, background: ICON_BACKGROUND, mark: colorMark }))
// Android crops maskable and monochrome icons to its own shape: the mark stays inside the 40% safe circle
writePng('icon-maskable-512.png', iconSvg({ size: 512, fill: 0.62, background: ICON_BACKGROUND, mark: colorMark }))
// Monochrome (Android 13+ themed icons): only the shape counts, so white on transparent
writePng('icon-monochrome-512.png', iconSvg({ size: 512, fill: 0.62, mark: monoMark }))
// Browser tab: the cloche alone, since speed lines vanish at 16 px
const favicon = iconSvg({ size: 64, fill: 0.84, bounds: CLOCHE_BOUNDS, background: ICON_BACKGROUND, radius: 14, mark: clocheMark })
writeSvg(publicDir, 'favicon.svg', favicon)
writePng('favicon-32.png', iconSvg({ size: 32, fill: 0.84, bounds: CLOCHE_BOUNDS, background: ICON_BACKGROUND, radius: 7, mark: clocheMark }))

// Master SVGs to open or hand on: the mark and the lockup (mark + name) for light and dark backgrounds, and the app icon
const markFile = (palette) => `<svg xmlns="http://www.w3.org/2000/svg" viewBox="${MARK_VIEWBOX}">${markSvgInner({ palette })}</svg>\n`
writeSvg(brandDir, 'mark-light.svg', markFile(PALETTES.light))
writeSvg(brandDir, 'mark-dark.svg', markFile(PALETTES.dark))
writeSvg(brandDir, 'app-icon.svg', iconSvg({ size: 512, fill: 0.8, background: ICON_BACKGROUND, mark: colorMark }))
writeSvg(brandDir, 'lockup-light.svg', lockupSvg(PALETTES.light))
writeSvg(brandDir, 'lockup-dark.svg', lockupSvg(PALETTES.dark))
