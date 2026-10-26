/**
 * Shared ingredient utilities used across meal-related components.
 */

/**
 * Format a single ingredient for display.
 * Handles both structured {name, quantity, unit} and plain string forms.
 */
export function formatIngredient(item) {
  if (typeof item === 'object' && item !== null && item.name) {
    const qty = item.quantity != null ? item.quantity : ''
    const unit = item.unit || ''
    return `${qty} ${unit} ${item.name}`.trim()
  }
  return String(item)
}

/**
 * Normalize an ingredient to structured form {name, quantity, unit}.
 * Ensures every ingredient has a consistent shape for editing.
 */
export function normalizeItem(item) {
  if (typeof item === 'object' && item !== null && item.name) {
    return { name: item.name, quantity: item.quantity ?? 1, unit: item.unit || 'adet' }
  }
  return { name: String(item), quantity: 1, unit: 'adet' }
}

// ── Unit utilities ─────────────────────────────────────────────────────────

export const UNITS = [
  'adet', 'g', 'kg', 'ml', 'L',
  'yemek kaşığı', 'çay kaşığı', 'tatlı kaşığı',
  'su bardağı', 'çay bardağı',
  'dilim', 'demet', 'tutam', 'avuç', 'dal', 'diş', 'paket',
]

/** Infer a sensible default unit from an ingredient name. */
export function getSmartUnit(name) {
  const n = name.toLowerCase()
  if (/yağ/.test(n))                                       return 'yemek kaşığı'
  if (/^su$|^su /.test(n))                                 return 'ml'
  if (/peynir|lor|labne/.test(n))                          return 'g'
  if (/et|tavuk|hindi|kıyma|sosis|sucuk|pastırma|jambon/.test(n)) return 'g'
  if (/ekmek|tost|pide|simit|bagel/.test(n))               return 'dilim'
  if (/maydanoz|dereotu|nane|kekik|roka|fesleğen/.test(n)) return 'demet'
  if (/sarımsak/.test(n))                                  return 'diş'
  if (/tarçın|karabiber|tuz|pul biber|kimyon/.test(n))     return 'çay kaşığı'
  if (/limon|portakal|mandalina|elma|armut|muz|domates|biber|soğan|salatalık|havuç|patates|yumurta/.test(n)) return 'adet'
  return 'adet'
}

const UNIT_MEM_KEY = 'breakFast_unit_mem'

/** Recall the user's last-used unit for an ingredient name (localStorage). */
export function recallUnit(name) {
  try {
    const mem = JSON.parse(localStorage.getItem(UNIT_MEM_KEY) || '{}')
    return mem[name.toLowerCase()] || null
  } catch { return null }
}

/** Save the user's chosen unit for an ingredient name (localStorage). */
export function rememberUnit(name, unit) {
  try {
    const mem = JSON.parse(localStorage.getItem(UNIT_MEM_KEY) || '{}')
    mem[name.toLowerCase()] = unit
    localStorage.setItem(UNIT_MEM_KEY, JSON.stringify(mem))
  } catch { /* ignore */ }
}

/** Best unit for a new ingredient: memory → smart default → 'adet'. */
export function resolveUnit(name) {
  return recallUnit(name) || getSmartUnit(name)
}

// Normalize an LLM meal to always have meal_name, a clean menu and a flat ingredients list.
// Handles both the old flat format and the menu format. A menu item with neither
// ingredients nor an amount (e.g. "Ayran" with an empty list) becomes a simple item ×1,
// so it never opens as an empty dish.
export function normalizeMeal(meal) {
  if (!meal) return meal
  const name = meal.meal_name || meal.menu_name || 'Meal'
  const menu = meal.menu?.map(item =>
    !item.ingredients?.length && item.amount == null
      ? { ...item, amount: 1, unit: item.unit || 'adet', ingredients: [] }
      : item
  )
  // Derive flat ingredients from menu if not already present
  const ingredients = meal.ingredients && meal.ingredients.length > 0
    ? meal.ingredients
    : (menu || []).flatMap(item =>
        item.ingredients && item.ingredients.length > 0
          ? item.ingredients.map(ing => ({ name: ing.name, quantity: ing.amount ?? 1, unit: ing.unit || 'adet' }))
          : [{ name: item.name, quantity: item.amount ?? 1, unit: item.unit || 'adet' }]
      )
  return menu ? { ...meal, meal_name: name, menu, ingredients } : { ...meal, meal_name: name, ingredients }
}
