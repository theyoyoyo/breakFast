import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import { applyTheme, storedTheme } from './utils/theme'
import './index.css'

// Before the first render, so the page never flashes the wrong accent color
applyTheme(storedTheme())

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
)
