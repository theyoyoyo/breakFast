/**
 * Tests for the shopping list panel: Select all and Delete all in the header, like the Fridge's
 * suggestions list; a checked item's best before date ("BBD:") on its own row; × to remove an item.
 * API calls are mocked — no real network calls are made.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import ShoppingListPanel from './ShoppingListPanel'
import * as api from '../services/api'

vi.mock('../services/api', () => ({
  getShoppingList: vi.fn(),
  addShoppingItem: vi.fn(() => Promise.resolve({})),
  deleteShoppingItem: vi.fn(() => Promise.resolve()),
  buyShoppingItems: vi.fn(() => Promise.resolve({ bought: 1 })),
  clearShoppingList: vi.fn(() => Promise.resolve()),
}))

const ITEMS = [
  { id: 1, item_name: 'Kiwi', created_at: '2026-11-05' },
  { id: 2, item_name: 'Salmon', created_at: '2026-11-05' },
]

describe('ShoppingListPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    api.getShoppingList.mockResolvedValue(ITEMS)
  })

  // Select all checks every item for Done, and a second tap unchecks them all
  it('selects and unselects every item', async () => {
    render(<ShoppingListPanel open onClose={() => {}} />)
    fireEvent.click(await screen.findByRole('button', { name: 'Select all' }))
    expect(screen.getAllByRole('checkbox').every(box => box.checked)).toBe(true)
    expect(screen.getByRole('button', { name: 'Done (2) ✓' })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Unselect all' }))
    expect(screen.getAllByRole('checkbox').some(box => box.checked)).toBe(false)
  })

  // Delete all empties the list, on the server too
  it('deletes every item', async () => {
    render(<ShoppingListPanel open onClose={() => {}} />)
    fireEvent.click(await screen.findByRole('button', { name: 'Delete all' }))
    expect(await screen.findByText('Shopping list is empty')).toBeInTheDocument()
    expect(api.clearShoppingList).toHaveBeenCalledTimes(1)
  })

  // A checked item asks for its best before date on its own row, and the date goes with Done
  it("asks for the best before date on the checked item's row", async () => {
    const onBought = vi.fn()
    render(<ShoppingListPanel open onClose={() => {}} onBought={onBought} />)
    fireEvent.click(await screen.findByRole('checkbox', { name: 'Kiwi' }))
    const date = screen.getByLabelText('Best before date for Kiwi')
    expect(date.closest('label').parentElement).toBe(screen.getByText('Kiwi').closest('label').parentElement)
    expect(screen.getByText('BBD:')).toBeInTheDocument()
    expect(screen.queryByText('Expiry:')).toBeNull()
    fireEvent.change(date, { target: { value: '2026-11-20' } })
    fireEvent.click(screen.getByRole('button', { name: 'Done (1) ✓' }))
    await waitFor(() => expect(api.buyShoppingItems).toHaveBeenCalledWith([1], { Kiwi: '2026-11-20' }))
    expect(onBought).toHaveBeenCalled()
  })

  // × removes one item; the list has no trash can per row
  it('removes an item with ×', async () => {
    render(<ShoppingListPanel open onClose={() => {}} />)
    fireEvent.click(await screen.findByRole('button', { name: 'Remove Kiwi' }))
    expect(screen.queryByText('Kiwi')).toBeNull()
    expect(screen.getByText('Salmon')).toBeInTheDocument()
    expect(api.deleteShoppingItem).toHaveBeenCalledWith(1)
    expect(screen.getByRole('button', { name: 'Remove Salmon' })).toHaveTextContent('×')
  })
})
