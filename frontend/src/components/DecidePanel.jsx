import { useState, useEffect, useCallback, useMemo, useRef } from 'react'
import { getRatings, createRating, logMeal, addFavorite, deleteFavorite } from '../services/api'
import { countUnit } from '../utils/ingredients'
import MealEditor from './MealEditor'
import StarRating from './StarRating'
import TodaySupplements from './TodaySupplements'
import * as s from './DecidePanel.styles'

/**
 * "Today I ate" panel.
 *
 * Props:
 *   meal      — the chat meal selected for today (its obtained marks carry over)
 *   saved     — that card's saved "Today I ate" version, if any; the editor starts from it
 *   onSave    — async (meal) => void — Save stores the current meal with the card, then the panel
 *               closes (no Save without it)
 *   onClose   — Close drops unsaved edits
 *   onConfirm — the meal was logged (with ratings, or with Skip on the rating step)
 *   supplements, onToggleSupplement(id, takenNow) — today's supplements behind the 💊 button,
 *               each tap saved at once
 */
export default function DecidePanel({ meal, saved, onSave, onClose, onConfirm, supplements = [], onToggleSupplement }) {
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
  // What the editor starts from: the card's saved version if there is one, else the card.
  // Read once when the panel opens, so a push from another device never resets an open panel;
  // only Back from rating changes it, to return to the edited menu. `edited` marks a meal the
  // editor built (saved, or Back from rating): its menu is used as is, even when emptied.
  const [base, setBase] = useState(() => ({ meal: saved || meal, edited: !!saved }))
  // Save: 'idle' → 'saving' → closed, or 'error' (stays open to try again)
  const [saveState, setSaveState] = useState('idle')
  // Today's supplements list: open until a tap elsewhere in the panel (Confirm keeps it open)
  const [suppOpen, setSuppOpen] = useState(false)
  const suppRef = useRef(null)

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
    const { meal: start, edited } = base
    const menu = start?.menu || start?.menu_items
    if (menu && (menu.length > 0 || edited)) return { ...start, menu }
    const flat = start?.ingredients || []
    return {
      ...start,
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

  // An edit after a failed Save clears its note
  const handleEditorChange = useCallback(() => {
    setSaveState(prev => (prev === 'error' ? 'idle' : prev))
  }, [])

  // Save stores the current meal with the card and closes the panel; a failed save stays open
  const handleSave = async (current) => {
    setSaveState('saving')
    try {
      await onSave(current)
    } catch {
      setSaveState('error')
      return
    }
    onClose()
  }

  // Back from rating returns to the edited menu, not the original
  const handleBackToEdit = () => {
    if (pendingMealRef.current) setBase({ meal: pendingMealRef.current, edited: true })
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

  // MealEditor's ☆ → keep the menu in favorites for later; nothing is logged.
  // Returns the favorite's id, so a second tap can remove it.
  const handleFavorite = useCallback(async (currentMeal) => {
    const { id } = await addFavorite({
      meal_name: currentMeal.menu_name || currentMeal.meal_name || 'Breakfast',
      description: currentMeal.description,
      ingredients: currentMeal.ingredients || [],
      steps: currentMeal.steps || [],
      prep_time_min: currentMeal.prep_time_min,
      nutrition_note: currentMeal.nutrition_note,
      menu_items: currentMeal.menu || currentMeal.menu_items || null,
    })
    return id
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

  // Rating phase Skip — log the meal without rating anything (the items are asked again next time)
  const handleSkipRatings = useCallback(() => logWithoutRating(pendingMealRef.current || meal), [meal, logWithoutRating])

  const handleOverlayClick = (e) => {
    if (e.target === e.currentTarget) onClose()
  }

  // A tap anywhere in the panel except the supplements and Confirm closes the supplements list
  const handlePanelClickCapture = (e) => {
    if (!suppOpen || suppRef.current?.contains(e.target)) return
    if (e.target.closest?.('[data-keeps-supplements]')) return
    setSuppOpen(false)
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
            <button style={s.outlineBtn} onClick={handleSkipRatings} disabled={saving} title="Log the meal without rating">
              Skip
            </button>
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
      <div style={s.panel} onClickCapture={handlePanelClickCapture}>
        <div style={{ ...s.panelHeader, position: 'relative' }}>
          Today I ate
          <TodaySupplements
            open={suppOpen}
            onOpenChange={setSuppOpen}
            supplements={supplements}
            onToggle={(id, taken) => onToggleSupplement?.(id, taken)}
            containerRef={suppRef}
          />
        </div>
        <MealEditor
          meal={editorMeal}
          onFavorite={handleFavorite}
          onUnfavorite={deleteFavorite}
          onClose={onClose}
          showPrepTime={true}
          editPrepTime={true}
          menuMode={true}
          checkFridge
          onMissingChange={handleMissingChange}
          onChange={handleEditorChange}
          extraActions={(buildCurrentMeal) => (
            <>
              {onSave && (
                <button
                  style={s.outlineBtn}
                  onClick={() => handleSave(buildCurrentMeal())}
                  disabled={saving || saveState === 'saving'}
                  title="Keep these edits with this chat meal, on every device, and close"
                >
                  {saveState === 'saving' ? '...' : 'Save'}
                </button>
              )}
              <button
                data-keeps-supplements
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
        {saveState === 'error' && (
          <div style={s.saveNote}>Couldn&apos;t save. Check the connection and try again.</div>
        )}
        {missing?.length > 0 && (
          <div style={s.missingNote}>
            Not in your fridge: {missing.join(', ')}. Tap an item, or a dish&apos;s name, once you have it, or remove it.
          </div>
        )}
      </div>
    </div>
  )
}
