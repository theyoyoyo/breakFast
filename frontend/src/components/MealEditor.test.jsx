/**
 * Tests for MealEditor's fridge check: missing ingredients are underlined, never removed,
 * and can be marked as obtained for the meal (yellow → green). Also units that follow the AI language.
 * The backend check is mocked — no real network calls are made.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, waitFor, fireEvent, within, act } from '@testing-library/react'
import MealEditor from './MealEditor'
import { checkMissingIngredients } from '../services/api'
import { applyLanguage } from '../utils/language'

vi.mock('../services/api', () => ({ checkMissingIngredients: vi.fn() }))

const MISSING = 'Not in your fridge — tap once you have it'
const OBTAINED = 'Marked as obtained — tap to undo'

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
  beforeEach(() => { vi.mocked(checkMissingIngredients).mockReset() })

  it('underlines simple items that are not in the fridge and reports them', async () => {
    checkMissingIngredients.mockResolvedValue({ missing: ['Olives'] })
    const onMissingChange = vi.fn()
    render(<MealEditor meal={MEAL} menuMode checkFridge onMissingChange={onMissingChange} />)
    await waitFor(() => expect(onMissingChange).toHaveBeenCalledWith(['Olives']))
    const olives = screen.getByText('Olives')
    expect(olives).toHaveAttribute('title', MISSING)
    expect(olives.style.textDecorationLine).toBe('underline')
    expect(screen.getByText('Menemen')).not.toHaveAttribute('title')
  })

  it('reports nothing before the first check answers', async () => {
    checkMissingIngredients.mockResolvedValue({ missing: [] })
    const onMissingChange = vi.fn()
    render(<MealEditor meal={MEAL} menuMode checkFridge onMissingChange={onMissingChange} />)
    expect(onMissingChange).not.toHaveBeenCalled()
    await waitFor(() => expect(onMissingChange).toHaveBeenCalledWith([]))
  })

  it('marks a missing item as obtained on tap, and back on a second tap', async () => {
    checkMissingIngredients.mockResolvedValue({ missing: ['Olives'] })
    const onMissingChange = vi.fn()
    render(<MealEditor meal={MEAL} menuMode checkFridge onMissingChange={onMissingChange} />)
    const olives = await screen.findByTitle(MISSING)
    fireEvent.click(olives)
    expect(olives).toHaveAttribute('title', OBTAINED)
    await waitFor(() => expect(onMissingChange).toHaveBeenLastCalledWith([]))
    fireEvent.click(olives)
    expect(olives).toHaveAttribute('title', MISSING)
    await waitFor(() => expect(onMissingChange).toHaveBeenLastCalledWith(['Olives']))
  })

  it('gives a dish a dotted mark that turns green once its missing sub-ingredients are obtained', async () => {
    checkMissingIngredients.mockResolvedValue({ missing: ['Avocado'] })
    render(<MealEditor meal={MEAL} menuMode checkFridge />)
    const dish = await screen.findByTitle('Some ingredients are not in your fridge')
    expect(dish).toHaveTextContent('Menemen')
    expect(dish.style.textDecorationStyle).toBe('dotted')
    fireEvent.click(screen.getByText('▶ Ingredients'))
    expect(screen.getByText('Yumurta')).not.toHaveAttribute('title')
    fireEvent.click(screen.getByText('Avocado'))
    expect(screen.getByText('Menemen')).toHaveAttribute('title', 'Missing ingredients are marked as obtained')
  })

  it('starts with marks the meal already carries, and saves them', async () => {
    checkMissingIngredients.mockResolvedValue({ missing: ['Olives'] })
    const onSave = vi.fn()
    render(<MealEditor meal={{ ...MEAL, obtained: ['Olives'] }} menuMode checkFridge onSave={onSave} />)
    expect(await screen.findByTitle(OBTAINED)).toHaveTextContent('Olives')
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))
    expect(onSave.mock.calls[0][0].obtained).toEqual(['Olives'])
  })

  it('lets extra actions mark every missing item as obtained at once', async () => {
    checkMissingIngredients.mockResolvedValue({ missing: ['Olives', 'Avocado'] })
    const onMissingChange = vi.fn()
    render(
      <MealEditor
        meal={MEAL} menuMode checkFridge onMissingChange={onMissingChange}
        extraActions={(_build, { markAllObtained }) => <button onClick={markAllObtained}>Mark all</button>}
      />,
    )
    await waitFor(() => expect(onMissingChange).toHaveBeenLastCalledWith(['Olives', 'Avocado']))
    fireEvent.click(screen.getByRole('button', { name: 'Mark all' }))
    await waitFor(() => expect(onMissingChange).toHaveBeenLastCalledWith([]))
    expect(screen.getByText('Olives')).toHaveAttribute('title', OBTAINED)
  })

  it('only underlines missing items in templates (favorites), with no tap to mark', async () => {
    checkMissingIngredients.mockResolvedValue({ missing: ['Olives'] })
    const onMissingChange = vi.fn()
    render(
      <MealEditor
        meal={{ ...MEAL, obtained: ['Olives'] }} menuMode checkFridge canMarkObtained={false}
        onMissingChange={onMissingChange}
      />,
    )
    const olives = await screen.findByTitle('Not in your fridge')
    expect(olives).toHaveTextContent('Olives')
    expect(olives.style.textDecorationLine).toBe('underline')
    expect(olives).not.toHaveAttribute('role')
    fireEvent.click(olives)
    expect(olives).toHaveAttribute('title', 'Not in your fridge')
    expect(onMissingChange).toHaveBeenLastCalledWith(['Olives'])
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

describe('MealEditor units', () => {
  afterEach(() => applyLanguage('en'))

  const UNIT_MEAL = {
    menu_name: 'Test Breakfast',
    menu: [
      { name: 'Olives', amount: 10, unit: 'adet', ingredients: [] },
      { name: 'Protein powder', amount: 1, unit: 'scoop', ingredients: [] },
    ],
  }

  it('shows known units and the dropdown in English by default', () => {
    render(<MealEditor meal={UNIT_MEAL} menuMode />)
    const [olives, powder] = screen.getAllByRole('combobox')
    expect(olives).toHaveValue('pcs')
    expect(within(olives).getAllByRole('option').map(o => o.value)).toContain('tbsp')
    expect(within(olives).queryByRole('option', { name: 'adet' })).toBeNull()
    expect(powder).toHaveValue('scoop')
  })

  it('switches the dropdowns to Turkish when the language changes', () => {
    render(<MealEditor meal={UNIT_MEAL} menuMode />)
    act(() => { applyLanguage('tr') })
    const [olives] = screen.getAllByRole('combobox')
    expect(olives).toHaveValue('adet')
    expect(within(olives).getAllByRole('option').map(o => o.value)).toContain('yemek kaşığı')
  })

  it('saves stored units as written and a picked unit as picked', () => {
    const onSave = vi.fn()
    render(<MealEditor meal={UNIT_MEAL} menuMode onSave={onSave} />)
    fireEvent.change(screen.getAllByRole('combobox')[1], { target: { value: 'tbsp' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))
    expect(onSave.mock.calls[0][0].menu.map(item => item.unit)).toEqual(['adet', 'tbsp'])
  })
})
