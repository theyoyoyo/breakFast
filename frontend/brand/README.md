# Brand files

Everything about the break FAST logo starts in one file: [`src/brand/brand.js`](../src/brand/brand.js). It holds the mark's shapes, its two palettes (light and dark backgrounds, each with the wordmark's two colors) and the icon background color.

The wordmark is "break" in Unbounded Regular and "FAST" in Unbounded ExtraBold (SIL OFL 1.1, a dev-only package, `@fontsource/unbounded`). The icon script outlines it into SVG paths (`src/brand/wordmark.js`, generated), so the app draws the name without loading a font.

| What | Where | Made by |
|---|---|---|
| The logo in the app (login, panel headers) | `src/components/Logo.jsx` (`withName` adds the wordmark) | drawn live from `brand.js` and `wordmark.js` |
| Outlined wordmark | `src/brand/wordmark.js` | `npm run icons` |
| App icons, favicon | `public/` | `npm run icons` |
| Master SVGs (`mark-*.svg`, `lockup-light.svg`, `lockup-dark.svg`, `app-icon.svg`) | this folder | `npm run icons` |
| Manifest colors (splash screen, browser bar) | `vite.config.js` | reads `ICON_BACKGROUND` from `brand.js` |
| Browser bar color before the app loads | `index.html` (`theme-color`) | by hand; a test checks it matches `ICON_BACKGROUND` |
| App name | `BRAND_NAME` in `brand.js`, `name` / `short_name` in `vite.config.js`, `<title>` in `index.html` | by hand |

## Changing the brand

1. Edit `brand.js`: colors in `PALETTES` and `ICON_BACKGROUND`, or new shapes in `MARK_SHAPES` (with `MARK_BOUNDS` / `CLOCHE_BOUNDS` around what's drawn). To change the wordmark's text or font, change `outlineWordmark` in `scripts/outline-wordmark.mjs`.
2. Update `theme-color` in `index.html` and the name fields listed above.
3. Run `npm run icons` in `frontend/` and commit the regenerated files.

`brand.js` and the name fields listed above are the only places the name and colors live; nothing else refers to the colors.

## Rules

- The mark is drawn for the project, so its license is the repo's.
- The lockup's "light" version (dark green name) is for light backgrounds, the "dark" version (cream name) for dark ones; the app shows the one that fits its current light or dark mode.
- Brand colors are fixed: they don't follow the accent theme (Settings → Theme), except "FAST" in the app's wordmark, which takes the theme's accent (`var(--accent)` in `Logo.jsx`). The master files keep the brand orange.
- The favicon leaves out the speed lines, which vanish at 16 px.
- The monochrome icon (Android themed icons) draws one color with the dome cut out, since only its shape is used.
