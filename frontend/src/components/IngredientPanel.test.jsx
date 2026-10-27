/**
 * Tests for the Fridge tab's shopping suggestions: new items are listed, and an empty
 * answer (everything was a repeat) says so instead of showing nothing.
 * API calls are mocked — no real network calls are made.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import IngredientPanel from './IngredientPanel'
import * as api from '../services/api'

vi.mock('../services/api', () => {
  const ok = (value) => vi.fn(() => Promise.resolve(value))
  return {
    getIngredients: ok([]), addIngredient: ok({}), updateIngredient: ok({}), deleteIngredient: ok({}),
    getExpiredIngredients: ok([]), getExpiredCount: ok({ count: 0 }), handleExpiredAction: ok({}),
    getShoppingSuggestions: ok({ suggestions: [], lyric: null }),
    addShoppingItemsBulk: ok({}), addShoppingItem: ok({}),
    getFavoriteIngredients: ok([]), addFavoriteIngredient: ok({}), removeFavoriteIngredient: ok({}),
    getShoppingList: ok([]), deleteShoppingItem: ok({}), buyShoppingItems: ok({}),
  }
})

describe('IngredientPanel shopping suggestions', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
  })

  it('lists the suggested products', async () => {
    api.getShoppingSuggestions.mockResolvedValueOnce({
      suggestions: [{ name: 'Salmon', reason: 'Omega-3' }], lyric: null,
    })
    render(<IngredientPanel visible />)
    fireEvent.click(await screen.findByRole('button', { name: /Suggest Shopping/ }))
    expect(await screen.findByText('Salmon')).toBeInTheDocument()
    expect(screen.queryByText(/No new items/)).toBeNull()
  })

  it('says so when nothing new came back', async () => {
    render(<IngredientPanel visible />)
    fireEvent.click(await screen.findByRole('button', { name: /Suggest Shopping/ }))
    expect(await screen.findByText(/No new items this time/)).toBeInTheDocument()
  })
})
