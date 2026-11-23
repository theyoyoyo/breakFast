/**
 * Tests for the Favorites list: the readiness badge (same as chat cards), each favorite's id
 * beside its name, the tab's name in the header, and a rename to a taken name.
 * API calls are mocked — no real network calls are made.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import FavoritesPanel from './FavoritesPanel'
import { emojiFor } from '../utils/emoji'
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
    expect(checkMissingIngredients).toHaveBeenCalledWith(expect.objectContaining({ menu: FAVORITES[0].menu_items }))
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
    expect(updateFavorite).toHaveBeenCalledWith(2, expect.objectContaining({ meal_name: 'Menemen Plate' }))
  })

  // A favorite shows its saved icon, and an older one without an icon the one from its id
  it('shows a saved icon or the id-based one', async () => {
    getFavorites.mockResolvedValue([{ ...FAVORITES[0], emoji: '🥯' }, FAVORITES[1]])
    render(<FavoritesPanel visible />)
    expect((await screen.findByText('Menemen Plate')).previousSibling).toHaveTextContent('🥯')
    expect(screen.getByText('Avocado Toast').previousSibling).toHaveTextContent(emojiFor(2))
  })

  // The editor's picker offers the app's icons and Save sends the picked one with the edit
  it('changes the icon in the editor', async () => {
    updateFavorite.mockResolvedValue({ status: 'ok' })
    render(<FavoritesPanel visible />)
    fireEvent.click(await screen.findByText('Avocado Toast'))
    fireEvent.click(screen.getByText('✏️ Edit'))
    fireEvent.click(screen.getByTitle("Change this favorite's icon"))
    fireEvent.click(screen.getByRole('button', { name: 'Icon 🧇' }))
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))
    await vi.waitFor(() => expect(updateFavorite).toHaveBeenCalled())
    expect(updateFavorite).toHaveBeenCalledWith(2, expect.objectContaining({ emoji: '🧇' }))
    expect((await screen.findByText('Avocado Toast')).previousSibling).toHaveTextContent('🧇')
  })

  // A favorite sent to chat carries its icon, the id-based one for an older favorite
  it('sends its icon to chat', async () => {
    const onSendToChat = vi.fn()
    render(<FavoritesPanel visible onSendToChat={onSendToChat} />)
    fireEvent.click(await screen.findByText('Avocado Toast'))
    fireEvent.click(screen.getByText('🫕 Send to Chat'))
    expect(onSendToChat).toHaveBeenCalledWith(expect.objectContaining({ emoji: emojiFor(2) }))
  })
})
