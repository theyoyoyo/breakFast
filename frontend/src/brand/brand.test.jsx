import { existsSync, readFileSync } from 'node:fs'
import { join } from 'node:path'
import { render, screen } from '@testing-library/react'
import Logo from '../components/Logo'
import { ICON_BACKGROUND, PALETTES, markSvgInner } from './brand'

const frontend = join(__dirname, '..', '..')
const read = (file) => readFileSync(join(frontend, file), 'utf8')

// Every icon the manifest lists is a file in public/, so installing the app shows an icon
test('manifest icons exist in public', () => {
  const icons = [...read('vite.config.js').matchAll(/src: '\/([^']+)'/g)].map((m) => m[1])
  expect(icons).toEqual(expect.arrayContaining(['icon-192.png', 'icon-512.png', 'icon-maskable-512.png', 'icon-monochrome-512.png']))
  for (const icon of icons) expect(existsSync(join(frontend, 'public', icon))).toBe(true)
})

// index.html links no manifest of its own (vite-plugin-pwa adds the one link) and its icons exist
test('index.html links its icons and no manifest', () => {
  const html = read('index.html')
  expect(html).not.toMatch(/rel="manifest"/)
  for (const [, href] of html.matchAll(/rel="(?:icon|apple-touch-icon)" href="\/([^"]+)"/g)) {
    expect(existsSync(join(frontend, 'public', href))).toBe(true)
  }
})

// The browser bar color in index.html is the brand's icon background, like the manifest's
test('index.html theme color matches the brand', () => {
  expect(read('index.html')).toContain(`<meta name="theme-color" content="${ICON_BACKGROUND}" />`)
  expect(read('vite.config.js')).toMatch(/theme_color: ICON_BACKGROUND/)
})

// The Logo draws the mark with the palette for its background and names the app for screen readers
test('Logo draws the mark in the chosen palette', () => {
  const { container } = render(<Logo mode="light" />)
  expect(screen.getByRole('img', { name: 'break FAST' })).toBeInTheDocument()
  const fills = [...container.querySelectorAll('[fill]')].map((el) => el.getAttribute('fill'))
  expect(fills).toContain(PALETTES.light.outline)
  expect(fills).not.toContain(PALETTES.dark.outline)
})

// The monochrome mark uses one color only and the favicon mark leaves out the speed lines
test('mark variants for icons', () => {
  const mono = markSvgInner({ mono: true, color: '#FFFFFF' })
  const colors = new Set([...mono.matchAll(/(?:fill|stroke)="(#[0-9A-Fa-f]{6})"/g)].map((m) => m[1]))
  expect([...colors].filter((c) => c !== '#fff' && c !== '#000')).toEqual(['#FFFFFF'])
  expect(markSvgInner({ lines: false })).not.toContain(PALETTES.dark.lines)
})

// With the name, the Logo adds the outlined wordmark: "break" in the mode's name color, "FAST" in the theme's accent
test('Logo with the name draws the wordmark in both palettes', () => {
  for (const mode of ['light', 'dark']) {
    const { container, unmount } = render(<Logo withName mode={mode} />)
    const fills = [...container.querySelectorAll('path[fill]')].map((el) => el.getAttribute('fill'))
    expect(fills).toEqual(expect.arrayContaining([PALETTES[mode].name, 'var(--accent)']))
    unmount()
  }
})
