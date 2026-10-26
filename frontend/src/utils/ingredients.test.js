/**
 * Tests for meal normalization of LLM output.
 */

import { describe, it, expect } from 'vitest'
import { normalizeMeal } from './ingredients'

describe('normalizeMeal', () => {
  it('turns a dish with no ingredients and no amount into a simple item', () => {
    const meal = normalizeMeal({ menu_name: 'Breakfast', menu: [{ name: 'Ayran', ingredients: [] }] })
    expect(meal.menu[0]).toEqual({ name: 'Ayran', amount: 1, unit: 'adet', ingredients: [] })
    expect(meal.ingredients).toEqual([{ name: 'Ayran', quantity: 1, unit: 'adet' }])
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
