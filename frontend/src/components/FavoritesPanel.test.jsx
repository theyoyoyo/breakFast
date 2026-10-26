/**
 * Tests for the Favorites list's readiness badge (same as chat cards).
 * API calls are mocked — no real network calls are made.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import FavoritesPanel from './FavoritesPanel'
import { getFavorites, checkMissingIngredients } from '../services/api'

vi.mock('../services/api', () => ({
  getFavorites: vi.fn(),
  deleteFavorite: vi.fn(),
  updateFavorite: vi.fn(),
  checkMissingIngredients: vi.fn(),
}))

const FAVORITES = [
  { id: 1, meal_name: 'Menemen Plate', menu_items: [{ name: 'Eggs', amount: 2, unit: 'adet', ingredients: [] }] },
  { id: 2, meal_name: 'Avocado Toast', menu_items: [{ name: 'Avocado', amount: 1, unit: 'adet', ingredients: [] }] },
]

describe('FavoritesPanel readiness', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    getFavorites.mockResolvedValue(FAVORITES)
    checkMissingIngredients.mockImplementation(meal =>
      Promise.resolve({ missing: meal.menu.some(i => i.name === 'Avocado') ? ['Avocado'] : [] }))
  })

  it('shows a ready badge or the missing items on each favorite', async () => {
    render(<FavoritesPanel visible />)
    expect(await screen.findByTitle('Ready — everything is in your fridge')).toBeInTheDocument()
    expect(await screen.findByTitle('Not ready — missing: Avocado')).toBeInTheDocument()
    expect(checkMissingIngredients.mock.calls[0][0].menu).toEqual(FAVORITES[0].menu_items)
  })
})
