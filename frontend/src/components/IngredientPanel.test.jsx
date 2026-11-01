/**
 * Tests for the Fridge tab's shopping suggestions: new items are listed, and an empty
 * answer (everything was a repeat) says so instead of showing nothing. The list is kept
 * on the server: Send to List moves only the checked items, × removes one item, ▲/▼ hides
 * the list without clearing it, Suggest More adds checked items at the end, the list
 * reloads on a push, and a list saved in this browser moves to the server.
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

// Render the Fridge tab with this list already saved on the server
async function renderWithList(items) {
  api.getSuggestionList.mockResolvedValue({ items })
  render(<IngredientPanel visible />)
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

  // ▲/▼ hides the list (the header shows the count) and shows it again, without clearing it
  it('hides and shows the list without clearing it', async () => {
    await renderWithList([SALMON, KIWI])
    fireEvent.click(screen.getByRole('button', { name: /Suggestions/ }))
    expect(screen.queryByText('Salmon')).toBeNull()
    expect(screen.getByRole('button', { name: /Suggestions \(2\)/ })).toHaveAttribute('aria-expanded', 'false')
    fireEvent.click(screen.getByRole('button', { name: /Suggestions/ }))
    expect(screen.getByText('Salmon')).toBeInTheDocument()
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
