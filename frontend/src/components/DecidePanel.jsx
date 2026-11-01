import { useState, useEffect, useCallback, useMemo, useRef } from 'react'
import { getRatings, createRating, logMeal, addFavorite } from '../services/api'
import { countUnit } from '../utils/ingredients'
import MealEditor from './MealEditor'
import StarRating from './StarRating'
import * as s from './DecidePanel.styles'

/**
 * "Today I ate" panel.
 *
 * Props:
 *   meal          — the chat meal selected for today (its obtained marks carry over)
 *   draft         — the user's earlier edits of that same meal, if any; used instead of meal
 *   onDraftChange — (draftMeal) => void — live editor state, so the parent can keep the draft
 *   onClose / onConfirm
 */
export default function DecidePanel({ meal, draft, onDraftChange, onClose, onConfirm }) {
  // Phase: 'edit' = MealEditor open, 'rate' = star-rating unrated items
  const [phase, setPhase] = useState('edit')
  const [ratings, setRatings] = useState({})
  const [existingRatings, setExistingRatings] = useState([])
  const [saving, setSaving] = useState(false)
  // Ingredients still missing (not in the fridge, not marked as obtained) — Confirm waits for none
  // null until the first fridge check answers, so nothing is unlocked early.
  const [missing, setMissing] = useState(null)
  // Holds the meal state captured from MealEditor when proceeding to rating
  const pendingMealRef = useRef(null)
  // What the editor starts from: the draft if there is one, else the selected meal.
  // Only changes on purpose (Back from rating, another meal selected), never on every edit.
  const [base, setBase] = useState(() => draft || meal)

  // Another meal selected while open → start over from it
  const sourceRef = useRef(meal)
  useEffect(() => {
    if (sourceRef.current === meal) return
    sourceRef.current = meal
    setBase(meal)
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

  // Build a menu-format meal for MealEditor (always menuMode so "+ Dish" is always available).
  // If the incoming meal already has a menu, use it. If it has flat ingredients, convert them to
  // simple menu items. If it's empty, MealEditor starts blank.
  // Memoized: MealEditor resets its edits whenever it receives a new meal object
  const editorMeal = useMemo(() => {
    const menu = base?.menu || base?.menu_items
    if (menu && menu.length > 0) return { ...base, menu }
    const flat = base?.ingredients || []
    return {
      ...base,
      menu: flat.map(ing => ({
        name: ing.name,
        amount: ing.quantity ?? ing.amount ?? 1,
        unit: ing.unit || countUnit(),
        ingredients: [],
      })),
    }
  }, [base])

  const handleMissingChange = useCallback((names) => {
    setMissing(prev => (prev && prev.join('\n') === names.join('\n') ? prev : names))
  }, [])

  // Keep the parent's draft in step with every edit (the latest callback, without re-renders)
  const draftCallbackRef = useRef(onDraftChange)
  draftCallbackRef.current = onDraftChange
  const handleEditorChange = useCallback((current) => draftCallbackRef.current?.(current), [])

  // Back from rating returns to the edited menu, not the original
  const handleBackToEdit = () => {
    if (pendingMealRef.current) setBase(pendingMealRef.current)
    setPhase('edit')
  }

  // Core log-meal call — used by both direct save and post-rating save
  const doLogMeal = useCallback(async (updatedMeal) => {
    await logMeal({
      meal_name: updatedMeal.menu_name || updatedMeal.meal_name || 'Breakfast',
      description: updatedMeal.description || '',
      ingredients: updatedMeal.ingredients || [],
      steps: updatedMeal.steps || [],
      prep_time_min: updatedMeal.prep_time_min ?? null,
      nutrition_note: updatedMeal.nutrition_note || '',
      menu_items: updatedMeal.menu || updatedMeal.menu_items || null,
    })
    onConfirm?.()
  }, [onConfirm])

  // Log without the rating step — used when every item is already rated
  const logWithoutRating = useCallback(async (updatedMeal) => {
    setSaving(true)
    try {
      await doLogMeal(updatedMeal)
    } catch { /* ignore */ }
    setSaving(false)
  }, [doLogMeal])

  // MealEditor's ⭐ Fav → keep the menu in favorites for later; nothing is logged
  const handleFavorite = useCallback(async (currentMeal) => {
    await addFavorite({
      meal_name: currentMeal.menu_name || currentMeal.meal_name || 'Breakfast',
      description: currentMeal.description,
      ingredients: currentMeal.ingredients || [],
      steps: currentMeal.steps || [],
      prep_time_min: currentMeal.prep_time_min,
      nutrition_note: currentMeal.nutrition_note,
      menu_items: currentMeal.menu || currentMeal.menu_items || null,
    })
  }, [])

  // "Confirm" → collect ratings for unrated items, then log (waits until nothing is missing)
  const handleProceedToRating = useCallback((updatedMeal) => {
    pendingMealRef.current = updatedMeal
    const ratedNames = new Set(existingRatings.map(r => r.product_name.toLowerCase()))
    // Always menu format now — top-level menu items are what the user rates
    const topItems = updatedMeal.menu || updatedMeal.ingredients || []
    const unrated = topItems.filter(item => !ratedNames.has(item.name.toLowerCase()))
    if (unrated.length === 0) {
      // All already rated — skip to save
      logWithoutRating(updatedMeal)
      return
    }
    const defaults = {}
    unrated.forEach(item => { defaults[item.name] = 10 })
    setRatings(defaults)
    setPhase('rate')
  }, [existingRatings, logWithoutRating])

  // Rating phase Confirm — persist ratings then log meal
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
            <button style={s.backBtn} onClick={handleBackToEdit}>Back</button>
            <button style={s.confirmBtn} onClick={handleSaveWithRatings} disabled={saving}>
              {saving ? '...' : 'Confirm'}
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
          meal={editorMeal}
          onFavorite={handleFavorite}
          onClose={onClose}
          showPrepTime={true}
          editPrepTime={true}
          menuMode={true}
          checkFridge
          onMissingChange={handleMissingChange}
          onChange={handleEditorChange}
          extraActions={(buildCurrentMeal, { markAllObtained }) => (
            <>
              <button
                style={missing?.length ? s.ateOutBtn : s.ateOutBtnIdle}
                onClick={markAllObtained}
                disabled={saving || !missing?.length}
                title="Ate out: mark every missing item as obtained"
              >
                Ate out
              </button>
              <button
                style={missing?.length === 0 ? s.confirmBtn : s.confirmBtnBlocked}
                onClick={() => handleProceedToRating(buildCurrentMeal())}
                disabled={saving || missing?.length !== 0}
                title={missing === null
                  ? 'Checking your fridge…'
                  : missing.length ? 'Some ingredients are not in your fridge' : undefined}
              >
                Confirm
              </button>
            </>
          )}
        />
        {missing?.length > 0 && (
          <div style={s.missingNote}>
            Not in your fridge: {missing.join(', ')}. Tap an item once you have it, remove it, or use Ate out if you ate somewhere else.
          </div>
        )}
      </div>
    </div>
  )
}
