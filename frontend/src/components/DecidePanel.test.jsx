/**
 * Tests for "Today I ate": Confirm waits until every ingredient is in the fridge,
 * Ate out logs without the check, and ⭐ Save stores the menu in favorites without logging.
 * API calls are mocked — no real network calls are made.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import DecidePanel from './DecidePanel'
import { checkMissingIngredients, getRatings, logMeal, addFavorite } from '../services/api'

vi.mock('../services/api', () => ({
  checkMissingIngredients: vi.fn(),
  getRatings: vi.fn(),
  createRating: vi.fn(),
  logMeal: vi.fn(() => Promise.resolve({})),
  addFavorite: vi.fn(() => Promise.resolve({})),
}))

const MEAL = {
  menu_name: 'Test Breakfast',
  menu: [
    { name: 'Olives', amount: 10, unit: 'adet', ingredients: [] },
    { name: 'Bread', amount: 1, unit: 'dilim', ingredients: [] },
  ],
}

describe('DecidePanel', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    // Both items already rated, so logging skips the rating step
    getRatings.mockResolvedValue([{ product_name: 'Olives' }, { product_name: 'Bread' }])
  })

  it('disables Confirm and names the missing items, but keeps Ate out enabled', async () => {
    checkMissingIngredients.mockResolvedValue({ missing: ['Olives'] })
    render(<DecidePanel meal={MEAL} onClose={() => {}} />)
    await screen.findByText(/Not in your fridge: Olives\./)
    expect(screen.getByRole('button', { name: 'Confirm' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Ate out' })).toBeEnabled()
  })

  it('enables Confirm once nothing is missing, without resetting edits', async () => {
    checkMissingIngredients.mockResolvedValueOnce({ missing: ['Olives'] }).mockResolvedValue({ missing: [] })
    render(<DecidePanel meal={MEAL} onClose={() => {}} />)
    await screen.findByText(/Not in your fridge: Olives\./)
    fireEvent.click(screen.getAllByTitle('Delete')[0]) // remove Olives
    await waitFor(() => expect(screen.getByRole('button', { name: 'Confirm' })).toBeEnabled())
    expect(screen.queryByText('Olives')).toBeNull()
    expect(screen.queryByText(/Not in your fridge/)).toBeNull()
  })

  it('logs a meal eaten out even when its items are not in the fridge', async () => {
    checkMissingIngredients.mockResolvedValue({ missing: ['Olives'] })
    const onConfirm = vi.fn()
    render(<DecidePanel meal={MEAL} onClose={() => {}} onConfirm={onConfirm} />)
    await screen.findByText(/Not in your fridge: Olives\./)
    await waitFor(() => expect(getRatings).toHaveBeenCalled())
    fireEvent.click(screen.getByRole('button', { name: 'Ate out' }))
    await waitFor(() => expect(logMeal).toHaveBeenCalledTimes(1))
    expect(logMeal.mock.calls[0][0].menu_items.map(i => i.name)).toEqual(['Olives', 'Bread'])
    expect(onConfirm).toHaveBeenCalled()
  })

  it('saves the menu to favorites with ⭐ Save and logs nothing', async () => {
    checkMissingIngredients.mockResolvedValue({ missing: [] })
    render(<DecidePanel meal={MEAL} onClose={() => {}} />)
    expect(screen.queryByRole('button', { name: 'Save' })).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: /Save/ }))
    await waitFor(() => expect(addFavorite).toHaveBeenCalledTimes(1))
    expect(addFavorite.mock.calls[0][0].meal_name).toBe('Test Breakfast')
    expect(logMeal).not.toHaveBeenCalled()
  })
})
