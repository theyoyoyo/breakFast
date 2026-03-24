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

/**
 * Get the display name of an ingredient (works for both string and structured forms).
 */
export function getIngredientName(item) {
  if (typeof item === 'object' && item !== null) return item.name || ''
  return String(item)
}

/**
 * Clamp a quantity string to max 2 decimal places and return as number.
 * Returns null if the input is empty or invalid.
 */
export function parseQuantity(val) {
  if (val === '' || val === null || val === undefined) return null
  const num = parseFloat(val)
  if (isNaN(num)) return null
  return Math.round(num * 100) / 100
}
