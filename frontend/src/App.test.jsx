/**
 * Tests for App's tabs: the open tab is in the link while logged in, so a refresh with a live
 * session reopens it, and a login starts on Chat.
 * The panels, the login screen and API calls are mocked — no real network calls are made.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react'
import App from './App'
import * as api from './services/api'

vi.mock('./services/api', () => {
  class NetworkError extends Error {}
  return {
    NetworkError,
    logout: vi.fn(),
    checkAuth: vi.fn(() => Promise.resolve({})),
    getPreferences: vi.fn(() => Promise.resolve([])),
  }
})
vi.mock('./utils/theme', () => ({ applyTheme: vi.fn() }))
vi.mock('./utils/language', () => ({ applyLanguage: vi.fn() }))

// Each panel is a stub that names itself, so a test can see which one is shown
vi.mock('./components/ChatInterface', async () => {
  const { forwardRef } = await import('react')
  return { default: forwardRef(() => <div>Chat panel</div>) }
})
vi.mock('./components/IngredientPanel', async () => {
  const { forwardRef } = await import('react')
  return { default: forwardRef(() => <div>Fridge panel</div>) }
})
vi.mock('./components/PreferencesPanel', () => ({ default: () => <div>Preferences panel</div> }))
vi.mock('./components/FavoritesPanel', () => ({ default: () => <div>Favorites panel</div> }))
vi.mock('./components/SettingsPanel', () => ({ default: () => <div>Settings panel</div> }))
vi.mock('./components/LoginScreen', () => ({
  default: ({ onLogin }) => (
    <button onClick={() => onLogin({ token: 'tok-2', user: { id: 2, name: 'Bob' } })}>Log in</button>
  ),
}))

function storeSession() {
  localStorage.setItem('bf_token', 'tok-1')
  localStorage.setItem('bf_user', JSON.stringify({ id: 1, name: 'Alice' }))
}

function openAt(hash) {
  window.history.replaceState(null, '', `/${hash}`)
}

describe('App tabs', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
    openAt('')
    api.checkAuth.mockResolvedValue({})
  })

  // A refresh on #fridge with a live session opens the Fridge tab and keeps the link
  it('reopens the tab the link names', async () => {
    storeSession()
    openAt('#fridge')
    render(<App />)
    expect(await screen.findByText('Fridge panel')).toBeVisible()
    expect(screen.getByText('Chat panel')).not.toBeVisible()
    expect(window.location.hash).toBe('#fridge')
  })

  // Switching tabs replaces the link without a history step, and Chat leaves the link plain
  it('puts the open tab in the link', async () => {
    storeSession()
    render(<App />)
    await screen.findByText('Chat panel')
    const steps = window.history.length

    fireEvent.click(screen.getByTitle('Settings'))
    expect(screen.getByText('Settings panel')).toBeVisible()
    expect(window.location.hash).toBe('#settings')

    fireEvent.click(screen.getByTitle('Chat'))
    expect(screen.getByText('Chat panel')).toBeVisible()
    expect(window.location.hash).toBe('')
    expect(window.history.length).toBe(steps)
  })

  // A tab typed into the link opens
  it('opens a tab typed into the link', async () => {
    storeSession()
    render(<App />)
    await screen.findByText('Chat panel')
    act(() => {
      openAt('#Favorites')
      window.dispatchEvent(new HashChangeEvent('hashchange'))
    })
    await waitFor(() => expect(screen.getByText('Favorites panel')).toBeVisible())
    expect(window.location.hash).toBe('#favorites')
  })

  // Logout leaves a plain link, and the next login starts on Chat
  it('starts the next login on Chat after Logout', async () => {
    storeSession()
    openAt('#settings')
    render(<App />)
    expect(await screen.findByText('Settings panel')).toBeVisible()

    fireEvent.click(screen.getByTitle('Logout'))
    expect(api.logout).toHaveBeenCalled()
    expect(window.location.hash).toBe('')

    fireEvent.click(screen.getByText('Log in'))
    expect(screen.getByText('Chat panel')).toBeVisible()
    expect(window.location.hash).toBe('')
  })

  // A stored session the server refuses at start shows the login, and the login starts on Chat
  it('starts on Chat when the stored session is refused', async () => {
    storeSession()
    openAt('#fridge')
    api.checkAuth.mockRejectedValue(new Error('API error 401'))
    render(<App />)
    fireEvent.click(await screen.findByText('Log in'))
    expect(screen.getByText('Chat panel')).toBeVisible()
    expect(window.location.hash).toBe('')
  })

  // Opened offline, the app keeps its stored session and so the link's tab
  it('keeps the tab when the server cannot be reached', async () => {
    storeSession()
    openAt('#fridge')
    api.checkAuth.mockRejectedValue(new api.NetworkError())
    render(<App />)
    expect(await screen.findByText('Fridge panel')).toBeVisible()
  })

  // An unknown tab in the link opens Chat and leaves the link plain
  it('opens Chat for an unknown tab', async () => {
    storeSession()
    openAt('#nope')
    render(<App />)
    expect(await screen.findByText('Chat panel')).toBeVisible()
    expect(window.location.hash).toBe('')
  })
})
