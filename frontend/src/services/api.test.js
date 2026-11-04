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
  LoginLimitError,
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
    createChatSocket(vi.fn(), onDone, vi.fn(), null, null, null, null, onSessionUpdated)
    sockets[0].onmessage({ data: JSON.stringify({ type: 'done', content: 'Hi', message_id: 5 }) })
    sockets[0].onmessage({ data: JSON.stringify({ type: 'session_updated', session_id: 's1' }) })
    expect(onDone).toHaveBeenCalledWith('Hi', 5)
    expect(onSessionUpdated).toHaveBeenCalledWith('s1')
    vi.unstubAllGlobals()
  })
})
