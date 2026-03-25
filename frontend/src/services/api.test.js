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
