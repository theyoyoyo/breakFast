// Lint rules for the frontend (#220): ESLint's, React's and the hooks' recommended sets.
// `npm run lint` checks every file, in CI too (#258).
import js from '@eslint/js'
import react from 'eslint-plugin-react'
import reactHooks from 'eslint-plugin-react-hooks'
import globals from 'globals'

export default [
  { ignores: ['dist/', 'dev-dist/'] },
  js.configs.recommended,
  react.configs.flat.recommended,
  // React 17+ JSX transform: no React import needed in a JSX file.
  react.configs.flat['jsx-runtime'],
  reactHooks.configs.flat.recommended,
  {
    files: ['**/*.{js,jsx}'],
    languageOptions: {
      ecmaVersion: 'latest',
      sourceType: 'module',
      parserOptions: { ecmaFeatures: { jsx: true } },
      globals: { ...globals.browser },
    },
    settings: { react: { version: 'detect' } },
    // The app doesn't use PropTypes (no types on props anywhere), so the rule would only add noise.
    rules: {
      'react/prop-types': 'off',
      // Panels load their data with setState inside an effect. Rewriting that changes when and how
      // often they load, so it waits for the UI redesign: a warning until then, and CI's
      // --max-warnings (.github/workflows/ci.yml) keeps new ones out.
      'react-hooks/set-state-in-effect': 'warn',
    },
  },
  {
    // Vitest runs with globals: true (vite.config.js), and the setup file runs in Node too.
    files: ['src/**/*.test.{js,jsx}', 'src/test-setup.js'],
    languageOptions: { globals: { ...globals.vitest, ...globals.node } },
  },
  {
    // Build config and the icon scripts (npm run icons) run in Node.
    files: ['*.config.js', 'scripts/**/*.mjs'],
    languageOptions: { globals: { ...globals.node } },
  },
]
