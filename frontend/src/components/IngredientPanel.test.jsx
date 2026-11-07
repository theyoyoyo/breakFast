/**
 * Tests for the Fridge tab's shopping suggestions: new items are listed, and an empty
 * answer (everything was a repeat) says so instead of showing nothing. The list is kept
 * on the server: it starts collapsed, Send to List moves only the checked items, × removes one
 * item, ▲/▼ hides the list without clearing it, the header's helpers check or uncheck every
 * item and clear the list after an "Are you sure?", Suggest More adds checked items at the end, the list reloads on a
 * push, and a list saved in this browser moves to the server.
 * API calls are mocked — no real network calls are made.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor, act, within } from '@testing-library/react'
import IngredientPanel from './IngredientPanel'
import { emitSyncNotice } from '../hooks/useSyncNotice'
import * as api from '../services/api'

vi.mock('../services/api', () => {
  const ok = (value) => vi.fn(() => Promise.resolve(value))
  return {
    getIngredients: ok([]), addIngredient: ok({}), updateIngredient: ok({}), deleteIngredient: ok({}),
    getExpiredIngredients: ok([]), getExpiredCount: ok({ count: 0 }), handleExpiredAction: ok({}),
    getShoppingSuggestions: ok({ suggestions: [], lyric: null }),
    getSuggestionList: ok({ items: [] }),
    saveSuggestionList: vi.fn((items) => Promise.resolve({ items })),
    addShoppingItemsBulk: ok({}), addShoppingItem: ok({}),
    getFavoriteIngredients: ok([]), addFavoriteIngredient: ok({}), removeFavoriteIngredient: ok({}),
    getShoppingList: ok([]), deleteShoppingItem: ok({}), buyShoppingItems: ok({}),
  }
})

const SALMON = { name: 'Salmon', reason: 'Omega-3', checked: true }
const KIWI = { name: 'Kiwi', reason: 'In season', checked: false }
const OATS = { name: 'Rolled oats', reason: 'Fiber', checked: true }

const checkboxFor = (name) => screen.getByRole('checkbox', { name: new RegExp(name) })
const lastSaved = () => api.saveSuggestionList.mock.calls.at(-1)

const header = () => screen.getByRole('button', { name: /^Suggestions \(/ })

// Render the Fridge tab with this list already saved on the server, and open the list
async function renderWithList(items) {
  api.getSuggestionList.mockResolvedValue({ items })
  render(<IngredientPanel visible />)
  fireEvent.click(await screen.findByRole('button', { name: `Suggestions (${items.length})` }))
  await screen.findByText(items[0].name)
}

describe('IngredientPanel shopping suggestions', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
    api.getSuggestionList.mockResolvedValue({ items: [] })
  })

  it('lists the suggested products', async () => {
    api.getShoppingSuggestions.mockResolvedValueOnce({
      suggestions: [{ name: 'Salmon', reason: 'Omega-3' }], lyric: null,
    })
    render(<IngredientPanel visible />)
    fireEvent.click(await screen.findByRole('button', { name: /Suggest Shopping/ }))
    expect(await screen.findByText('Salmon')).toBeInTheDocument()
    expect(screen.queryByText(/No new items/)).toBeNull()
    expect(lastSaved()).toEqual([[SALMON], []])
  })

  it('says so when nothing new came back', async () => {
    render(<IngredientPanel visible />)
    fireEvent.click(await screen.findByRole('button', { name: /Suggest Shopping/ }))
    expect(await screen.findByText(/No new items this time/)).toBeInTheDocument()
  })

  // Suggest More adds new items at the end, checked, and the old items keep their checks
  it('adds Suggest More items at the end, checked, keeping old checks', async () => {
    await renderWithList([SALMON, KIWI])
    api.getShoppingSuggestions.mockResolvedValueOnce({
      suggestions: [{ name: 'kiwi', reason: 'Again' }, { name: 'Rolled oats', reason: 'Fiber' }], lyric: null,
    })
    fireEvent.click(screen.getByRole('button', { name: /Suggest More/ }))
    expect(await screen.findByText('Rolled oats')).toBeInTheDocument()
    expect(api.getShoppingSuggestions).toHaveBeenCalledWith(['Salmon', 'Kiwi'])
    expect(lastSaved()).toEqual([[SALMON, KIWI, OATS], []])
    expect(checkboxFor('Kiwi')).not.toBeChecked()
  })

  // Send to List moves the checked items to the shopping list and keeps the unchecked ones
  it('sends only the checked items and keeps the rest', async () => {
    await renderWithList([SALMON, KIWI, OATS])
    fireEvent.click(screen.getByRole('button', { name: /Send to List \(2\)/ }))
    await waitFor(() => expect(api.addShoppingItemsBulk).toHaveBeenCalledWith(['Salmon', 'Rolled oats']))
    await waitFor(() => expect(lastSaved()).toEqual([[KIWI], []]))
    expect(screen.getByText('Kiwi')).toBeInTheDocument()
    expect(screen.queryByText('Salmon')).toBeNull()
  })

  // × removes one item and tells the server it was removed, so it isn't suggested again for a while
  it('removes one item with ×', async () => {
    await renderWithList([SALMON, KIWI])
    fireEvent.click(screen.getByRole('button', { name: 'Remove Salmon' }))
    expect(lastSaved()).toEqual([[KIWI], ['Salmon']])
    expect(screen.queryByText('Salmon')).toBeNull()
    expect(screen.getByText('Kiwi')).toBeInTheDocument()
  })

  // A tap on a checkbox saves the new check
  it('saves a check change', async () => {
    await renderWithList([SALMON, KIWI])
    fireEvent.click(checkboxFor('Kiwi'))
    expect(lastSaved()).toEqual([[SALMON, { ...KIWI, checked: true }], []])
  })

  // The list starts collapsed: only the header with the count shows
  it('starts collapsed', async () => {
    api.getSuggestionList.mockResolvedValue({ items: [SALMON, KIWI] })
    render(<IngredientPanel visible />)
    expect(await screen.findByRole('button', { name: 'Suggestions (2)' })).toHaveAttribute('aria-expanded', 'false')
    expect(screen.queryByText('Salmon')).toBeNull()
    expect(screen.queryByRole('button', { name: 'Delete all' })).toBeNull()
  })

  // ▲/▼ hides the list and shows it again, without clearing it: ▼ while open, ▲ while closed
  it('hides and shows the list without clearing it', async () => {
    await renderWithList([SALMON, KIWI])
    expect(header()).toHaveAttribute('aria-expanded', 'true')
    expect(within(header()).getByText('▼')).toBeInTheDocument()
    fireEvent.click(header())
    expect(screen.queryByText('Salmon')).toBeNull()
    expect(header()).toHaveAttribute('aria-expanded', 'false')
    expect(within(header()).getByText('▲')).toBeInTheDocument()
    fireEvent.click(header())
    expect(screen.getByText('Salmon')).toBeInTheDocument()
    expect(api.saveSuggestionList).not.toHaveBeenCalled()
  })

  // One helper checks every item, and once all are checked it unchecks them all
  it('checks and unchecks every item with one button', async () => {
    await renderWithList([SALMON, KIWI])
    fireEvent.click(screen.getByRole('button', { name: 'Select all' }))
    expect(lastSaved()).toEqual([[SALMON, { ...KIWI, checked: true }], []])
    fireEvent.click(screen.getByRole('button', { name: 'Unselect all' }))
    expect(lastSaved()).toEqual([[{ ...SALMON, checked: false }, KIWI], []])
    expect(header()).toHaveAttribute('aria-expanded', 'true') // the helpers don't toggle the list
  })

  // The trash asks first, then clears the whole list without leaving the items out of later suggestions
  it('deletes all items after asking, without marking them removed', async () => {
    await renderWithList([SALMON, KIWI])
    fireEvent.click(screen.getByRole('button', { name: 'Delete all' }))
    const prompt = screen.getByRole('alertdialog', { name: 'Delete all suggestions' })
    expect(prompt).toHaveTextContent('Are you sure you want to delete all 2 suggestions?')
    expect(api.saveSuggestionList).not.toHaveBeenCalled()
    expect(header()).toHaveAttribute('aria-expanded', 'true') // the trash doesn't toggle the list
    fireEvent.click(within(prompt).getByRole('button', { name: 'Delete' }))
    expect(lastSaved()).toEqual([[], []])
    expect(await screen.findByRole('button', { name: /Suggest Shopping/ })).toBeInTheDocument()
  })

  // Cancel closes the prompt and keeps the list; hiding the list closes it too
  it('keeps the list when Delete all is cancelled', async () => {
    await renderWithList([SALMON, KIWI])
    fireEvent.click(screen.getByRole('button', { name: 'Delete all' }))
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))
    expect(screen.queryByRole('alertdialog')).toBeNull()
    expect(screen.getByText('Salmon')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Delete all' }))
    fireEvent.click(header())
    fireEvent.click(header())
    expect(screen.queryByRole('alertdialog')).toBeNull()
    expect(api.saveSuggestionList).not.toHaveBeenCalled()
  })

  // Send to List and Suggest More sit together under the list; Suggest Shopping isn't at the top any more
  it('puts Send to List and Suggest More together under the list', async () => {
    await renderWithList([SALMON])
    const sendToList = screen.getByRole('button', { name: /Send to List/ })
    const row = sendToList.parentElement
    expect(within(row).getByRole('button', { name: /Suggest More/ })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Suggest Shopping/ })).toBeNull()
    expect(screen.getByText('Salmon').compareDocumentPosition(sendToList) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  })

  // Another device changed the list: the push reloads it
  it('reloads the list on a push', async () => {
    await renderWithList([SALMON])
    api.getSuggestionList.mockResolvedValue({ items: [SALMON, KIWI] })
    act(() => emitSyncNotice({ type: 'shopping_suggestions_updated' }))
    expect(await screen.findByText('Kiwi')).toBeInTheDocument()
    expect(header()).toHaveTextContent('Suggestions (2)')
  })

  // A list this browser kept before moves to the server after what's there, then the local copy is cleared
  it('moves a list saved in this browser to the server on first load', async () => {
    localStorage.setItem('bf_suggestions', JSON.stringify([{ name: 'salmon', reason: 'Old' }, { name: 'Kiwi', reason: 'In season' }]))
    api.getSuggestionList.mockResolvedValue({ items: [SALMON] })
    render(<IngredientPanel visible />)
    await waitFor(() => expect(api.saveSuggestionList).toHaveBeenCalledWith([SALMON, { ...KIWI, checked: true }]))
    await waitFor(() => expect(localStorage.getItem('bf_suggestions')).toBeNull())
  })
})

describe('IngredientPanel fridge rows', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
    api.getSuggestionList.mockResolvedValue({ items: [] })
    api.getIngredients.mockResolvedValue([
      { id: 1, name: 'Tomatoes', group_name: '🥬 Produce' },
      { id: 2, name: 'Cucumber', group_name: '🥬 Produce' },
    ])
  })

  // The delete choices under a group's last row take their own line inside the group, so the card grows to show them
  it("opens the last row's delete choices inside its group, in view", async () => {
    const scrollIntoView = vi.fn()
    Element.prototype.scrollIntoView = scrollIntoView
    render(<IngredientPanel visible />)
    await screen.findByText('Cucumber')
    fireEvent.click(screen.getAllByRole('button', { name: 'Delete' }).at(-1))

    const choices = screen.getByRole('group', { name: 'Delete Cucumber' })
    expect(choices.style.position).not.toBe('absolute')
    expect(choices.previousElementSibling).toHaveTextContent('Cucumber')
    expect(scrollIntoView).toHaveBeenCalledWith({ block: 'nearest' })

    fireEvent.click(within(choices).getByRole('button', { name: 'Delete' }))
    await waitFor(() => expect(api.deleteIngredient).toHaveBeenCalledWith(2))
    delete Element.prototype.scrollIntoView
  })
})
