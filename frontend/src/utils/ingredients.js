/**
 * Shared ingredient utilities used across meal-related components.
 */

import { currentLanguage } from './language'

/**
 * Format a single ingredient for display, its unit in the given language.
 * Handles both structured {name, quantity, unit} and plain string forms.
 */
export function formatIngredient(item, language = currentLanguage()) {
  if (typeof item === 'object' && item !== null && item.name) {
    const qty = item.quantity != null ? item.quantity : ''
    const unit = localizeUnit(item.unit || '', language)
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
    return { name: item.name, quantity: item.quantity ?? 1, unit: item.unit || countUnit() }
  }
  return { name: String(item), quantity: 1, unit: countUnit() }
}

// ── Unit utilities ─────────────────────────────────────────────────────────

// Mirrors backend/models/units.py: each row pairs an English unit with its Turkish match (1-1).
// Units follow the AI language; stored meals keep theirs and are shown in the current language.
export const UNIT_PAIRS = [
  ['pcs', 'adet'],
  ['g', 'g'],
  ['kg', 'kg'],
  ['ml', 'ml'],
  ['l', 'L'],
  ['tsp', 'çay kaşığı'],
  ['dsp', 'tatlı kaşığı'],
  ['tbsp', 'yemek kaşığı'],
  ['tea glass', 'çay bardağı'],
  ['glass', 'su bardağı'],
  ['slice', 'dilim'],
  ['bunch', 'demet'],
  ['pinch', 'tutam'],
  ['handful', 'avuç'],
  ['clove', 'diş'],
  ['sprig', 'dal'],
  ['pack', 'paket'],
]

export const UNITS = {
  en: UNIT_PAIRS.map(([en]) => en),
  tr: UNIT_PAIRS.map(([, tr]) => tr),
}

// Mirrors UNIT_ML: spoons and glasses have one fixed size, the same in both languages
export const UNIT_ML = { tsp: 5, dsp: 10, tbsp: 15, 'tea glass': 100, glass: 200 }

// Other spellings of a listed unit, from older meals (the prompt example once said "gr") and the model
const UNIT_ALIASES = {
  gr: 'g', gram: 'g', grams: 'g',
  pc: 'pcs', piece: 'pcs', pieces: 'pcs', tane: 'pcs',
  liter: 'l', litre: 'l', lt: 'l',
  teaspoon: 'tsp', teaspoons: 'tsp',
  tablespoon: 'tbsp', tablespoons: 'tbsp',
  glasses: 'glass', slices: 'slice', bunches: 'bunch', pinches: 'pinch',
  handfuls: 'handful', cloves: 'clove', sprigs: 'sprig', packs: 'pack',
}

// Row index for every known spelling, in either language
const UNIT_ROW = new Map(UNIT_PAIRS.flatMap((pair, i) => pair.map(name => [name.toLowerCase(), i])))
for (const [alias, unit] of Object.entries(UNIT_ALIASES)) UNIT_ROW.set(alias, UNIT_ROW.get(unit))

/** The unit list of the AI language (Turkish unless it's English, like the prompts). */
export function unitsFor(language = currentLanguage()) {
  return language === 'en' ? UNITS.en : UNITS.tr
}

/** The plain count unit (pcs / adet), used when an item has no unit. */
export function countUnit(language = currentLanguage()) {
  return unitsFor(language)[0]
}

/** A known unit in the given language; anything else as written. */
export function localizeUnit(unit, language = currentLanguage()) {
  if (typeof unit !== 'string') return unit
  const row = UNIT_ROW.get(unit.trim().toLowerCase())
  return row == null ? unit : UNIT_PAIRS[row][language === 'en' ? 0 : 1]
}

/** A spoon or glass with its fixed size ("tbsp (15 ml)"), any other unit as is; for the open unit list. */
export function unitWithSize(unit) {
  const ml = UNIT_ML[localizeUnit(unit, 'en')]
  return ml ? `${unit} (${ml} ml)` : unit
}

