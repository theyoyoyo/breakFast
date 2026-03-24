import { useState, useMemo } from 'react'
import { addFavorite } from '../services/api'
import MealEditor from './MealEditor'
import * as s from './MealBlock.styles'
import * as es from './MealEditor.styles'

const BREAKFAST_EMOJIS = ['🍳', '🥐', '🧀', '🥚', '🫕', '🥞', '🧇', '🥣', '🍞', '🥯', '🫖', '☕', '🥗', '🥑', '🍯']

/**
 * Pick a stable random emoji from the list based on a string seed.
 */
function pickEmoji(seed) {
  let hash = 0
  const str = String(seed || '')
  for (let i = 0; i < str.length; i++) {
    hash = ((hash << 5) - hash + str.charCodeAt(i)) | 0
  }
  return BREAKFAST_EMOJIS[Math.abs(hash) % BREAKFAST_EMOJIS.length]
}

/**
 * Format a single ingredient for display.
 */
function formatIngredient(item) {
  if (typeof item === 'object' && item !== null && item.name) {
    const qty = item.quantity != null ? item.quantity : ''
    const unit = item.unit || ''
    return `${qty} ${unit} ${item.name}`.trim()
  }
  return String(item)
}

/**
 * Clickable meal summary block rendered inline in chat.
 * Shows checkbox, meal names, prep time, and analysis button.
 * Click opens the shared MealEditor in an overlay.
 */
export default function MealBlock({ meal, checked, onCheck, onSave, onAnalyze, analyzing }) {
  const [panelOpen, setPanelOpen] = useState(false)
  const [favSaving, setFavSaving] = useState(false)
  const [favAdded, setFavAdded] = useState(false)

  const emoji = useMemo(() => pickEmoji(meal?.meal_name || meal?.meal_id), [meal?.meal_name, meal?.meal_id])

  const ingredients = meal?.ingredients || []
  const displayNames = ingredients.length > 0
    ? ingredients.map(formatIngredient).join(', ')
    : meal?.meal_name || 'Meal'

  const handleOverlayClick = (e) => {
    if (e.target === e.currentTarget) setPanelOpen(false)
  }

  const handleEditorSave = (updated) => {
    onSave?.(updated)
    setPanelOpen(false)
  }

  const handleCopyToFavorites = async () => {
    setFavSaving(true)
    try {
      await addFavorite({
        meal_name: meal?.meal_name || 'Meal',
        description: meal?.description,
        ingredients: meal?.ingredients || [],
        steps: meal?.steps || [],
        prep_time_min: meal?.prep_time_min,
        nutrition_note: meal?.nutrition_note,
      })
      setFavAdded(true)
    } catch { /* ignore */ }
    setFavSaving(false)
  }

  return (
    <>
      <div style={s.blockRow}>
        <button
          style={s.checkbox(checked)}
          onClick={(e) => { e.stopPropagation(); onCheck?.() }}
          title={checked ? 'Selected as today\'s meal' : 'Select as today\'s meal'}
        >
          {checked ? '☑' : '☐'}
        </button>
        <div style={s.block} onClick={() => { setPanelOpen(true); setFavAdded(false) }}>
          <span style={s.blockIcon}>{emoji}</span>
          <span style={s.blockText}>{displayNames}</span>
          {meal?.prep_time_min && <span style={s.prepBadge}>⏱ {meal.prep_time_min}m</span>}
        </div>
        <button
          style={s.analyzeBtn(analyzing)}
          onClick={(e) => { e.stopPropagation(); onAnalyze?.() }}
          disabled={analyzing}
          title="Nutrition analysis"
        >
          {analyzing ? '⏳' : '📊'}
        </button>
      </div>

      {panelOpen && (
        <div style={s.overlay} onClick={handleOverlayClick}>
          <div style={s.panel}>
            <MealEditor
              meal={meal}
              onSave={handleEditorSave}
              onClose={() => setPanelOpen(false)}
              showPrepTime={true}
              editPrepTime={true}
              showId={true}
              extraActions={
                <button
                  style={favAdded ? es.copyToFavBtnDone : es.copyToFavBtn}
                  onClick={handleCopyToFavorites}
                  disabled={favSaving || favAdded}
                  title={favAdded ? 'Added to favorites' : 'Copy to favorites'}
                >
                  {favSaving ? '...' : favAdded ? '✓ Saved' : '⭐ Save'}
                </button>
              }
            />
          </div>
        </div>
      )}
    </>
  )
}
