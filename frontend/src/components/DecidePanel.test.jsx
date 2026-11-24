/**
 * Tests for "Today I ate": Confirm waits until nothing is missing and comes last, the ☆ adds
 * the menu to favorites and a second tap removes it, Save stores the edited meal with its
 * chat card, the panel opens from the card's saved version, edits survive going back from
 * rating, Skip logs without ratings, and a changed card never resets an open panel.
 * API calls are mocked — no real network calls are made.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import DecidePanel from './DecidePanel'
import { checkMissingIngredients, getRatings, createRating, logMeal, addFavorite, deleteFavorite } from '../services/api'

vi.mock('../services/api', () => ({
  checkMissingIngredients: vi.fn(),
  getRatings: vi.fn(),
  createRating: vi.fn(() => Promise.resolve({})),
  logMeal: vi.fn(() => Promise.resolve({})),
  addFavorite: vi.fn(() => Promise.resolve({ id: 12 })),
  deleteFavorite: vi.fn(() => Promise.resolve()),
  getFavorites: vi.fn(() => Promise.resolve([])),
}))

const MEAL = {
  menu_name: 'Test Breakfast',
  menu: [
    { name: 'Olives', amount: 10, unit: 'adet', ingredients: [] },
    { name: 'Bread', amount: 1, unit: 'dilim', ingredients: [] },
  ],
}

const confirmBtn = () => screen.getByRole('button', { name: 'Confirm' })

describe('DecidePanel', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    getRatings.mockResolvedValue([{ product_name: 'Olives' }, { product_name: 'Bread' }])
  })

  // A meal can't be logged as eaten while an item isn't in the fridge, and the note says which one
  it('disables Confirm and names the missing items', async () => {
    checkMissingIngredients.mockResolvedValue({ missing: ['Olives'] })
    render(<DecidePanel meal={MEAL} onClose={() => {}} />)
    await screen.findByText(/Not in your fridge: Olives\./)
    expect(confirmBtn()).toBeDisabled()
    expect(screen.queryByRole('button', { name: 'Ate out' })).toBeNull()
  })

  // Removing the missing item frees Confirm without throwing away the user's other edits
  it('enables Confirm once the missing item is removed, without resetting edits', async () => {
    checkMissingIngredients.mockResolvedValueOnce({ missing: ['Olives'] }).mockResolvedValue({ missing: [] })
    render(<DecidePanel meal={MEAL} onClose={() => {}} />)
    await screen.findByText(/Not in your fridge: Olives\./)
    fireEvent.click(screen.getAllByTitle('Delete')[0]) // remove Olives
    await waitFor(() => expect(confirmBtn()).toBeEnabled())
    expect(screen.queryByText('Olives')).toBeNull()
  })

  // Close, Save, Confirm: Confirm, which logs the meal, is the last button
  it('puts Confirm at the end', async () => {
    checkMissingIngredients.mockResolvedValue({ missing: [] })
    render(<DecidePanel meal={MEAL} onSave={vi.fn()} onClose={() => {}} />)
    const row = confirmBtn().parentElement
    expect([...row.querySelectorAll('button')].map(b => b.textContent)).toEqual(['Close', 'Save', 'Confirm'])
  })

  // Items marked as obtained on the chat card count as available here, once the fridge check has answered
  it('carries marks from the selected chat meal', async () => {
    checkMissingIngredients.mockResolvedValue({ missing: ['Olives'] })
    render(<DecidePanel meal={{ ...MEAL, obtained: ['Olives'] }} onClose={() => {}} />)
    expect(confirmBtn()).toBeDisabled() // still checking the fridge
    expect(await screen.findByTitle('Marked as obtained — tap to undo')).toHaveTextContent('Olives')
    await waitFor(() => expect(confirmBtn()).toBeEnabled())
  })

  // The ☆ left of the name adds the menu to favorites; a second tap removes that favorite
  it('adds the menu to favorites with the star and removes it with a second tap', async () => {
    checkMissingIngredients.mockResolvedValue({ missing: [] })
    render(<DecidePanel meal={MEAL} onClose={() => {}} />)
    expect(screen.queryByRole('button', { name: 'Save' })).toBeNull() // no card to save to
    await waitFor(() => expect(screen.getByRole('button', { name: 'Add to favorites' })).toBeEnabled())
    fireEvent.click(screen.getByRole('button', { name: 'Add to favorites' }))
    const star = await screen.findByRole('button', { name: 'Remove from favorites' })
    expect(star).toHaveAttribute('aria-pressed', 'true')
    expect(addFavorite).toHaveBeenCalledTimes(1)
    fireEvent.click(star)
    await waitFor(() => expect(deleteFavorite).toHaveBeenCalledWith(12))
    expect(await screen.findByRole('button', { name: 'Add to favorites' })).toHaveAttribute('aria-pressed', 'false')
    expect(logMeal).not.toHaveBeenCalled()
  })

  // Save sends the edited meal, then closes the panel; nothing is logged
  it('Save sends the current meal and closes', async () => {
    checkMissingIngredients.mockResolvedValue({ missing: [] })
    const onSave = vi.fn(() => Promise.resolve())
    const onClose = vi.fn()
    render(<DecidePanel meal={MEAL} onSave={onSave} onClose={onClose} />)
    fireEvent.click(screen.getAllByTitle('Delete')[0]) // remove Olives
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))
    await waitFor(() => expect(onClose).toHaveBeenCalledTimes(1))
    expect(onSave).toHaveBeenCalledTimes(1)
    expect(onSave).toHaveBeenCalledWith(expect.objectContaining({ menu: [expect.objectContaining({ name: 'Bread' })] }))
    expect(logMeal).not.toHaveBeenCalled()
  })

  // A failed Save says so, stays open and lets the user try again
  it('stays open and tells the user when Save fails', async () => {
    checkMissingIngredients.mockResolvedValue({ missing: [] })
    const onClose = vi.fn()
    render(<DecidePanel meal={MEAL} onSave={() => Promise.reject(new Error('offline'))} onClose={onClose} />)
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))
    expect(await screen.findByText(/Couldn't save/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Save' })).toBeEnabled()
    expect(onClose).not.toHaveBeenCalled()
  })

  // Opening starts from the card's saved version, not the card
  it('opens from the saved version', async () => {
    checkMissingIngredients.mockResolvedValue({ missing: [] })
    const saved = { ...MEAL, menu: [MEAL.menu[1]] } // Bread only
    render(<DecidePanel meal={MEAL} saved={saved} onSave={vi.fn()} onClose={() => {}} />)
    expect(screen.queryByText('Olives')).toBeNull()
    expect(screen.getByText('Bread')).toBeInTheDocument()
  })

  // Back from the rating step returns to the edited menu, not the original one
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

  // Skip, between Back and Confirm, logs the meal without saving any rating
  it('logs the meal without ratings on Skip', async () => {
    checkMissingIngredients.mockResolvedValue({ missing: [] })
    getRatings.mockResolvedValue([])
    const onConfirm = vi.fn()
    render(<DecidePanel meal={MEAL} onClose={() => {}} onConfirm={onConfirm} />)
    await waitFor(() => expect(confirmBtn()).toBeEnabled())
    fireEvent.click(confirmBtn())
    const skip = await screen.findByRole('button', { name: 'Skip' })
    expect([...skip.parentElement.querySelectorAll('button')].map(b => b.textContent)).toEqual(['Back', 'Skip', 'Confirm'])
    fireEvent.click(skip)
    await waitFor(() => expect(onConfirm).toHaveBeenCalledTimes(1))
    expect(logMeal).toHaveBeenCalledTimes(1)
    expect(createRating).not.toHaveBeenCalled()
  })

  // A push from another device (a new card or saved version) never resets an open panel
  it('keeps its edits when the card changes while open', async () => {
    checkMissingIngredients.mockResolvedValue({ missing: [] })
    const other = { menu_name: 'Other', menu: [{ name: 'Honey', amount: 1, unit: 'adet', ingredients: [] }] }
    const { rerender } = render(<DecidePanel meal={MEAL} onClose={() => {}} />)
    fireEvent.click(screen.getAllByTitle('Delete')[0]) // remove Olives
    rerender(<DecidePanel meal={other} saved={other} onClose={() => {}} />)
    expect(screen.getByText('Bread')).toBeInTheDocument()
    expect(screen.queryByText('Honey')).toBeNull()
    expect(screen.queryByText('Olives')).toBeNull()
  })

  describe('supplements', () => {
    const SUPPS = [
      { id: 1, name: 'Vitamin D', frequency: 'daily', taken_today: 1 },
      { id: 2, name: 'Magnesium', frequency: 'sometimes', taken_today: 0 },
    ]

    // The 💊 button reveals today's supplements: daily ones ticked, occasional ones not
    it('reveals daily supplements ticked and occasional ones not', async () => {
      checkMissingIngredients.mockResolvedValue({ missing: [] })
      render(<DecidePanel meal={MEAL} onClose={() => {}} supplements={SUPPS} />)
      fireEvent.click(screen.getByRole('button', { name: 'Supplements' }))
      expect(screen.getByRole('button', { name: '✓ Vitamin D' })).toHaveAttribute('aria-pressed', 'true')
      expect(screen.getByRole('button', { name: 'Magnesium' })).toHaveAttribute('aria-pressed', 'false')
    })

    // A tap on a chip flips it at once, with its state before the tap
    it('flips a supplement with one tap', async () => {
      checkMissingIngredients.mockResolvedValue({ missing: [] })
      const onToggle = vi.fn()
      render(<DecidePanel meal={MEAL} onClose={() => {}} supplements={SUPPS} onToggleSupplement={onToggle} />)
      fireEvent.click(screen.getByRole('button', { name: 'Supplements' }))
      fireEvent.click(screen.getByRole('button', { name: '✓ Vitamin D' }))
      fireEvent.click(screen.getByRole('button', { name: 'Magnesium' }))
      expect(onToggle).toHaveBeenCalledTimes(2)
      expect(onToggle).toHaveBeenNthCalledWith(1, 1, true)
      expect(onToggle).toHaveBeenNthCalledWith(2, 2, false)
      expect(screen.getByRole('group', { name: "Today's supplements" })).toBeInTheDocument() // still open
    })

    // Confirm works with the list open, and a tap anywhere else in the panel closes the list
    it('keeps the list for Confirm and closes it on a tap elsewhere', async () => {
      checkMissingIngredients.mockResolvedValue({ missing: [] })
      const onConfirm = vi.fn()
      render(<DecidePanel meal={MEAL} onClose={() => {}} onConfirm={onConfirm} supplements={SUPPS} />)
      fireEvent.click(screen.getByRole('button', { name: 'Supplements' }))
      fireEvent.click(screen.getByText('Today I ate'))
      expect(screen.queryByRole('group', { name: "Today's supplements" })).toBeNull()

      fireEvent.click(screen.getByRole('button', { name: 'Supplements' }))
      await waitFor(() => expect(confirmBtn()).toBeEnabled())
      fireEvent.click(confirmBtn())
      await waitFor(() => expect(logMeal).toHaveBeenCalledTimes(1))
      expect(onConfirm).toHaveBeenCalled()
    })
  })
})

describe('DecidePanel title row', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    getRatings.mockResolvedValue([])
    checkMissingIngredients.mockResolvedValue({ missing: [] })
  })

  // The star sits in the title row beside "Today I ate", and the meal icon takes its place left of the name
  it('puts the star in the title row and the icon beside the name', async () => {
    render(<DecidePanel meal={{ ...MEAL, emoji: '🥐' }} onClose={() => {}} />)
    const star = await screen.findByRole('button', { name: 'Add to favorites' })
    expect(star.closest('div').textContent).toContain('Today I ate')
    const icon = screen.getByRole('img', { name: 'Meal icon' })
    expect(icon).toHaveTextContent('🥐')
    expect(icon.nextElementSibling).toHaveValue('Test Breakfast')
  })
})