/** Infer a sensible default unit from a Turkish or English ingredient name, in the given language. */
export function getSmartUnit(name, language = currentLanguage()) {
  return localizeUnit(guessUnit(name.toLowerCase()), language)
}

// English unit for a lower-cased name; eggs, fruit and vegetables are counted
function guessUnit(n) {
  if (/yağ|oil|butter/.test(n))                            return 'tbsp'
  if (/^su$|^su |^water$|^water /.test(n))                 return 'ml'
  if (/peynir|lor|labne|cheese/.test(n))                   return 'g'
  if (/et|tavuk|hindi|kıyma|sosis|sucuk|pastırma|jambon|chicken|turkey|beef|ham|sausage|bacon|salami/.test(n)) return 'g'
  if (/ekmek|tost|pide|simit|bagel|bread|toast/.test(n))   return 'slice'
  if (/maydanoz|dereotu|nane|kekik|roka|fesleğen|parsley|dill|mint|thyme|rocket|arugula|basil|herb/.test(n)) return 'bunch'
  if (/sarımsak|garlic/.test(n))                           return 'clove'
  if (/tarçın|karabiber|tuz|pul biber|kimyon|cinnamon|black pepper|salt|pepper flakes|cumin/.test(n)) return 'tsp'
  return 'pcs'
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

/** Best unit for a new ingredient, in the given language: memory → smart default → pcs / adet. */
export function resolveUnit(name, language = currentLanguage()) {
  return localizeUnit(recallUnit(name) || getSmartUnit(name, language), language)
}

// Normalize an LLM meal to always have meal_name, a clean menu and a flat ingredients list.
// Handles both the old flat format and the menu format. A menu item with neither
// ingredients nor an amount (e.g. "Ayran" with an empty list) becomes a simple item ×1,
// so it never opens as an empty dish.
export function normalizeMeal(meal) {
  if (!meal) return meal
  const name = meal.meal_name || meal.menu_name || 'Meal'
  const count = countUnit()
  const menu = meal.menu?.map(item =>
    !item.ingredients?.length && item.amount == null
      ? { ...item, amount: 1, unit: item.unit || count, ingredients: [] }
      : item
  )
  // Derive flat ingredients from menu if not already present
  const ingredients = meal.ingredients && meal.ingredients.length > 0
    ? meal.ingredients
    : (menu || []).flatMap(item =>
        item.ingredients && item.ingredients.length > 0
          ? item.ingredients.map(ing => ({ name: ing.name, quantity: ing.amount ?? 1, unit: ing.unit || count }))
          : [{ name: item.name, quantity: item.amount ?? 1, unit: item.unit || count }]
      )
  return menu ? { ...meal, meal_name: name, menu, ingredients } : { ...meal, meal_name: name, ingredients }
}

// A meal's food as one string, so two copies of a meal compare equal whatever their order: each
// item is its name (any case), amount and unit (in English), a dish lists its ingredients the same
// way, and both lists are sorted. Marks, times, notes, methods and prep words don't count.
export function menuKey(meal) {
  if (!meal) return ''
  const menu = meal.menu?.length ? meal.menu : meal.menu_items
  const items = menu?.length
    ? menu
    : (meal.ingredients || []).map(ing => (typeof ing === 'object' && ing !== null
        ? { name: ing.name, amount: ing.quantity ?? ing.amount, unit: ing.unit }
        : { name: String(ing) }))
  const name = (x) => String(x.name ?? '').trim().toLowerCase()
  const part = (x) => {
    const amount = parseFloat(x.amount ?? 1)
    const unit = localizeUnit(String(x.unit || 'pcs'), 'en').trim().toLowerCase()
    return `${name(x)}|${isNaN(amount) ? '' : Math.round(amount * 100) / 100}|${unit}`
  }
  return items
    // A simple item has an amount; one with neither amount nor ingredients is a simple item ×1
    .map(item => (item.amount != null || !item.ingredients?.length
      ? part(item)
      : `${name(item)}[${item.ingredients.map(part).sort().join(';')}]`))
    .sort()
    .join('\n')
}
