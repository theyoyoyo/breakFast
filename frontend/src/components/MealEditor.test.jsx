/**
 * Tests for MealEditor's fridge check: missing ingredients are underlined, never removed.
 * The backend check is mocked — no real network calls are made.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import MealEditor from './MealEditor'
import { checkMissingIngredients } from '../services/api'

vi.mock('../services/api', () => ({ checkMissingIngredients: vi.fn() }))

const MEAL = {
  menu_name: 'Test Breakfast',
  menu: [
    { name: 'Menemen', ingredients: [
      { name: 'Yumurta', amount: 2, unit: 'adet' },
      { name: 'Avocado', amount: 1, unit: 'adet' },
    ] },
    { name: 'Olives', amount: 10, unit: 'adet', ingredients: [] },
  ],
}

describe('MealEditor fridge check', () => {
  beforeEach(() => vi.mocked(checkMissingIngredients).mockReset())

  it('underlines simple items that are not in the fridge and reports them', async () => {
    checkMissingIngredients.mockResolvedValue({ missing: ['Olives'] })
    const onMissingChange = vi.fn()
    render(<MealEditor meal={MEAL} menuMode checkFridge onMissingChange={onMissingChange} />)
    await waitFor(() => expect(onMissingChange).toHaveBeenCalledWith(['Olives']))
    const olives = screen.getByText('Olives')
    expect(olives).toHaveAttribute('title', 'Not in your fridge')
    expect(olives.style.textDecorationLine).toBe('underline')
    expect(screen.getByText('Menemen')).not.toHaveAttribute('title')
  })

  it('marks a dish with a dotted underline when a hidden sub-ingredient is missing', async () => {
    checkMissingIngredients.mockResolvedValue({ missing: ['Avocado'] })
    render(<MealEditor meal={MEAL} menuMode checkFridge />)
    const dish = await screen.findByTitle('Some ingredients are not in your fridge')
    expect(dish).toHaveTextContent('Menemen')
    expect(dish.style.textDecorationStyle).toBe('dotted')
    fireEvent.click(screen.getByText('▶ Ingredients'))
    expect(screen.getByText('Avocado')).toHaveAttribute('title', 'Not in your fridge')
    expect(screen.getByText('Yumurta')).not.toHaveAttribute('title')
  })

  it('checks again after an edit and clears the mark once the item is removed', async () => {
    checkMissingIngredients.mockResolvedValueOnce({ missing: ['Olives'] }).mockResolvedValue({ missing: [] })
    const onMissingChange = vi.fn()
    render(<MealEditor meal={MEAL} menuMode checkFridge onMissingChange={onMissingChange} />)
    await waitFor(() => expect(onMissingChange).toHaveBeenLastCalledWith(['Olives']))
    fireEvent.click(screen.getAllByTitle('Delete')[1]) // dish row first, then Olives
    await waitFor(() => expect(onMissingChange).toHaveBeenLastCalledWith([]))
    const lastMeal = checkMissingIngredients.mock.calls.at(-1)[0]
    expect(lastMeal.menu.map(item => item.name)).toEqual(['Menemen'])
  })

  it('does not call the backend unless checkFridge is on', async () => {
    render(<MealEditor meal={MEAL} menuMode />)
    await new Promise(resolve => setTimeout(resolve, 400))
    expect(checkMissingIngredients).not.toHaveBeenCalled()
  })
})
