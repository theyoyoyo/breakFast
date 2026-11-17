/**
 * Tests for the api.js service layer.
 * `fetch` is stubbed globally — no real network calls are made.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import {
  getIngredients,
  addIngredient,
  deleteIngredient,
  setPreference,
  getMeals,
  updateSessionMessage,
  createChatSocket,
  login,
  logout,
  LoginLimitError,
  NetworkError,
  onSessionEnded,
  getRemovedSuggestionCount,
  bringBackRemovedSuggestions,
} from './api'


function mockFetch(status, body) {
  return vi.fn().mockResolvedValue({
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(body),
  })
}

beforeEach(() => {
  vi.restoreAllMocks()
})


describe('apiFetch error handling', () => {
  it('throws on non-2xx responses', async () => {
    vi.stubGlobal('fetch', mockFetch(404, { detail: 'Not found' }))
    await expect(getIngredients()).rejects.toThrow('API error 404')
  })

  it('returns undefined for 204 No Content', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, status: 204 }))
    const result = await deleteIngredient(1)
    expect(result).toBeUndefined()
  })
})


describe('ended session', () => {
  let ended
  let stopListening

  function storeSession(token) {
    localStorage.setItem('bf_token', token)
    localStorage.setItem('bf_user', JSON.stringify({ id: 1, name: 'Alice' }))
  }

  beforeEach(() => {
    localStorage.clear()
    ended = vi.fn()
    stopListening?.()
    stopListening = onSessionEnded(ended)
  })

  // A 401 clears the stored session, tells the app once, and still throws for the caller
  it('clears the stored session and tells the app on 401', async () => {
    storeSession('tok-1')
    const stub = mockFetch(401, { detail: 'Not authenticated' })
    vi.stubGlobal('fetch', stub)
    const err = await getIngredients().catch(e => e)
    expect(err.status).toBe(401)
    expect(localStorage.getItem('bf_token')).toBeNull()
    expect(localStorage.getItem('bf_user')).toBeNull()
    expect(ended).toHaveBeenCalledTimes(1)
    expect(stub).toHaveBeenCalledTimes(1) // no /auth/logout for a session the server already ended
  })

  // A 401 for a request sent with an old token leaves a session made meanwhile alone
  it('keeps a newer session when a 401 for an older token arrives', async () => {
    storeSession('tok-1')
    let answer
    vi.stubGlobal('fetch', vi.fn(() => new Promise(resolve => { answer = resolve })))
    const done = getIngredients().catch(e => e)
    storeSession('tok-2')
    answer({ ok: false, status: 401, json: () => Promise.resolve({}) })
    expect((await done).status).toBe(401)
    expect(localStorage.getItem('bf_token')).toBe('tok-2')
    expect(localStorage.getItem('bf_user')).not.toBeNull()
    expect(ended).not.toHaveBeenCalled()
  })

  // An unreachable server is not a logout: the session stays and the app isn't told
  it('keeps the session on a network error', async () => {
    storeSession('tok-1')
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))
    await expect(getIngredients()).rejects.toBeInstanceOf(NetworkError)
    expect(localStorage.getItem('bf_token')).toBe('tok-1')
    expect(ended).not.toHaveBeenCalled()
  })

  // Other errors (404, 500) keep the session and the app isn't told
  it('keeps the session on other errors', async () => {
    storeSession('tok-1')
    for (const status of [404, 500]) {
      vi.stubGlobal('fetch', mockFetch(status, {}))
      await expect(getIngredients()).rejects.toThrow(`API error ${status}`)
    }
    expect(localStorage.getItem('bf_token')).toBe('tok-1')
    expect(ended).not.toHaveBeenCalled()
  })
})


describe('login', () => {
  // A rate-limited login throws LoginLimitError carrying the server's Retry-After seconds
  it('throws LoginLimitError with the wait on 429', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: false,
      status: 429,
      headers: new Headers({ 'Retry-After': '30' }),
    }))
    const err = await login('Alice', '999999').catch(e => e)
    expect(err).toBeInstanceOf(LoginLimitError)
    expect(err.retryAfter).toBe(30)
  })

  // A 429 whose Retry-After the browser hides still throws LoginLimitError, with no wait
  it('throws LoginLimitError without a wait when Retry-After is missing', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 429, headers: new Headers() }))
    const err = await login('Alice', '999999').catch(e => e)
    expect(err).toBeInstanceOf(LoginLimitError)
    expect(err.retryAfter).toBe(0)
  })

  // A wrong PIN stays a plain error, not a rate limit
  it('throws a plain error on 401', async () => {
    vi.stubGlobal('fetch', mockFetch(401, { detail: 'Invalid name or pin' }))
    const err = await login('Alice', '999999').catch(e => e)
    expect(err).not.toBeInstanceOf(LoginLimitError)
    expect(err.message).toBe('Login failed')
  })
})


describe('logout', () => {
  function storeSession(token) {
    localStorage.setItem('bf_token', token)
    localStorage.setItem('bf_user', JSON.stringify({ id: 1, name: 'Alice' }))
  }

  beforeEach(() => localStorage.clear())

  // Logout ends the stored session on the server with its own token and clears it on the device
  it('POSTs /auth/logout with the session token and clears the stored session', async () => {
    storeSession('tok-1')
    const stub = vi.fn().mockResolvedValue({ ok: true, status: 204 })
    vi.stubGlobal('fetch', stub)
    await logout()
    expect(stub).toHaveBeenCalledWith(
      expect.stringMatching(/\/auth\/logout$/),
      expect.objectContaining({ method: 'POST', headers: { Authorization: 'Bearer tok-1' } }),
    )
    expect(localStorage.getItem('bf_token')).toBeNull()
    expect(localStorage.getItem('bf_user')).toBeNull()
  })

  // An unreachable server still logs the device out, without an error
  it('clears the stored session when the server cannot be reached', async () => {
    storeSession('tok-1')
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))
    await expect(logout()).resolves.toBeUndefined()
    expect(localStorage.getItem('bf_token')).toBeNull()
    expect(localStorage.getItem('bf_user')).toBeNull()
  })

  // A server error still logs the device out, without an error
  it('clears the stored session when the server answers with an error', async () => {
    storeSession('tok-1')
    vi.stubGlobal('fetch', mockFetch(500, { detail: 'Server error' }))
    await expect(logout()).resolves.toBeUndefined()
    expect(localStorage.getItem('bf_token')).toBeNull()
  })

  // The session is gone before the server answers, so a login made meanwhile keeps its new one
  it('clears the stored session before the call answers', async () => {
    storeSession('tok-1')
    let answer
    vi.stubGlobal('fetch', vi.fn(() => new Promise(resolve => { answer = resolve })))
    const done = logout()
    expect(localStorage.getItem('bf_token')).toBeNull()
    storeSession('tok-2')
    answer({ ok: true, status: 204 })
    await done
    expect(localStorage.getItem('bf_token')).toBe('tok-2')
  })

  // With no stored session there is nothing to end, so no call is made
  it('makes no call without a stored session', async () => {
    const stub = vi.fn()
    vi.stubGlobal('fetch', stub)
    await logout()
    expect(stub).not.toHaveBeenCalled()
  })
})


describe('ingredient API', () => {
  it('GET /ingredients/ calls the right URL with auth header', async () => {
    const stub = mockFetch(200, [])
    vi.stubGlobal('fetch', stub)
    await getIngredients()
    expect(stub).toHaveBeenCalledWith(
      expect.stringContaining('/ingredients/'),
      expect.objectContaining({
        headers: expect.objectContaining({
          Authorization: expect.stringContaining('Bearer'),
        }),
      }),
    )
  })

  it('POST /ingredients/ sends the ingredient payload', async () => {
    const stub = mockFetch(201, { id: 1, name: 'eggs' })
    vi.stubGlobal('fetch', stub)
    await addIngredient('eggs', '2026-04-01', '🧀 Şarküteri')
    const [, opts] = stub.mock.calls[0]
    expect(opts.method).toBe('POST')
    expect(JSON.parse(opts.body)).toEqual({ name: 'eggs', expiry_date: '2026-04-01', group_name: '🧀 Şarküteri' })
  })
})


describe('preference API', () => {
  it('PUT /preferences/{key} sends only the value in the body', async () => {
    const stub = mockFetch(200, { key: 'fav:eggs', value: 'eggs' })
    vi.stubGlobal('fetch', stub)
    await setPreference('fav:eggs', 'eggs')
    const [url, opts] = stub.mock.calls[0]
    expect(url).toContain('/preferences/fav%3Aeggs')
    expect(JSON.parse(opts.body)).toEqual({ value: 'eggs' })
  })
})


describe('shopping suggestions API', () => {
  // Settings reads the removed count and brings the removed items back on the same URL
  it('GET and DELETE /shopping/suggestions/removed', async () => {
    const stub = mockFetch(200, { count: 2 })
    vi.stubGlobal('fetch', stub)
    expect(await getRemovedSuggestionCount()).toEqual({ count: 2 })
    expect(stub.mock.calls[0][0]).toMatch(/\/shopping\/suggestions\/removed$/)
    vi.stubGlobal('fetch', mockFetch(204))
    await bringBackRemovedSuggestions()
    const [url, opts] = fetch.mock.calls[0]
    expect(url).toMatch(/\/shopping\/suggestions\/removed$/)
    expect(opts.method).toBe('DELETE')
  })
})


describe('chat sync API', () => {
  // A meal card edit PUTs the message's new content to its session message
  it('PUT /sessions/{id}/messages/{messageId} sends the new content', async () => {
    const stub = mockFetch(200, { status: 'ok' })
    vi.stubGlobal('fetch', stub)
    await updateSessionMessage('s1', 7, 'edited')
    const [url, opts] = stub.mock.calls[0]
    expect(url).toContain('/sessions/s1/messages/7')
    expect(opts.method).toBe('PUT')
    expect(JSON.parse(opts.body)).toEqual({ content: 'edited' })
  })

  // The chat socket hands done its saved message id and session_updated its session id
  it('passes the done message id and session_updated to their callbacks', () => {
    const sockets = []
    vi.stubGlobal('WebSocket', class { constructor() { sockets.push(this) } })
    const onDone = vi.fn()
    const onSessionUpdated = vi.fn()
    createChatSocket(vi.fn(), onDone, vi.fn(), null, null, null, onSessionUpdated)
    sockets[0].onmessage({ data: JSON.stringify({ type: 'done', content: 'Hi', message_id: 5 }) })
    sockets[0].onmessage({ data: JSON.stringify({ type: 'session_updated', session_id: 's1' }) })
    expect(onDone).toHaveBeenCalledWith('Hi', 5)
    expect(onSessionUpdated).toHaveBeenCalledWith('s1')
    vi.unstubAllGlobals()
  })

  // A refused message's error text reaches onDone without a message id, so the chat stops waiting, and isn't a notice
  it('passes a socket error to onDone as the reply', () => {
    const sockets = []
    vi.stubGlobal('WebSocket', class { constructor() { sockets.push(this) } })
    const onDone = vi.fn()
    const onNotice = vi.fn()
    createChatSocket(vi.fn(), onDone, vi.fn(), null, null, null, null, onNotice)
    sockets[0].onmessage({ data: JSON.stringify({ type: 'error', code: 'session_not_found', message: 'Gone' }) })
    expect(onDone).toHaveBeenCalledWith('Gone')
    expect(onNotice).not.toHaveBeenCalled()
    vi.unstubAllGlobals()
  })
})


describe('chat socket auth', () => {
  function stubSockets() {
    const sockets = []
    vi.stubGlobal('WebSocket', class {
      constructor(url, protocols) {
        this.url = url
        this.protocols = protocols
        sockets.push(this)
      }
    })
    return sockets
  }

  beforeEach(() => localStorage.clear())

  // The token goes in the Sec-WebSocket-Protocol header as bearer plus the token, and the URL carries none
  it('opens /chat with the token as a subprotocol, not in the URL', () => {
    localStorage.setItem('bf_token', 'tok-1')
    const sockets = stubSockets()
    createChatSocket(vi.fn(), vi.fn(), vi.fn())
    expect(sockets[0].url).toMatch(/\/chat$/)
    expect(sockets[0].url).not.toContain('tok-1')
    expect(sockets[0].protocols).toEqual(['bearer', 'tok-1'])
    vi.unstubAllGlobals()
  })

  // Without a stored session the socket sends bearer alone, since an empty subprotocol would throw
  it('opens /chat with bearer alone when there is no stored session', () => {
    const sockets = stubSockets()
    createChatSocket(vi.fn(), vi.fn(), vi.fn())
    expect(sockets[0].protocols).toEqual(['bearer'])
    vi.unstubAllGlobals()
  })
})
