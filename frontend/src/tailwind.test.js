/**
 * Tailwind is set up without its base reset and reads the app's tokens (index.css, #235).
 */
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { compile } from '@tailwindcss/node'

const cssPath = resolve(process.cwd(), 'src/index.css')

// Token utilities compile to the app's CSS variables, and `dark:` follows data-mode (the Appearance setting)
it('builds utilities from the app tokens', async () => {
  const compiler = await compile(readFileSync(cssPath, 'utf8'), { base: resolve(process.cwd(), 'src'), onDependency: () => {} })
  const css = compiler.build(['bg-surface', 'text-fg-muted', 'border-line', 'text-accent', 'dark:bg-bg'])
  expect(css).toMatch(/\.bg-surface\s*{\s*background-color: var\(--surface\)/)
  expect(css).toMatch(/\.text-fg-muted\s*{\s*color: var\(--text-muted\)/)
  expect(css).toContain('var(--accent)')
  expect(css).toMatch(/data-mode="dark"/)
})

// The base reset (preflight) stays out until the shared ui/ components, so today's styles look the same,
// and the app's own page-wide rules sit in the base layer, so utilities like p-4 win over its reset
it('leaves out the base reset and layers the page rules', () => {
  const css = readFileSync(cssPath, 'utf8')
  expect(css).not.toMatch(/@import "tailwindcss";|preflight\.css/)
  const base = css.slice(css.indexOf('@layer base {'))
  expect(base).toMatch(/^@layer base {\s+\*, \*::before, \*::after {/)
  expect(css.slice(0, css.indexOf('@layer base {'))).not.toContain('*, *::before')
})
