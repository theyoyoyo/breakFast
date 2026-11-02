/**
 * Tests for meal normalization of LLM output and for units that follow the AI language.
 */

import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import {
  normalizeMeal, formatIngredient, localizeUnit, unitWithSize, unitsFor, countUnit, getSmartUnit, resolveUnit, rememberUnit,
  menuKey,
} from './ingredients'
import { applyLanguage } from './language'

beforeEach(() => localStorage.clear())
afterEach(() => applyLanguage('en'))

describe('menuKey', () => {
  // The same food in another order, case or unit language gives the same key; methods and prep words don't count
  it('ignores order, case and the unit language', () => {
    const a = { menu: [
      { name: 'Menemen', ingredients: [{ name: 'Egg', amount: 2, unit: 'pcs' }, { name: 'Tomato', amount: 1, unit: 'pcs', prep: 'diced' }] },
      { name: 'Olives', amount: 10, unit: 'pcs', ingredients: [] },
    ] }
    const b = { menu_items: [
      { name: 'olives ', amount: '10', unit: 'adet', ingredients: [] },
      { name: 'MENEMEN', method: 'Fry', ingredients: [{ name: 'Tomato', amount: 1, unit: 'adet' }, { name: 'egg', amount: 2, unit: 'adet' }] },
    ] }
    expect(menuKey(a)).toBe(menuKey(b))
  })

  // Another amount, unit, item or dish ingredient is other food
  it('changes with the food', () => {
    const olives = { name: 'Olives', amount: 10, unit: 'pcs' }
    const toast = { name: 'Toast', ingredients: [{ name: 'Bread', amount: 2, unit: 'slice' }] }
    const key = menuKey({ menu: [olives, toast] })
    expect(menuKey({ menu: [{ ...olives, amount: 11 }, toast] })).not.toBe(key)
    expect(menuKey({ menu: [{ ...olives, unit: 'g' }, toast] })).not.toBe(key)
    expect(menuKey({ menu: [olives] })).not.toBe(key)
    expect(menuKey({ menu: [olives, { name: 'Toast', ingredients: [{ name: 'Bread', amount: 3, unit: 'slice' }] }] })).not.toBe(key)
  })

  // An old flat meal compares like a menu of simple items, and an item with no amount counts as one
  it('reads flat ingredients and missing amounts like the editor does', () => {
    expect(menuKey({ ingredients: [{ name: 'Egg', quantity: 2, unit: 'pcs' }] }))
      .toBe(menuKey({ menu: [{ name: 'Egg', amount: 2, unit: 'pcs', ingredients: [] }] }))
    expect(menuKey({ menu: [{ name: 'Ayran', ingredients: [] }] }))
      .toBe(menuKey({ menu: [{ name: 'Ayran', amount: 1, unit: 'pcs', ingredients: [] }] }))
  })
})

describe('normalizeMeal', () => {
  it('turns a dish with no ingredients and no amount into a simple item', () => {
    const meal = normalizeMeal({ menu_name: 'Breakfast', menu: [{ name: 'Ayran', ingredients: [] }] })
    expect(meal.menu[0]).toEqual({ name: 'Ayran', amount: 1, unit: 'pcs', ingredients: [] })
    expect(meal.ingredients).toEqual([{ name: 'Ayran', quantity: 1, unit: 'pcs' }])
  })

  it('gives items without a unit the Turkish count unit in Turkish mode', () => {
    applyLanguage('tr')
    const meal = normalizeMeal({ menu_name: 'Kahvaltı', menu: [{ name: 'Ayran', ingredients: [] }] })
    expect(meal.menu[0].unit).toBe('adet')
  })

  it('keeps real dishes and simple items as they are', () => {
    const menemen = { name: 'Menemen', ingredients: [{ name: 'Egg', amount: 2, unit: 'adet' }] }
    const cheese = { name: 'Cheese', amount: 50, unit: 'g', ingredients: [] }
    const meal = normalizeMeal({ menu_name: 'Breakfast', menu: [menemen, cheese] })
    expect(meal.menu).toEqual([menemen, cheese])
    expect(meal.meal_name).toBe('Breakfast')
    expect(meal.ingredients.map(i => i.name)).toEqual(['Egg', 'Cheese'])
  })

  it('leaves old flat-format meals without a menu', () => {
    const meal = normalizeMeal({ meal_name: 'Toast', ingredients: [{ name: 'Bread' }] })
    expect(meal.menu).toBeUndefined()
    expect(meal.ingredients).toEqual([{ name: 'Bread' }])
  })
})

describe('units', () => {
  it('has one English and one Turkish list that match 1-1, English by default', () => {
    expect(unitsFor('en')).toHaveLength(unitsFor('tr').length)
    expect(unitsFor()[0]).toBe('pcs')
    expect(countUnit('tr')).toBe('adet')
  })

  it('shows known units in the given language and unknown ones as written', () => {
    expect(localizeUnit('adet', 'en')).toBe('pcs')
    expect(localizeUnit('tbsp', 'tr')).toBe('yemek kaşığı')
    expect(localizeUnit('Çay bardağı', 'en')).toBe('tea glass')
    expect(localizeUnit('su bardağı', 'en')).toBe('glass')
    expect(localizeUnit('scoop', 'tr')).toBe('scoop')
    expect(localizeUnit('cup', 'tr')).toBe('cup')
  })

  it('treats other spellings of a listed unit (old "gr", plurals) as that unit', () => {
    expect(localizeUnit('gr', 'en')).toBe('g')
    expect(localizeUnit('Slices', 'tr')).toBe('dilim')
    expect(localizeUnit('pieces', 'en')).toBe('pcs')
  })

  it('adds the fixed size to spoons and glasses in either language, nothing to other units', () => {
    expect(unitWithSize('tbsp')).toBe('tbsp (15 ml)')
    expect(unitWithSize('su bardağı')).toBe('su bardağı (200 ml)')
    expect(unitWithSize('g')).toBe('g')
    expect(unitWithSize('scoop')).toBe('scoop')
  })

  it('formats an ingredient with its unit in the current language', () => {
    expect(formatIngredient({ name: 'Egg', quantity: 2, unit: 'adet' })).toBe('2 pcs Egg')
    applyLanguage('tr')
    expect(formatIngredient({ name: 'Egg', quantity: 2, unit: 'pcs' })).toBe('2 adet Egg')
  })

  it('guesses units from English and Turkish names, in the current language', () => {
    expect(getSmartUnit('Olive oil')).toBe('tbsp')
    expect(getSmartUnit('Garlic')).toBe('clove')
    expect(getSmartUnit('Parsley')).toBe('bunch')
    expect(getSmartUnit('Sarımsak')).toBe('clove')
    expect(getSmartUnit('Banana')).toBe('pcs')
    applyLanguage('tr')
    expect(getSmartUnit('Olive oil')).toBe('yemek kaşığı')
    expect(getSmartUnit('Muz')).toBe('adet')
  })

  it('shows a remembered unit in the current language', () => {
    rememberUnit('Yumurta', 'adet')
    expect(resolveUnit('Yumurta')).toBe('pcs')
    applyLanguage('tr')
    expect(resolveUnit('Yumurta')).toBe('adet')
  })
})
