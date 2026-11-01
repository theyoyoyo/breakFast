/**
 * Tests for "Today I ate": Confirm waits until nothing is missing, Ate out marks missing items
 * as obtained (no logging), ⭐ Fav stores the menu in favorites, and edits survive
 * closing, going back from rating and re-opening.
 * API calls are mocked — no real network calls are made.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import DecidePanel from './DecidePanel'
import { checkMissingIngredients, getRatings, logMeal, addFavorite } from '../services/api'

vi.mock('../services/api', () => ({
  checkMissingIngredients: vi.fn(),
  getRatings: vi.fn(),
  createRating: vi.fn(() => Promise.resolve({})),
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

const confirmBtn = () => screen.getByRole('button', { name: 'Confirm' })
const ateOutBtn = () => screen.getByRole('button', { name: 'Ate out' })

describe('DecidePanel', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    getRatings.mockResolvedValue([{ product_name: 'Olives' }, { product_name: 'Bread' }])
  })

  it('disables Confirm and names the missing items', async () => {
    checkMissingIngredients.mockResolvedValue({ missing: ['Olives'] })
    render(<DecidePanel meal={MEAL} onClose={() => {}} />)
    await screen.findByText(/Not in your fridge: Olives\./)
    expect(confirmBtn()).toBeDisabled()
    expect(ateOutBtn()).toBeEnabled()
  })

  it('enables Confirm once the missing item is removed, without resetting edits', async () => {
    checkMissingIngredients.mockResolvedValueOnce({ missing: ['Olives'] }).mockResolvedValue({ missing: [] })
    render(<DecidePanel meal={MEAL} onClose={() => {}} />)
    await screen.findByText(/Not in your fridge: Olives\./)
    fireEvent.click(screen.getAllByTitle('Delete')[0]) // remove Olives
    await waitFor(() => expect(confirmBtn()).toBeEnabled())
    expect(screen.queryByText('Olives')).toBeNull()
  })

  it('Ate out marks every missing item as obtained and keeps the panel open', async () => {
    checkMissingIngredients.mockResolvedValue({ missing: ['Olives', 'Bread'] })
    const onConfirm = vi.fn()
    render(<DecidePanel meal={MEAL} onClose={() => {}} onConfirm={onConfirm} />)
    await screen.findByText(/Not in your fridge: Olives, Bread\./)
    fireEvent.click(ateOutBtn())
    await waitFor(() => expect(confirmBtn()).toBeEnabled())
    expect(screen.getByText('Olives')).toHaveAttribute('title', 'Marked as obtained — tap to undo')
    expect(logMeal).not.toHaveBeenCalled()
    expect(onConfirm).not.toHaveBeenCalled()
    expect(ateOutBtn()).toBeDisabled() // nothing left to mark
  })

  it('carries marks from the selected chat meal', async () => {
    checkMissingIngredients.mockResolvedValue({ missing: ['Olives'] })
    render(<DecidePanel meal={{ ...MEAL, obtained: ['Olives'] }} onClose={() => {}} />)
    expect(confirmBtn()).toBeDisabled() // still checking the fridge
    expect(await screen.findByTitle('Marked as obtained — tap to undo')).toHaveTextContent('Olives')
    await waitFor(() => expect(confirmBtn()).toBeEnabled())
  })

  it('saves the menu to favorites with ⭐ Fav and logs nothing', async () => {
    checkMissingIngredients.mockResolvedValue({ missing: [] })
    render(<DecidePanel meal={MEAL} onClose={() => {}} />)
    expect(screen.queryByRole('button', { name: 'Save' })).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: '⭐ Fav' }))
    expect(await screen.findByRole('button', { name: '✓ Fav' })).toBeInTheDocument()
    expect(addFavorite).toHaveBeenCalledTimes(1)
    expect(logMeal).not.toHaveBeenCalled()
  })

  // The rating step logs the meal with Confirm, like the button that logs it when there's nothing to rate
  it('names the rating step\'s button Confirm', async () => {
    checkMissingIngredients.mockResolvedValue({ missing: [] })
    getRatings.mockResolvedValue([])
    const onConfirm = vi.fn()
    render(<DecidePanel meal={MEAL} onClose={() => {}} onConfirm={onConfirm} />)
    await waitFor(() => expect(confirmBtn()).toBeEnabled())
    fireEvent.click(confirmBtn())
    expect(await screen.findByText('Rate')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Save' })).toBeNull()
    fireEvent.click(confirmBtn())
    await waitFor(() => expect(logMeal).toHaveBeenCalledTimes(1))
    expect(onConfirm).toHaveBeenCalledTimes(1)
  })

  it('reports edits as a draft and starts from that draft when reopened', async () => {
    checkMissingIngredients.mockResolvedValue({ missing: [] })
    const onDraftChange = vi.fn()
    const { unmount } = render(<DecidePanel meal={MEAL} onDraftChange={onDraftChange} onClose={() => {}} />)
    fireEvent.click(screen.getAllByTitle('Delete')[0]) // remove Olives
    await waitFor(() => expect(onDraftChange.mock.calls.at(-1)[0].menu.map(i => i.name)).toEqual(['Bread']))
    const draft = onDraftChange.mock.calls.at(-1)[0]
    unmount() // close
    render(<DecidePanel meal={MEAL} draft={draft} onClose={() => {}} />) // reopen
    expect(screen.queryByText('Olives')).toBeNull()
    expect(screen.getByText('Bread')).toBeInTheDocument()
  })

  it('keeps edits when going back from the rating step', async () => {
    checkMissingIngredients.mockResolvedValue({ missing: [] })
    getRatings.mockResolvedValue([]) // nothing rated yet → Confirm opens the rating step
    render(<DecidePanel meal={MEAL} onClose={() => {}} />)
    fireEvent.click(screen.getAllByTitle('Delete')[0]) // remove Olives
    await waitFor(() => expect(confirmBtn()).toBeEnabled())
    fireEvent.click(confirmBtn())
    fireEvent.click(await screen.findByRole('button', { name: 'Back' }))
    expect(await screen.findByText('Bread')).toBeInTheDocument()
    expect(screen.queryByText('Olives')).toBeNull()
  })

  it('starts over when another chat meal is selected', async () => {
    checkMissingIngredients.mockResolvedValue({ missing: [] })
    const other = { menu_name: 'Other', menu: [{ name: 'Honey', amount: 1, unit: 'adet', ingredients: [] }] }
    const { rerender } = render(<DecidePanel meal={MEAL} onClose={() => {}} />)
    fireEvent.click(screen.getAllByTitle('Delete')[0])
    rerender(<DecidePanel meal={other} onClose={() => {}} />)
    expect(await screen.findByText('Honey')).toBeInTheDocument()
    expect(screen.queryByText('Bread')).toBeNull()
  })
})
