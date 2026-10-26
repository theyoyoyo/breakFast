import { useState, useEffect } from 'react'
import { checkMissingIngredients } from '../services/api'

/**
 * Is this meal ready to make from the fridge?
 * Returns { readiness: 'ready' | 'missing' | null, stillMissing: [names] | null }.
 * null means not checked yet or offline. Items in meal.obtained count as available.
 * The check re-runs when the menu's content or checkKey changes (not on every new object).
 */
export function useMealReadiness(meal, checkKey) {
  const [missing, setMissing] = useState(null)
  const menu = meal?.menu || meal?.menu_items
  const contentKey = JSON.stringify(menu || meal?.ingredients || [])

  useEffect(() => {
    if (!meal) return
    let cancelled = false
    checkMissingIngredients(menu ? { ...meal, menu } : meal)
      .then(res => { if (!cancelled) setMissing(res?.missing || []) })
      .catch(() => {}) // offline — no indicator
    return () => { cancelled = true }
  }, [contentKey, checkKey]) // eslint-disable-line react-hooks/exhaustive-deps

  const stillMissing = missing ? missing.filter(name => !(meal?.obtained || []).includes(name)) : null
  const readiness = !stillMissing ? null : stillMissing.length ? 'missing' : 'ready'
  return { readiness, stillMissing }
}
