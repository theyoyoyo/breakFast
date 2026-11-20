// Lint rules for the frontend (#220): ESLint's, React's and the hooks' recommended sets.
// `npm run lint` checks every file; CI checks only the files a pull request changes.
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
  },
  {
    // Vitest runs with globals: true (vite.config.js), and the setup file runs in Node too.
    files: ['src/**/*.test.{js,jsx}', 'src/test-setup.js'],
    languageOptions: { globals: { ...globals.vitest, ...globals.node } },
  },
  {
    // Build config runs in Node.
    files: ['*.config.js'],
    languageOptions: { globals: { ...globals.node } },
  },
]
