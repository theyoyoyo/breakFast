/**
 * Tests for the login screen's error messages.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import * as api from '../services/api'
import LoginScreen, { retryMessage } from './LoginScreen'

vi.mock('../services/api', async (importOriginal) => {
  const actual = await importOriginal()
  return { ...actual, login: vi.fn() }
})

beforeEach(() => {
  vi.clearAllMocks()
})

function submit(name, pin) {
  fireEvent.change(screen.getByPlaceholderText('Name'), { target: { value: name } })
  fireEvent.change(screen.getByPlaceholderText('PIN'), { target: { value: pin } })
  fireEvent.click(screen.getByRole('button', { name: 'Login' }))
}

describe('retryMessage', () => {
  // Waits under a minute read in seconds, longer ones in whole minutes rounded up
  it('says how long to wait', () => {
    expect(retryMessage(30)).toBe('Too many failed logins. Try again in 30 seconds.')
    expect(retryMessage(60)).toBe('Too many failed logins. Try again in 1 minute.')
    expect(retryMessage(61)).toBe('Too many failed logins. Try again in 2 minutes.')
    expect(retryMessage(900)).toBe('Too many failed logins. Try again in 15 minutes.')
  })

  // Without a wait from the server the message says "later"
  it('falls back to later', () => {
    expect(retryMessage(0)).toBe('Too many failed logins. Try again later.')
  })
})

describe('LoginScreen', () => {
  // A rate-limited login shows the wait instead of "Invalid name or PIN"
  it('shows the wait when logins are rate limited', async () => {
    api.login.mockRejectedValue(new api.LoginLimitError(120))
    render(<LoginScreen onLogin={vi.fn()} />)
    submit('Alice', '999999')
    expect(await screen.findByText('Too many failed logins. Try again in 2 minutes.')).toBeInTheDocument()
  })

  // A wrong PIN still shows the plain message
  it('shows invalid name or PIN for a wrong PIN', async () => {
    api.login.mockRejectedValue(new Error('Login failed'))
    render(<LoginScreen onLogin={vi.fn()} />)
    submit('Alice', '999999')
    expect(await screen.findByText('Invalid name or PIN')).toBeInTheDocument()
  })
})
