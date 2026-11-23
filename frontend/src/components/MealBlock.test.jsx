/**
 * Tests for the chat meal card's readiness indicator (icon background).
 * The backend check is mocked — no real network calls are made.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import MealBlock from './MealBlock'
import { checkMissingIngredients, addFavorite } from '../services/api'
import { emojiFor } from '../utils/emoji'

vi.mock('../services/api', () => ({
  checkMissingIngredients: vi.fn(),
  addFavorite: vi.fn(),
  deleteFavorite: vi.fn(),
  getFavorites: vi.fn(() => Promise.resolve([])),
}))

const MEAL = {
  menu_name: 'Test Breakfast',
  menu: [
    { name: 'Olives', amount: 10, unit: 'adet', ingredients: [] },
    { name: 'Bread', amount: 1, unit: 'dilim', ingredients: [] },
  ],
}

describe('MealBlock readiness', () => {
  beforeEach(() => { vi.mocked(checkMissingIngredients).mockReset() })

  it('shows "not ready" with the missing items when something is not in the fridge', async () => {
    checkMissingIngredients.mockResolvedValue({ missing: ['Olives'] })
    render(<MealBlock meal={MEAL} />)
    expect(await screen.findByTitle('Not ready — missing: Olives')).toBeInTheDocument()
  })

  // The card's title shows the name and prep time, without the meal's id
  it('shows no id on the card', async () => {
    checkMissingIngredients.mockResolvedValue({ missing: [] })
    render(<MealBlock meal={{ ...MEAL, id: 7, prep_time_min: 15 }} />)
    expect(await screen.findByText('Test Breakfast')).toBeInTheDocument()
    expect(screen.queryByText('#7')).toBeNull()
  })

  it('shows "ready" when everything is in the fridge', async () => {
    checkMissingIngredients.mockResolvedValue({ missing: [] })
    render(<MealBlock meal={MEAL} />)
    expect(await screen.findByTitle('Ready — everything is in your fridge')).toBeInTheDocument()
  })

  it('counts items marked as obtained as available', async () => {
    checkMissingIngredients.mockResolvedValue({ missing: ['Olives'] })
    render(<MealBlock meal={{ ...MEAL, obtained: ['Olives'] }} />)
    expect(await screen.findByTitle('Ready — everything is in your fridge')).toBeInTheDocument()
  })

  it('shows no indicator when the check fails', async () => {
    checkMissingIngredients.mockRejectedValue(new Error('offline'))
    render(<MealBlock meal={MEAL} />)
    await waitFor(() => expect(checkMissingIngredients).toHaveBeenCalled())
    expect(screen.queryByTitle(/ready/i)).toBeNull()
  })

  // The card shows the icon the server gave its meal, the same on every render (#244)
  it("shows the meal's saved icon", async () => {
    checkMissingIngredients.mockResolvedValue({ missing: [] })
    const { rerender } = render(<MealBlock meal={{ ...MEAL, emoji: '🥯' }} />)
    expect(await screen.findByTitle('Ready — everything is in your fridge')).toHaveTextContent('🥯')
    rerender(<MealBlock meal={{ ...MEAL, emoji: '🥯' }} />)
    expect(screen.getByTitle('Ready — everything is in your fridge')).toHaveTextContent('🥯')
  })

  // An older card without an icon gets the same one from its name every time
  it('gives an older card a stable icon', async () => {
    checkMissingIngredients.mockResolvedValue({ missing: [] })
    render(<MealBlock meal={MEAL} />)
    expect(await screen.findByTitle('Ready — everything is in your fridge')).toHaveTextContent(emojiFor('Test Breakfast'))
  })

  // The ready and missing rings sit on a neutral tile in the mode's green and yellow, with no tinted fill
  it('draws the readiness as a ring on a neutral tile', async () => {
    checkMissingIngredients.mockResolvedValueOnce({ missing: [] }).mockResolvedValueOnce({ missing: ['Olives'] })
    render(<MealBlock meal={MEAL} />)
    const ready = await screen.findByTitle('Ready — everything is in your fridge')
    expect(ready.style.background).toBe('var(--surface)')
    expect(ready.style.border).toBe('var(--ring-w) solid var(--c-ring-ready)')
    render(<MealBlock meal={MEAL} fridgeCheckKey={1} />)
    const missing = await screen.findByTitle('Not ready — missing: Olives')
    expect(missing.style.background).toBe('var(--surface)')
    expect(missing.style.border).toBe('var(--ring-w) solid var(--c-ring-missing)')
  })

  // Saving a card to Favorites copies its icon
  it('copies the icon to a new favorite', async () => {
    checkMissingIngredients.mockResolvedValue({ missing: [] })
    addFavorite.mockResolvedValue({ id: 3 })
    render(<MealBlock meal={{ ...MEAL, emoji: '🥯' }} />)
    fireEvent.click(await screen.findByText('Test Breakfast'))
    fireEvent.click(await screen.findByTitle(/favorite/i))
    await waitFor(() => expect(addFavorite).toHaveBeenCalled())
    expect(addFavorite).toHaveBeenCalledWith(expect.objectContaining({ emoji: '🥯' }))
  })
})
