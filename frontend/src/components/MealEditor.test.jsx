/**
 * Tests for MealEditor's fridge check: missing ingredients are underlined, never removed,
 * and can be marked as obtained for the meal (yellow → green), a dish's all at once with a tap
 * on its name. Also the header (☆ favorites toggle, prep time in min) and units that follow
 * the AI language.
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
    const dish = await screen.findByTitle('Some ingredients are not in your fridge — tap the name once you have them')
    expect(dish).toHaveTextContent('Menemen')
    expect(dish.style.textDecorationStyle).toBe('dotted')
    fireEvent.click(screen.getByText('▶ Ingredients'))
    expect(screen.getByText('Yumurta')).not.toHaveAttribute('title')
    fireEvent.click(screen.getByText('Avocado'))
    expect(screen.getByText('Menemen')).toHaveAttribute('title', 'Missing ingredients are marked as obtained — tap to undo')
  })

  it('starts with marks the meal already carries, and saves them', async () => {
    checkMissingIngredients.mockResolvedValue({ missing: ['Olives'] })
    const onSave = vi.fn()
    render(<MealEditor meal={{ ...MEAL, obtained: ['Olives'] }} menuMode checkFridge onSave={onSave} />)
    expect(await screen.findByTitle(OBTAINED)).toHaveTextContent('Olives')
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))
    expect(onSave.mock.calls[0][0].obtained).toEqual(['Olives'])
  })

  // A tap on a dish's name marks all of its missing items (name included) and a second tap unmarks
  // them, without opening the dish
  it('marks all of a dish\'s missing items with a tap on its name', async () => {
    checkMissingIngredients.mockResolvedValue({ missing: ['Menemen', 'Avocado', 'Olives'] })
    const onMissingChange = vi.fn()
    render(<MealEditor meal={MEAL} menuMode checkFridge onMissingChange={onMissingChange} />)
    await waitFor(() => expect(onMissingChange).toHaveBeenLastCalledWith(['Menemen', 'Avocado', 'Olives']))
    fireEvent.click(screen.getByText('Menemen'))
    await waitFor(() => expect(onMissingChange).toHaveBeenLastCalledWith(['Olives']))
    expect(screen.getByText('Menemen')).toHaveAttribute('title', OBTAINED)
    expect(screen.queryByText('Yumurta')).toBeNull()
    fireEvent.click(screen.getByText('Menemen'))
    await waitFor(() => expect(onMissingChange).toHaveBeenLastCalledWith(['Menemen', 'Avocado', 'Olives']))
  })

  // In a template (favorites) a dish name only shows the mark; a tap opens the dish as usual
  it('opens a template dish on a name tap instead of marking it', async () => {
    checkMissingIngredients.mockResolvedValue({ missing: ['Avocado'] })
    render(<MealEditor meal={MEAL} menuMode checkFridge canMarkObtained={false} />)
    const dish = await screen.findByTitle('Some ingredients are not in your fridge')
    expect(dish).not.toHaveAttribute('role')
    fireEvent.click(dish)
    expect(screen.getByText('Yumurta')).toBeInTheDocument()
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

describe('MealEditor dish rows', () => {
  beforeEach(() => { vi.mocked(checkMissingIngredients).mockReset() })

  const TWO_DISHES = {
    menu_name: 'Test Breakfast',
    menu: [
      MEAL.menu[0],
      { name: 'Porridge', ingredients: [{ name: 'Oats', amount: 1, unit: 'glass' }] },
    ],
  }

  // The whole row is the target on a phone: its name and the space around it both toggle
  it('opens a dish with a tap on its name and closes it with a tap on the row', () => {
    render(<MealEditor meal={MEAL} menuMode />)
    expect(screen.queryByText('Yumurta')).toBeNull()
    fireEvent.click(screen.getByText('Menemen'))
    expect(screen.getByText('Yumurta')).toBeInTheDocument()
    fireEvent.click(screen.getByText('🍳').parentElement)
    expect(screen.queryByText('Yumurta')).toBeNull()
  })

  // The button sits inside the row, so a tap that reached the row too would close the dish again
  it('toggles the ingredients exactly once from the Ingredients button', () => {
    render(<MealEditor meal={MEAL} menuMode />)
    fireEvent.click(screen.getByText('▶ Ingredients'))
    expect(screen.getByText('Yumurta')).toBeInTheDocument()
    fireEvent.click(screen.getByText('▲ Ingredients'))
    expect(screen.queryByText('Yumurta')).toBeNull()
  })

  // A delete that reached the row would open the dish that moves up into its place
  it('deletes a dish with its trash button without opening the next one', () => {
    render(<MealEditor meal={TWO_DISHES} menuMode />)
    fireEvent.click(screen.getAllByTitle('Delete')[0])
    expect(screen.queryByText('Menemen')).toBeNull()
    expect(screen.getByText('Porridge')).toBeInTheDocument()
    expect(screen.queryByText('Oats')).toBeNull()
  })

  // On a phone a focused box brings up the keyboard over the editor, so opening a dish focuses nothing
  it('opens a dish without focusing its add box', () => {
    render(<MealEditor meal={MEAL} menuMode />)
    fireEvent.click(screen.getByText('Menemen'))
    expect(screen.getByPlaceholderText('Add ingredient…')).not.toHaveFocus()
  })

  // A missing dish name is its own button: the tap marks it as obtained and leaves the dish closed
  it('marks a missing dish name as obtained without opening the dish', async () => {
    checkMissingIngredients.mockResolvedValue({ missing: ['Menemen'] })
    render(<MealEditor meal={MEAL} menuMode checkFridge />)
    const name = await screen.findByTitle(MISSING)
    expect(name).toHaveTextContent('Menemen')
    fireEvent.click(name)
    expect(name).toHaveAttribute('title', OBTAINED)
    expect(screen.queryByText('Yumurta')).toBeNull()
  })
})

describe('MealEditor header', () => {
  beforeEach(() => { vi.mocked(checkMissingIngredients).mockReset() })

  // The ☆ left of the name adds the current meal; once added it's a filled star, and a second tap removes it
  it('adds and removes a favorite with the star', async () => {
    const onFavorite = vi.fn(() => Promise.resolve(7))
    const onUnfavorite = vi.fn(() => Promise.resolve())
    render(<MealEditor meal={MEAL} menuMode onFavorite={onFavorite} onUnfavorite={onUnfavorite} />)
    const star = screen.getByRole('button', { name: 'Add to favorites' })
    expect(star.nextSibling).toHaveValue('Test Breakfast') // just left of the name
    fireEvent.click(star)
    await waitFor(() => expect(star).toHaveAttribute('aria-pressed', 'true'))
    expect(onFavorite.mock.calls[0][0].menu_name).toBe('Test Breakfast')
    expect(star).toHaveAccessibleName('Remove from favorites')
    fireEvent.click(star)
    await waitFor(() => expect(star).toHaveAttribute('aria-pressed', 'false'))
    expect(onUnfavorite).toHaveBeenCalledWith(7)
  })

  // Without a favorites action there's no star; the prep time reads "min", with no clock and no id
  it('shows the prep time in min, with no star, clock or id', () => {
    render(<MealEditor meal={{ ...MEAL, id: 42, prep_time_min: 15 }} menuMode />)
    expect(screen.queryByRole('button', { name: 'Add to favorites' })).toBeNull()
    expect(screen.getByDisplayValue('15').nextSibling).toHaveTextContent('min')
    expect(screen.queryByText('⏱')).toBeNull()
    expect(screen.queryByText('#42')).toBeNull()
  })
})

describe('MealEditor prep words', () => {
  beforeEach(() => { vi.mocked(checkMissingIngredients).mockReset() })

  const PREP_MEAL = {
    menu_name: 'Porridge',
    menu: [{ name: 'Porridge', ingredients: [
      { name: 'Oats', amount: 1, unit: 'glass', prep: 'rolled' },
      { name: 'Banana', amount: 1, unit: 'pcs', prep: 'sliced' },
    ] }],
  }

  it('shows the prep words per dish behind the info button, not on the item names', async () => {
    checkMissingIngredients.mockResolvedValue({ missing: ['Banana'] })
    render(<MealEditor meal={PREP_MEAL} menuMode checkFridge />)
    const info = screen.getByTitle('Preparation details')
    expect(screen.queryByText('Oats: rolled')).toBeNull()
    fireEvent.click(info)
    expect(info).toHaveAttribute('aria-expanded', 'true')
    expect(screen.getByText('Oats: rolled')).toBeInTheDocument()
    expect(screen.getByText('Banana: sliced')).toBeInTheDocument()
    fireEvent.click(screen.getByText('▶ Ingredients'))
    expect(screen.getByText('Oats')).not.toHaveAttribute('title')
    await waitFor(() => expect(screen.getByText('Banana')).toHaveAttribute('title', MISSING))
  })

  it('keeps prep words through edits, and has no info button when there are none', () => {
    const onChange = vi.fn()
    const { unmount } = render(<MealEditor meal={PREP_MEAL} menuMode onChange={onChange} />)
    fireEvent.click(screen.getByText('▶ Ingredients'))
    fireEvent.click(screen.getAllByText('▲')[0])
    const oats = onChange.mock.lastCall[0].menu[0].ingredients[0]
    expect(oats).toMatchObject({ name: 'Oats', amount: 2, prep: 'rolled' })
    unmount()
    render(<MealEditor meal={MEAL} menuMode />)
    expect(screen.queryByTitle('Preparation details')).toBeNull()
  })

  const METHOD_MEAL = {
    menu_name: 'Egg sandwich',
    menu: [
      { name: 'Egg sandwich', method: 'Hard-boil the eggs, peel, slice into the bread', ingredients: [
        { name: 'Eggs', amount: 2, unit: 'pcs' },
        { name: 'Bread', amount: 2, unit: 'slice' },
      ] },
      { name: 'Olives', amount: 10, unit: 'pcs', ingredients: [] },
    ],
  }

  it('shows a dish method behind the info button, also when no ingredient has prep words', () => {
    render(<MealEditor meal={METHOD_MEAL} menuMode />)
    expect(screen.queryByText('Hard-boil the eggs, peel, slice into the bread')).toBeNull()
    fireEvent.click(screen.getByTitle('Preparation details'))
    expect(screen.getByText('Egg sandwich', { selector: 'div' })).toBeInTheDocument()
    expect(screen.getByText('Hard-boil the eggs, peel, slice into the bread')).toBeInTheDocument()
  })

  it('keeps a dish method through edits', () => {
    const onChange = vi.fn()
    render(<MealEditor meal={METHOD_MEAL} menuMode onChange={onChange} />)
    fireEvent.click(screen.getByText('▶ Ingredients'))
    fireEvent.click(screen.getAllByText('▲')[0])
    const dish = onChange.mock.lastCall[0].menu[0]
    expect(dish.method).toBe('Hard-boil the eggs, peel, slice into the bread')
    expect(dish.ingredients[0]).toMatchObject({ name: 'Eggs', amount: 3 })
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

  it('shows spoon and glass sizes in the open list only, the box keeps the plain unit', () => {
    const meal = { menu_name: 'Test', menu: [{ name: 'Honey', amount: 1, unit: 'yemek kaşığı', ingredients: [] }] }
    render(<MealEditor meal={meal} menuMode />)
    const picker = screen.getByRole('combobox')
    expect(picker).toHaveValue('tbsp')
    expect(within(picker).getByRole('option', { name: 'tbsp (15 ml)' })).toHaveValue('tbsp')
    expect(within(picker).getByRole('option', { name: 'g' })).toBeInTheDocument()
    expect(screen.getByText('tbsp')).toBeInTheDocument()
  })

  // Two-word units wrap, so the column is only as wide as the longest single word ("handful", "bardağı")
  it('keeps the unit column as wide as the longest word of any unit, in both languages', () => {
    render(<MealEditor meal={UNIT_MEAL} menuMode />)
    const widths = () => screen.getAllByRole('combobox').map(select => select.parentElement.style.width)
    expect(widths()).toEqual(['9ch', '9ch'])
    act(() => { applyLanguage('tr') })
    expect(widths()).toEqual(['9ch', '9ch'])
  })

  it('saves stored units as written and a picked unit as picked', () => {
    const onSave = vi.fn()
    render(<MealEditor meal={UNIT_MEAL} menuMode onSave={onSave} />)
    fireEvent.change(screen.getAllByRole('combobox')[1], { target: { value: 'tbsp' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))
    expect(onSave.mock.calls[0][0].menu.map(item => item.unit)).toEqual(['adet', 'tbsp'])
  })
})
