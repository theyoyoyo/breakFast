/**
 * Tests for "Today I ate": Confirm waits until every ingredient is in the fridge; Save does not.
 * API calls are mocked — no real network calls are made.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import DecidePanel from './DecidePanel'
import { checkMissingIngredients } from '../services/api'

vi.mock('../services/api', () => ({
  checkMissingIngredients: vi.fn(),
  getRatings: vi.fn(() => Promise.resolve([])),
  createRating: vi.fn(),
  logMeal: vi.fn(() => Promise.resolve({})),
}))

const MEAL = {
  menu_name: 'Test Breakfast',
  menu: [
    { name: 'Olives', amount: 10, unit: 'adet', ingredients: [] },
    { name: 'Bread', amount: 1, unit: 'dilim', ingredients: [] },
  ],
}

describe('DecidePanel fridge check', () => {
  beforeEach(() => vi.mocked(checkMissingIngredients).mockReset())

  it('disables Confirm and names the missing items, but keeps Save enabled', async () => {
    checkMissingIngredients.mockResolvedValue({ missing: ['Olives'] })
    render(<DecidePanel meal={MEAL} onClose={() => {}} />)
    await screen.findByText(/Not in your fridge: Olives\./)
    expect(screen.getByRole('button', { name: 'Confirm' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Save' })).toBeEnabled()
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
})
