import { useState, useEffect, useCallback, useRef } from 'react'
import { getRatings, createRating, logMeal } from '../services/api'
import MealEditor from './MealEditor'
import StarRating from './StarRating'
import * as s from './DecidePanel.styles'

export default function DecidePanel({ meal, onClose, onConfirm }) {
  // Phase: 'edit' = MealEditor open, 'rate' = star-rating unrated items
  const [phase, setPhase] = useState('edit')
  const [ratings, setRatings] = useState({})
  const [existingRatings, setExistingRatings] = useState([])
  const [saving, setSaving] = useState(false)
  // Holds the meal state captured from MealEditor when proceeding to rating
  const pendingMealRef = useRef(null)

  // Reset phase whenever a new meal is passed in
  useEffect(() => {
    setPhase('edit')
    setRatings({})
    pendingMealRef.current = null
  }, [meal])

  // Load existing ratings to skip already-rated products in the rate phase
  useEffect(() => {
    getRatings()
      .then(setExistingRatings)
      .catch(() => setExistingRatings([]))
  }, [])

  const isMenuFormat = !!(meal?.menu && meal.menu.length > 0)

  // Core log-meal call — used by both direct save and post-rating save
  const doLogMeal = useCallback(async (updatedMeal) => {
    await logMeal({
      meal_name: updatedMeal.menu_name || updatedMeal.meal_name || 'Kahvaltı',
      description: updatedMeal.description || '',
      ingredients: updatedMeal.ingredients || [],
      steps: updatedMeal.steps || [],
      prep_time_min: updatedMeal.prep_time_min ?? null,
      nutrition_note: updatedMeal.nutrition_note || '',
      menu_items: updatedMeal.menu || updatedMeal.menu_items || null,
    })
    onConfirm?.()
  }, [onConfirm])

  // MealEditor's Save button → log directly without rating
  const handleEditorSave = useCallback(async (updatedMeal) => {
    setSaving(true)
    try {
      await doLogMeal(updatedMeal)
    } catch { /* ignore */ }
    setSaving(false)
  }, [doLogMeal])

  // MealEditor's extraActions "Confirm" button → collect ratings for unrated items, then log
  const handleProceedToRating = useCallback((updatedMeal) => {
    pendingMealRef.current = updatedMeal
    const ratedNames = new Set(existingRatings.map(r => r.product_name.toLowerCase()))
    const topItems = isMenuFormat
      ? (updatedMeal.menu || [])
      : (updatedMeal.ingredients || [])
    const unrated = topItems.filter(item => !ratedNames.has(item.name.toLowerCase()))
    if (unrated.length === 0) {
      // All already rated — skip to save
      handleEditorSave(updatedMeal)
      return
    }
    const defaults = {}
    unrated.forEach(item => { defaults[item.name] = 10 })
    setRatings(defaults)
    setPhase('rate')
  }, [existingRatings, isMenuFormat, handleEditorSave])

  // Rating phase Save — persist ratings then log meal
  const handleSaveWithRatings = useCallback(async () => {
    setSaving(true)
    try {
      for (const [name, rating] of Object.entries(ratings)) {
        try { await createRating(name, rating) } catch { /* already rated or error — skip */ }
      }
      await doLogMeal(pendingMealRef.current || meal)
    } catch { /* ignore */ }
    setSaving(false)
  }, [ratings, meal, doLogMeal])

  const handleOverlayClick = (e) => {
    if (e.target === e.currentTarget) onClose()
  }

  // ── Rate phase ────────────────────────────────────────────────────────────

  if (phase === 'rate') {
    const unratedItems = Object.keys(ratings)
    return (
      <div style={s.overlay} onClick={handleOverlayClick}>
        <div style={s.panel}>
          <div style={s.panelHeader}>Rate</div>
          <div style={s.itemList}>
            {unratedItems.map(item => (
              <div key={item} style={s.rateRow}>
                <span style={s.rateLabel}>{item}</span>
                <StarRating
                  value={ratings[item]}
                  onChange={(n) => setRatings(prev => ({ ...prev, [item]: n }))}
                />
              </div>
            ))}
          </div>
          <div style={s.actions}>
            <button style={s.backBtn} onClick={() => setPhase('edit')}>Back</button>
            <button style={s.confirmBtn} onClick={handleSaveWithRatings} disabled={saving}>
              {saving ? '...' : 'Save'}
            </button>
          </div>
        </div>
      </div>
    )
  }

  // ── Edit phase ────────────────────────────────────────────────────────────

  return (
    <div style={s.overlay} onClick={handleOverlayClick}>
      <div style={s.panel}>
        <div style={s.panelHeader}>Today I ate</div>
        <MealEditor
          meal={{ ...meal, menu: meal?.menu || meal?.menu_items || undefined }}
          onSave={handleEditorSave}
          onClose={onClose}
          showPrepTime={true}
          editPrepTime={true}
          menuMode={isMenuFormat}
          extraActions={(buildCurrentMeal) => (
            <button
              style={s.confirmBtn}
              onClick={() => handleProceedToRating(buildCurrentMeal())}
              disabled={saving}
            >
              Confirm
            </button>
          )}
        />
      </div>
    </div>
  )
}
