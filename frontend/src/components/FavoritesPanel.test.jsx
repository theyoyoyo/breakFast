/**
 * Tests for the Favorites list: the readiness badge (same as chat cards), each favorite's id
 * beside its name, the tab's name in the header, and a rename to a taken name.
 * API calls are mocked — no real network calls are made.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import FavoritesPanel from './FavoritesPanel'
import { getFavorites, checkMissingIngredients, updateFavorite } from '../services/api'

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

  // Each favorite shows its id next to its name, and the header names the tab
  it('shows each favorite\'s id and the tab name', async () => {
    render(<FavoritesPanel visible />)
    expect((await screen.findByText('Menemen Plate')).nextSibling).toHaveTextContent('#1')
    expect(screen.getByText('Avocado Toast').nextSibling).toHaveTextContent('#2')
    expect(screen.getByText('Favorites')).toBeInTheDocument()
  })

  // A rename to another favorite's name is refused by the server: the editor stays open with the
  // typed name and a note
  it('keeps the editor open when the new name is taken', async () => {
    updateFavorite.mockRejectedValueOnce(Object.assign(new Error('API error 409'), { status: 409 }))
    render(<FavoritesPanel visible />)
    fireEvent.click(await screen.findByText('Avocado Toast'))
    fireEvent.click(screen.getByText('✏️ Edit'))
    fireEvent.change(screen.getByDisplayValue('Avocado Toast'), { target: { value: 'Menemen Plate' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))
    expect(await screen.findByText('Another favorite already has this name. Pick a new one to save.')).toBeInTheDocument()
    expect(screen.getByDisplayValue('Menemen Plate')).toBeInTheDocument()
    expect(updateFavorite.mock.calls[0][0]).toBe(2)
  })
})
