/**
 * Tests for meal normalization of LLM output and for units that follow the AI language.
 */

import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import {
  normalizeMeal, formatIngredient, localizeUnit, unitsFor, countUnit, getSmartUnit, resolveUnit, rememberUnit,
} from './ingredients'
import { applyLanguage } from './language'

beforeEach(() => localStorage.clear())
afterEach(() => applyLanguage('en'))

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
