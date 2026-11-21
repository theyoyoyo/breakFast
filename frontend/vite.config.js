import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'
import { ICON_BACKGROUND } from './src/brand/brand.js'

export default defineConfig({
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test-setup.js'],
  },
  plugins: [
    react(),
    VitePWA({
      registerType: 'autoUpdate',
      manifest: {
        name: 'break FAST',
        short_name: 'breakFAST',
        description: 'Personal AI breakfast planner',
        // Brand colors come from src/brand/brand.js, like the icons
        theme_color: ICON_BACKGROUND,
        background_color: ICON_BACKGROUND,
        display: 'standalone',
        icons: [
          { src: '/icon-192.png', sizes: '192x192', type: 'image/png', purpose: 'any' },
          { src: '/icon-512.png', sizes: '512x512', type: 'image/png', purpose: 'any' },
          { src: '/icon-maskable-512.png', sizes: '512x512', type: 'image/png', purpose: 'maskable' },
          { src: '/icon-monochrome-512.png', sizes: '512x512', type: 'image/png', purpose: 'monochrome' },
        ],
      },
    }),
  ],
  server: {
    host: true,
    port: 5173,
  },
})
