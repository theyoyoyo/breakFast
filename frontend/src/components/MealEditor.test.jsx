/**
 * Tests for MealEditor's fridge check: missing ingredients are underlined, never removed,
 * and can be marked as obtained for the meal (yellow → green), a dish's all at once with a tap
 * on its name. Also the header (☆ filled when a favorite has the meal's name and food, a note
 * when another favorite has the name, prep time in min), the ✱ and ℹ️ line on a dish ingredient the
 * review put in for a missing one, and units that follow the AI language. Editing: typed amounts,
 * the ▲ / ▼ steppers and blur, new items and dishes, a dish's ingredients, the name and prep time.
 * The backend check is mocked — no real network calls are made.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, waitFor, fireEvent, within, act } from '@testing-library/react'
import MealEditor from './MealEditor'
import { checkMissingIngredients, getFavorites } from '../services/api'
import { applyLanguage } from '../utils/language'
import { OMELETTE_MENU, PLATE_MENU } from './meals.fixtures'

vi.mock('../services/api', () => ({ checkMissingIngredients: vi.fn(), getFavorites: vi.fn(() => Promise.resolve([])) }))

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

  // The fridge check's missing names get a yellow underline and reach the caller; a dish without missing items stays plain
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

  // Callers such as "Today I ate" wait for the first answer, so an empty list before it would enable Confirm too early
  it('reports nothing before the first check answers', async () => {
    checkMissingIngredients.mockResolvedValue({ missing: [] })
    const onMissingChange = vi.fn()
    render(<MealEditor meal={MEAL} menuMode checkFridge onMissingChange={onMissingChange} />)
    expect(onMissingChange).not.toHaveBeenCalled()
    await waitFor(() => expect(onMissingChange).toHaveBeenCalledWith([]))
  })

  // A tap toggles an item between missing and obtained, and the caller hears the new missing list each time
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

  // A dish with a missing ingredient is marked on its name, and the mark changes once that ingredient is obtained
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

  // Marks saved with a chat card come back when the editor opens, and Save keeps them
  it('starts with marks the meal already carries, and saves them', async () => {
    checkMissingIngredients.mockResolvedValue({ missing: ['Olives'] })
    const onSave = vi.fn()
    render(<MealEditor meal={{ ...MEAL, obtained: ['Olives'] }} menuMode checkFridge onSave={onSave} />)
    expect(await screen.findByTitle(OBTAINED)).toHaveTextContent('Olives')
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))
    expect(onSave).toHaveBeenCalledWith(expect.objectContaining({ obtained: ['Olives'] }))
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

  // Only the name's text marks: a tap on the space beside it opens the dish and changes no mark
  it('opens a dish with a tap beside its marked name', async () => {
    checkMissingIngredients.mockResolvedValue({ missing: ['Avocado', 'Olives'] })
    const onMissingChange = vi.fn()
    render(<MealEditor meal={MEAL} menuMode checkFridge onMissingChange={onMissingChange} />)
    const dish = await screen.findByTitle('Some ingredients are not in your fridge — tap the name once you have them')
    fireEvent.click(dish.parentElement) // the cell the name sits in, which fills the row
    expect(screen.getByText('Yumurta')).toBeInTheDocument()
    expect(dish).toHaveAttribute('title', 'Some ingredients are not in your fridge — tap the name once you have them')
    await waitFor(() => expect(onMissingChange).toHaveBeenLastCalledWith(['Avocado', 'Olives']))
    const olives = screen.getByText('Olives')
    fireEvent.click(olives.parentElement) // beside a simple item's name: no mark either
    expect(olives).toHaveAttribute('title', MISSING)
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

  // Favorites are templates: the underline shows what to buy, but nothing there can be marked as obtained
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

  // Removing the missing item runs the fridge check again on the edited menu, and the mark goes with it
  it('checks again after an edit and clears the mark once the item is removed', async () => {
    checkMissingIngredients.mockResolvedValueOnce({ missing: ['Olives'] }).mockResolvedValue({ missing: [] })
    const onMissingChange = vi.fn()
    render(<MealEditor meal={MEAL} menuMode checkFridge onMissingChange={onMissingChange} />)
    await waitFor(() => expect(onMissingChange).toHaveBeenLastCalledWith(['Olives']))
    fireEvent.click(screen.getAllByTitle('Delete')[1]) // the eggs: the dish's own delete comes first // dish row first, then Olives
    await waitFor(() => expect(onMissingChange).toHaveBeenLastCalledWith([]))
    expect(checkMissingIngredients).toHaveBeenLastCalledWith({ menu: [expect.objectContaining({ name: 'Menemen' })] })
  })

  // Editors that don't show readiness (meal history, plain views) make no fridge request
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
    await waitFor(() => expect(star).toBeEnabled()) // once the favorites are loaded
    fireEvent.click(star)
    await waitFor(() => expect(star).toHaveAttribute('aria-pressed', 'true'))
    expect(onFavorite).toHaveBeenCalledWith(expect.objectContaining({ menu_name: 'Test Breakfast' }))
    expect(star).toHaveAccessibleName('Remove from favorites')
    fireEvent.click(star)
    await waitFor(() => expect(star).toHaveAttribute('aria-pressed', 'false'))
    expect(onUnfavorite).toHaveBeenCalledWith(7)
  })

  // A meal saved earlier opens with a filled star: a favorite has its name (any case) and its food
  // (any order), and the star follows the name and the food as they're edited
  it('fills the star for a meal that is already a favorite', async () => {
    const reordered = [MEAL.menu[1], { ...MEAL.menu[0], ingredients: [...MEAL.menu[0].ingredients].reverse() }]
    getFavorites.mockResolvedValueOnce([
      { id: 3, meal_name: 'test breakfast', menu_items: reordered },
      { id: 4, meal_name: 'Pancakes', menu_items: MEAL.menu },
    ])
    const onUnfavorite = vi.fn(() => Promise.resolve())
    render(<MealEditor meal={MEAL} menuMode onFavorite={vi.fn()} onUnfavorite={onUnfavorite} />)
    const star = await screen.findByRole('button', { name: 'Remove from favorites' })
    expect(star).toHaveAttribute('aria-pressed', 'true')
    fireEvent.change(screen.getByDisplayValue('Test Breakfast'), { target: { value: 'Pancakes ' } })
    expect(star).toHaveAttribute('aria-pressed', 'true')
    fireEvent.change(screen.getByDisplayValue('Pancakes'), { target: { value: 'Waffles' } })
    expect(star).toHaveAttribute('aria-pressed', 'false')
    fireEvent.change(screen.getByDisplayValue('Waffles'), { target: { value: 'Test Breakfast' } })
    expect(star).toHaveAttribute('aria-pressed', 'true')
    fireEvent.click(screen.getByText('▲')) // one more olive: other food
    expect(star).toHaveAttribute('aria-pressed', 'false')
    fireEvent.click(screen.getByText('▼'))
    expect(star).toHaveAttribute('aria-pressed', 'true')
    fireEvent.click(star)
    await waitFor(() => expect(onUnfavorite).toHaveBeenCalledWith(3))
    await waitFor(() => expect(star).toHaveAttribute('aria-pressed', 'false'))
  })

  // Another favorite with this name and other food: the star stays empty, and a tap saves nothing
  // and shows a note until the meal gets a new name
  it('asks for a new name when another favorite has this one', async () => {
    getFavorites.mockResolvedValueOnce([{ id: 3, meal_name: 'Test Breakfast', menu_items: [MEAL.menu[1]] }])
    const onFavorite = vi.fn(() => Promise.resolve(8))
    render(<MealEditor meal={MEAL} menuMode onFavorite={onFavorite} onUnfavorite={vi.fn()} />)
    const star = screen.getByRole('button', { name: 'Add to favorites' })
    await waitFor(() => expect(star).toBeEnabled())
    fireEvent.click(star)
    expect(screen.getByText(/"Test Breakfast" is already in Favorites/)).toBeInTheDocument()
    expect(onFavorite).not.toHaveBeenCalled()
    fireEvent.change(screen.getByDisplayValue('Test Breakfast'), { target: { value: 'Test Breakfast 2' } })
    expect(screen.queryByText(/is already in Favorites/)).toBeNull()
    fireEvent.click(star)
    await waitFor(() => expect(star).toHaveAttribute('aria-pressed', 'true'))
    expect(onFavorite).toHaveBeenCalledWith(expect.objectContaining({ menu_name: 'Test Breakfast 2' }))
  })

  // The server's refusal (another device took the name meanwhile) shows the same note
  it('shows the note when the server refuses a taken name', async () => {
    const onFavorite = vi.fn(() => Promise.reject(Object.assign(new Error('API error 409'), { status: 409 })))
    render(<MealEditor meal={MEAL} menuMode onFavorite={onFavorite} onUnfavorite={vi.fn()} />)
    const star = screen.getByRole('button', { name: 'Add to favorites' })
    await waitFor(() => expect(star).toBeEnabled())
    fireEvent.click(star)
    expect(await screen.findByText(/"Test Breakfast" is already in Favorites/)).toBeInTheDocument()
    expect(star).toHaveAttribute('aria-pressed', 'false')
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

  // Prep words appear in the info panel only, so item names stay exactly the fridge names the check compares
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

  // A changed amount keeps each ingredient's prep words, and a meal without any shows no info button
  it('keeps prep words through edits, and has no info button when there are none', () => {
    const onChange = vi.fn()
    const { unmount } = render(<MealEditor meal={PREP_MEAL} menuMode onChange={onChange} />)
    fireEvent.click(screen.getByText('▶ Ingredients'))
    fireEvent.click(screen.getAllByText('▲')[0])
    expect(onChange).toHaveBeenLastCalledWith(expect.objectContaining({
      menu: [expect.objectContaining({ ingredients: [
        expect.objectContaining({ name: 'Oats', amount: 2, prep: 'rolled' }),
        expect.objectContaining({ name: 'Banana', prep: 'sliced' }),
      ] })],
    }))
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

  // A dish's method alone is enough to show the info panel
  it('shows a dish method behind the info button, also when no ingredient has prep words', () => {
    render(<MealEditor meal={METHOD_MEAL} menuMode />)
    expect(screen.queryByText('Hard-boil the eggs, peel, slice into the bread')).toBeNull()
    fireEvent.click(screen.getByTitle('Preparation details'))
    expect(screen.getByText('Egg sandwich', { selector: 'div' })).toBeInTheDocument()
    expect(screen.getByText('Hard-boil the eggs, peel, slice into the bread')).toBeInTheDocument()
  })

  // A simple item that is cut or cooked shows its method in the info panel, and an edit keeps it
  it('shows a simple item method behind the info button and keeps it through edits', () => {
    const onChange = vi.fn()
    const meal = { menu_name: 'Bowls', menu: [
      { name: 'Sweet potato', amount: 300, unit: 'g', method: 'Peel, cube and roast', ingredients: [] },
      { name: 'Olives', amount: 10, unit: 'pcs', ingredients: [] },
    ] }
    render(<MealEditor meal={meal} menuMode onChange={onChange} />)
    fireEvent.click(screen.getByTitle('Preparation details'))
    expect(screen.getByText('Sweet potato', { selector: 'div' })).toBeInTheDocument()
    expect(screen.getByText('Peel, cube and roast')).toBeInTheDocument()
    expect(screen.queryByText('Olives', { selector: 'div' })).toBeNull()
    fireEvent.click(screen.getAllByText('▲')[0])
    expect(onChange).toHaveBeenLastCalledWith(expect.objectContaining({
      menu: [expect.objectContaining({ name: 'Sweet potato', amount: 301, method: 'Peel, cube and roast' }), expect.anything()],
    }))
  })

  // Changing an ingredient's amount doesn't drop the dish's method, which the prep plan needs
  it('keeps a dish method through edits', () => {
    const onChange = vi.fn()
    render(<MealEditor meal={METHOD_MEAL} menuMode onChange={onChange} />)
    fireEvent.click(screen.getByText('▶ Ingredients'))
    fireEvent.click(screen.getAllByText('▲')[0])
    expect(onChange).toHaveBeenLastCalledWith(expect.objectContaining({
      menu: [expect.objectContaining({
        method: 'Hard-boil the eggs, peel, slice into the bread',
        ingredients: [expect.objectContaining({ name: 'Eggs', amount: 3 }), expect.objectContaining({ name: 'Bread' })],
      }), expect.anything()],
    }))
  })

  // Removing a dish ingredient drops the method written for it, from the info panel and the saved meal (#268)
  it('drops a dish method once an ingredient is removed', () => {
    const onSave = vi.fn()
    render(<MealEditor meal={METHOD_MEAL} menuMode onSave={onSave} />)
    fireEvent.click(screen.getByText('▶ Ingredients'))
    fireEvent.click(screen.getAllByTitle('Delete')[1]) // the eggs: the dish's own delete comes first
    // With the method gone the dish has nothing left to explain, so the info button goes too
    expect(screen.queryByTitle('Preparation details')).toBeNull()
    fireEvent.click(screen.getByText('Save'))
    const dish = onSave.mock.lastCall[0].menu[0]
    expect(dish.ingredients.map(sub => sub.name)).toEqual(['Bread'])
    expect(dish).not.toHaveProperty('method')
  })

  // Adding a dish ingredient drops the method too, since it wasn't written with that food (#268)
  it('drops a dish method once an ingredient is added', () => {
    const onSave = vi.fn()
    render(<MealEditor meal={METHOD_MEAL} menuMode onSave={onSave} />)
    fireEvent.click(screen.getByText('▶ Ingredients'))
    fireEvent.change(screen.getByPlaceholderText('Add ingredient…'), { target: { value: 'Butter' } })
    fireEvent.keyDown(screen.getByPlaceholderText('Add ingredient…'), { key: 'Enter' })
    fireEvent.click(screen.getByText('Save'))
    const dish = onSave.mock.lastCall[0].menu[0]
    expect(dish.ingredients.map(sub => sub.name)).toEqual(['Eggs', 'Bread', 'Butter'])
    expect(dish).not.toHaveProperty('method')
  })

  // A saved meal carries no editor bookkeeping, and an unchanged dish keeps its method (#268)
  it('saves an unchanged method and nothing of its own', () => {
    const onSave = vi.fn()
    render(<MealEditor meal={METHOD_MEAL} menuMode onSave={onSave} />)
    fireEvent.click(screen.getByText('Save'))
    const [dish, olives] = onSave.mock.lastCall[0].menu
    expect(dish.method).toBe('Hard-boil the eggs, peel, slice into the bread')
    expect(dish).not.toHaveProperty('_food')
    expect(olives).not.toHaveProperty('_food')
  })

  const PAIRED_MEAL = {
    menu_name: 'Green morning',
    menu: [
      { name: 'Omelette', ingredients: [{ name: 'Eggs', amount: 2, unit: 'pcs' }] },
      { name: 'Tahini dressing', serve_with: 'Omelette', ingredients: [{ name: 'Tahini', amount: 1, unit: 'tbsp' }] },
    ],
  }

  // An item served with another one names that item in the info panel, under the paired item only (#263)
  it('shows the item a paired item is served with behind the info button', () => {
    render(<MealEditor meal={PAIRED_MEAL} menuMode />)
    fireEvent.click(screen.getByTitle('Preparation details'))
    expect(screen.getByText('Tahini dressing', { selector: 'div' }).parentElement).toHaveTextContent(/Omelette/)
    expect(screen.queryByText('Omelette', { selector: 'div' })).toBeNull()
  })

  // An edit keeps the item a paired item is served with, like its method (#263)
  it('keeps the paired item through edits', () => {
    const onChange = vi.fn()
    render(<MealEditor meal={PAIRED_MEAL} menuMode onChange={onChange} />)
    fireEvent.click(screen.getAllByText('▶ Ingredients')[1])
    fireEvent.click(screen.getAllByText('▲')[0])
    expect(onChange).toHaveBeenLastCalledWith(expect.objectContaining({
      menu: [expect.anything(), expect.objectContaining({
        serve_with: 'Omelette', ingredients: [expect.objectContaining({ name: 'Tahini', amount: 2 })],
      })],
    }))
  })

  // Deleting an item clears the pairings that name it and keeps the paired items (#263)
  it('keeps a paired item and clears its pairing when its partner is deleted', () => {
    const onChange = vi.fn()
    render(<MealEditor meal={PAIRED_MEAL} menuMode onChange={onChange} />)
    fireEvent.click(screen.getAllByTitle('Delete')[0])
    const { menu } = onChange.mock.lastCall[0]
    expect(menu.map(item => item.name)).toEqual(['Tahini dressing'])
    expect(menu[0]).not.toHaveProperty('serve_with')
    expect(screen.queryByTitle('Preparation details')).toBeNull()
  })

  // A pairing that names no other item of the menu shows nothing, so the info button stays hidden (#263)
  it('shows no pairing that names no other menu item', () => {
    const meal = { menu_name: 'Plate', menu: [
      { name: 'Honey', amount: 1, unit: 'tsp', serve_with: 'Pancakes', ingredients: [] },
      { name: 'Olives', amount: 10, unit: 'pcs', serve_with: 'Olives', ingredients: [] },
    ] }
    render(<MealEditor meal={meal} menuMode />)
    expect(screen.queryByTitle('Preparation details')).toBeNull()
  })
})

describe('MealEditor replaced ingredients', () => {
  beforeEach(() => { vi.mocked(checkMissingIngredients).mockReset() })

  const SWAP_MEAL = {
    menu_name: 'Frittata',
    menu: [
      { name: 'Frittata', ingredients: [
        { name: 'Eggs', amount: 3, unit: 'pcs' },
        { name: 'Feta', amount: 50, unit: 'g', replaces: 'Salmon' },
      ] },
      { name: 'Olives', amount: 10, unit: 'pcs', ingredients: [] },
    ],
  }

  // The ✱ sits right after the name of the ingredient the review put in, and names the missing item it stands in for
  it('marks a replaced dish ingredient with a ✱ that names the missing item', () => {
    render(<MealEditor meal={SWAP_MEAL} menuMode />)
    expect(screen.queryByText('✱')).toBeNull() // the dish is closed
    fireEvent.click(screen.getByText('▶ Ingredients'))
    const marks = screen.getAllByRole('img', { name: 'Instead of Salmon' })
    expect(marks).toHaveLength(1)
    expect(marks[0]).toHaveTextContent('✱')
    expect(marks[0]).toHaveAttribute('title', 'Instead of Salmon')
    expect(marks[0].previousSibling).toHaveTextContent(/^Feta$/)
  })

  // The ℹ️ panel has one line per replaced ingredient under its dish, and the button shows when that's the only detail
  it('lists a replaced ingredient behind the info button, also when it is the only detail', () => {
    render(<MealEditor meal={SWAP_MEAL} menuMode />)
    fireEvent.click(screen.getByTitle('Preparation details'))
    const line = screen.getByText('Feta: instead of Salmon (not in your fridge)')
    expect(line.parentElement.firstChild).toHaveTextContent('Frittata')
    expect(screen.queryByText('Olives', { selector: 'div' })).toBeNull()
  })

  // A simple item never shows the mark or the line, even if it carries the field
  it('shows no mark or info line for a simple item', () => {
    const meal = { menu_name: 'Plate', menu: [{ name: 'Olives', amount: 10, unit: 'pcs', replaces: 'Capers', ingredients: [] }] }
    render(<MealEditor meal={meal} menuMode />)
    expect(screen.queryByText('✱')).toBeNull()
    expect(screen.queryByTitle('Preparation details')).toBeNull()
  })

  // The ✱ sits outside the missing mark: a tap on it changes no mark and keeps the dish open, a tap on the name still marks
  it('keeps the missing mark and its tap on the name, not on the ✱', async () => {
    checkMissingIngredients.mockResolvedValue({ missing: ['Feta'] })
    render(<MealEditor meal={SWAP_MEAL} menuMode checkFridge />)
    fireEvent.click(screen.getByText('▶ Ingredients'))
    const feta = await screen.findByTitle(MISSING)
    expect(feta).toHaveTextContent(/^Feta$/)
    fireEvent.click(screen.getByText('✱'))
    expect(feta).toHaveAttribute('title', MISSING)
    expect(screen.getByText('Eggs')).toBeInTheDocument()
    fireEvent.click(feta)
    expect(feta).toHaveAttribute('title', OBTAINED)
  })

  // Like prep words, the field rides along with its row through amount and unit edits, other rows' edits and Save
  it('keeps replaces through edits and Save', () => {
    const onChange = vi.fn()
    const onSave = vi.fn()
    render(<MealEditor meal={SWAP_MEAL} menuMode onChange={onChange} onSave={onSave} />)
    fireEvent.click(screen.getByText('▶ Ingredients'))
    fireEvent.click(screen.getAllByText('▲')[1]) // Eggs, Feta, then Olives
    fireEvent.change(screen.getAllByRole('combobox')[1], { target: { value: 'tbsp' } })
    fireEvent.click(screen.getAllByText('▲')[2])
    fireEvent.click(screen.getAllByTitle('Delete')[1]) // the eggs: the dish's own delete comes first // the dish's trash first, then Eggs
    const expected = [{ name: 'Feta', amount: 51, unit: 'tbsp', replaces: 'Salmon' }]
    expect(onChange).toHaveBeenLastCalledWith(expect.objectContaining({
      menu: [expect.objectContaining({ ingredients: expected }), expect.anything()],
    }))
    expect(screen.getByRole('img', { name: 'Instead of Salmon' })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))
    const dish = expect.objectContaining({ name: 'Frittata', ingredients: expected })
    expect(onSave).toHaveBeenCalledWith(expect.objectContaining({ menu: [dish, expect.anything()], menu_items: [dish, expect.anything()] }))
  })

  // The editor changes a row's name by deleting it and adding another, and the new row has no replaces (no ✱, no ℹ️ line)
  it('drops replaces when the ingredient gives way to another name', () => {
    const onChange = vi.fn()
    render(<MealEditor meal={SWAP_MEAL} menuMode onChange={onChange} />)
    fireEvent.click(screen.getByText('▶ Ingredients'))
    fireEvent.click(screen.getAllByTitle('Delete')[2]) // the dish's trash, Eggs, then Feta
    const add = screen.getByPlaceholderText('Add ingredient…')
    fireEvent.change(add, { target: { value: 'Halloumi' } })
    fireEvent.keyDown(add, { key: 'Enter' })
    expect(onChange).toHaveBeenLastCalledWith(expect.objectContaining({
      menu: [expect.objectContaining({ ingredients: [
        { name: 'Eggs', amount: 3, unit: 'pcs' },
        expect.objectContaining({ name: 'Halloumi' }),
      ] }), expect.anything()],
    }))
    expect(onChange).toHaveBeenLastCalledWith(expect.objectContaining({
      menu: [expect.objectContaining({ ingredients: [expect.anything(), expect.not.objectContaining({ replaces: expect.anything() })] }), expect.anything()],
    }))
    expect(screen.queryByText('✱')).toBeNull()
    expect(screen.queryByTitle('Preparation details')).toBeNull()
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

  // Stored Turkish units show in English by default, and a unit off the list keeps its own name
  it('shows known units and the dropdown in English by default', () => {
    render(<MealEditor meal={UNIT_MEAL} menuMode />)
    const [olives, powder] = screen.getAllByRole('combobox')
    expect(olives).toHaveValue('pcs')
    expect(within(olives).getAllByRole('option').map(o => o.value)).toContain('tbsp')
    expect(within(olives).queryByRole('option', { name: 'adet' })).toBeNull()
    expect(powder).toHaveValue('scoop')
  })

  // An open editor follows a language switch without reopening
  it('switches the dropdowns to Turkish when the language changes', () => {
    render(<MealEditor meal={UNIT_MEAL} menuMode />)
    act(() => { applyLanguage('tr') })
    const [olives] = screen.getAllByRole('combobox')
    expect(olives).toHaveValue('adet')
    expect(within(olives).getAllByRole('option').map(o => o.value)).toContain('yemek kaşığı')
  })

  // Sizes in ml help while picking, but the closed box keeps the short unit so rows stay narrow
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

  // Showing a unit in another language doesn't rewrite it: only the unit the user picks changes on save
  it('saves stored units as written and a picked unit as picked', () => {
    const onSave = vi.fn()
    render(<MealEditor meal={UNIT_MEAL} menuMode onSave={onSave} />)
    fireEvent.change(screen.getAllByRole('combobox')[1], { target: { value: 'tbsp' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))
    expect(onSave).toHaveBeenCalledWith(expect.objectContaining({
      menu: [expect.objectContaining({ unit: 'adet' }), expect.objectContaining({ unit: 'tbsp' })],
    }))
  })
})

describe('MealEditor editing', () => {
  beforeEach(() => {
    vi.mocked(checkMissingIngredients).mockReset()
    localStorage.clear() // no remembered units
  })

  // Press Save once, and check it sent one meal like this one
  function expectSaved(onSave, meal) {
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))
    expect(onSave).toHaveBeenCalledTimes(1)
    expect(onSave).toHaveBeenCalledWith(expect.objectContaining(meal))
  }

  // A typed amount is saved as a number, and the other items keep theirs
  it('saves a typed amount as a number', () => {
    const onSave = vi.fn()
    render(<MealEditor meal={PLATE_MENU} menuMode onSave={onSave} />)
    fireEvent.change(screen.getByDisplayValue('50'), { target: { value: '72.5' } })
    expect(onSave).not.toHaveBeenCalled()
    expectSaved(onSave, { menu: [
      expect.objectContaining({ name: 'Cheese', amount: 72.5, unit: 'g' }),
      expect.objectContaining({ name: 'Tomato', amount: 1, unit: 'pcs' }),
    ] })
  })

  // The amount box takes only numbers with up to two decimals, so a letter or a third decimal changes nothing
  it('ignores amounts that are not a number with up to two decimals', () => {
    render(<MealEditor meal={PLATE_MENU} menuMode />)
    const cheese = screen.getByDisplayValue('50')
    fireEvent.change(cheese, { target: { value: '5a' } })
    expect(cheese).toHaveValue('50')
    fireEvent.change(cheese, { target: { value: '1.255' } })
    expect(cheese).toHaveValue('50')
    fireEvent.change(cheese, { target: { value: '1.25' } })
    expect(cheese).toHaveValue('1.25')
  })

  // An emptied or zero amount becomes 1 when the box loses focus
  it('turns an empty or zero amount into 1 on blur', () => {
    render(<MealEditor meal={PLATE_MENU} menuMode />)
    const cheese = screen.getByDisplayValue('50')
    fireEvent.change(cheese, { target: { value: '' } })
    fireEvent.blur(cheese)
    expect(cheese).toHaveValue('1')
    fireEvent.change(cheese, { target: { value: '0' } })
    fireEvent.blur(cheese)
    expect(cheese).toHaveValue('1')
  })

  // ▲ adds one and ▼ takes one away, but never down to zero
  it('steps an amount up and down, never to zero', () => {
    const onChange = vi.fn()
    render(<MealEditor meal={{ ...PLATE_MENU, menu: [PLATE_MENU.menu[1]] }} menuMode onChange={onChange} />)
    const tomato = screen.getByDisplayValue('1')
    fireEvent.click(screen.getByText('▲'))
    fireEvent.click(screen.getByText('▲'))
    expect(tomato).toHaveValue('3')
    fireEvent.click(screen.getByText('▼'))
    expect(tomato).toHaveValue('2')
    fireEvent.click(screen.getByText('▼'))
    fireEvent.click(screen.getByText('▼'))
    expect(tomato).toHaveValue('1')
    expect(onChange).toHaveBeenLastCalledWith(expect.objectContaining({
      menu: [expect.objectContaining({ name: 'Tomato', amount: 1 })],
    }))
  })

  // A new simple item gets amount 1 and a unit from its name, added with Enter or ＋ Item; a name already there (any case) isn't added twice
  it('adds simple items once each', () => {
    const onSave = vi.fn()
    render(<MealEditor meal={PLATE_MENU} menuMode onSave={onSave} />)
    const add = screen.getByPlaceholderText('Item or dish name…')
    fireEvent.change(add, { target: { value: 'Honey' } })
    fireEvent.keyDown(add, { key: 'Enter' })
    expect(add).toHaveValue('')
    fireEvent.change(add, { target: { value: 'Walnuts' } })
    fireEvent.click(screen.getByRole('button', { name: '＋ Item' }))
    fireEvent.change(add, { target: { value: 'cheese' } })
    fireEvent.click(screen.getByRole('button', { name: '＋ Item' }))
    fireEvent.change(add, { target: { value: '   ' } })
    fireEvent.click(screen.getByRole('button', { name: '＋ Item' }))

    expectSaved(onSave, { menu: [
      expect.objectContaining({ name: 'Cheese' }),
      expect.objectContaining({ name: 'Tomato' }),
      expect.objectContaining({ name: 'Honey', amount: 1, ingredients: [] }),
      expect.objectContaining({ name: 'Walnuts', amount: 1, ingredients: [] }),
    ] })
  })

  // ＋ Dish adds a dish with no amount of its own; opened, it takes ingredients that can be stepped, typed and removed
  it('adds a dish and edits its ingredients', () => {
    const onSave = vi.fn()
    render(<MealEditor meal={PLATE_MENU} menuMode onSave={onSave} />)
    fireEvent.change(screen.getByPlaceholderText('Item or dish name…'), { target: { value: 'Pancakes' } })
    fireEvent.click(screen.getByRole('button', { name: '＋ Dish' }))
    fireEvent.click(screen.getByText('▶ Ingredients'))

    const addSub = screen.getByPlaceholderText('Add ingredient…')
    for (const name of ['Flour', 'Milk', 'Egg']) {
      fireEvent.change(addSub, { target: { value: name } })
      fireEvent.keyDown(addSub, { key: 'Enter' })
    }
    fireEvent.change(addSub, { target: { value: 'milk' } }) // already in the dish
    fireEvent.keyDown(addSub, { key: 'Enter' })
    expect(screen.getAllByText('Milk')).toHaveLength(1)
    fireEvent.click(screen.getAllByText('▲').at(-1)) // Egg: 2
    fireEvent.click(screen.getAllByTitle('Delete').at(-2)) // Milk
    const flour = screen.getAllByDisplayValue('1').at(-1)
    fireEvent.change(flour, { target: { value: '200' } })
    fireEvent.blur(flour)

    expectSaved(onSave, { menu: [
      expect.anything(),
      expect.anything(),
      { name: 'Pancakes', ingredients: [
        expect.objectContaining({ name: 'Flour', amount: 200 }),
        expect.objectContaining({ name: 'Egg', amount: 2 }),
      ] },
    ] })
  })

  // A dish ingredient's steppers, a typed amount and its blur work like a simple item's, and its prep words stay
  it('steps, types and blurs a dish ingredient amount', () => {
    const onChange = vi.fn()
    render(<MealEditor meal={OMELETTE_MENU} menuMode onChange={onChange} />)
    fireEvent.click(screen.getByText('Veggie omelette'))
    const egg = screen.getAllByDisplayValue('2')[0] // Egg, above Toast
    fireEvent.change(egg, { target: { value: '' } })
    fireEvent.blur(egg)
    expect(egg).toHaveValue('1')
    fireEvent.click(screen.getAllByText('▼')[0]) // Egg stays at 1
    expect(egg).toHaveValue('1')
    const pepper = screen.getByDisplayValue('0.5')
    fireEvent.change(pepper, { target: { value: '0.75' } })
    fireEvent.blur(pepper)
    expect(onChange).toHaveBeenLastCalledWith(expect.objectContaining({
      menu: expect.arrayContaining([expect.objectContaining({
        name: 'Veggie omelette',
        ingredients: [
          expect.objectContaining({ name: 'Egg', amount: 1, prep: 'whisked' }),
          expect.objectContaining({ name: 'Bell pepper', amount: 0.75, prep: 'diced' }),
          expect.objectContaining({ name: 'Butter', amount: 1 }),
        ],
      })]),
    }))
  })

  // The name and prep time are saved as edited, and an emptied name goes back to the meal's own on blur
  it('saves an edited name and prep time, and restores an emptied name', () => {
    const onSave = vi.fn()
    render(<MealEditor meal={OMELETTE_MENU} menuMode onSave={onSave} />)
    const name = screen.getByDisplayValue('Sunday Omelette')
    fireEvent.change(name, { target: { value: '' } })
    fireEvent.blur(name)
    expect(name).toHaveValue('Sunday Omelette')
    fireEvent.change(name, { target: { value: 'Lazy Omelette' } })
    const prep = screen.getByDisplayValue('15')
    fireEvent.change(prep, { target: { value: 'abc' } }) // not a number: ignored
    expect(prep).toHaveValue('15')
    fireEvent.change(prep, { target: { value: '20' } })
    expectSaved(onSave, { menu_name: 'Lazy Omelette', meal_name: 'Lazy Omelette', prep_time_min: 20 })
  })

  // Close leaves without saving the edits
  it('closes without saving', () => {
    const onSave = vi.fn()
    const onClose = vi.fn()
    render(<MealEditor meal={PLATE_MENU} menuMode onSave={onSave} onClose={onClose} />)
    fireEvent.change(screen.getByDisplayValue('50'), { target: { value: '60' } })
    fireEvent.click(screen.getByRole('button', { name: 'Close' }))
    expect(onClose).toHaveBeenCalledTimes(1)
    expect(onSave).not.toHaveBeenCalled()
  })
})

describe('MealEditor number boxes', () => {
  beforeEach(() => { vi.mocked(checkMissingIngredients).mockReset() })

  // The prep time box takes digits only: a typed letter is refused and the number stays as it was
  it('refuses letters in the prep time', () => {
    render(<MealEditor meal={{ ...MEAL, prep_time_min: 15 }} menuMode />)
    const prep = screen.getByLabelText('Prep time in minutes')
    fireEvent.change(prep, { target: { value: '2x' } })
    expect(prep).toHaveValue('15')
    fireEvent.change(prep, { target: { value: '' } })
    expect(prep).toHaveValue('')
    fireEvent.change(prep, { target: { value: '20' } })
    expect(prep).toHaveValue('20')
  })

  // A dish ingredient's typed amount reaches the live meal as a number before the box loses focus
  it('reports a typed dish ingredient amount as a number', () => {
    const onChange = vi.fn()
    render(<MealEditor meal={MEAL} menuMode onChange={onChange} />)
    fireEvent.click(screen.getByText('Menemen'))
    fireEvent.change(screen.getByLabelText('Amount of Yumurta'), { target: { value: '200' } })
    const eggs = () => onChange.mock.lastCall[0].menu[0].ingredients[0]
    expect(eggs()).toMatchObject({ name: 'Yumurta', amount: 200 })
    fireEvent.change(screen.getByLabelText('Amount of Yumurta'), { target: { value: '' } })
    expect(eggs()).toMatchObject({ name: 'Yumurta', amount: 1 })
  })
})
