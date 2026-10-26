/**
 * Tests for the chat meal card's readiness indicator (icon background).
 * The backend check is mocked — no real network calls are made.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import MealBlock from './MealBlock'
import { checkMissingIngredients } from '../services/api'

vi.mock('../services/api', () => ({
  checkMissingIngredients: vi.fn(),
  addFavorite: vi.fn(),
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
})
