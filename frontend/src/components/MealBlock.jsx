import { useState } from 'react'
import { addFavorite } from '../services/api'
import { formatIngredient } from '../utils/ingredients'
import MealEditor from './MealEditor'
import * as s from './MealBlock.styles'
import * as es from './MealEditor.styles'

const BREAKFAST_EMOJIS = [
  '🍳', '🥐', '🧀', '🥚', '🫕', '🥞', '🧇', '🥣', '🍞', '🥯', '🫖', '☕',
  '🥗', '🥑', '🍯', '🫒', '🧈', '🥛', '🍵', '🫐', '🍓', '🍌', '🍊', '🍇',
  '🥜', '🌰', '🥒', '🍅', '🫑', '🌿', '🌶️', '🧄', '🫘', '🥕', '🌽', '🥦',
  '🍋', '🥝', '🍑', '🫚', '🥥', '🧆', '🥙', '🫓', '🥖', '🥨', '🥮', '🍠',
]

function pickEmoji() {
  return BREAKFAST_EMOJIS[Math.floor(Math.random() * BREAKFAST_EMOJIS.length)]
}

/**
 * Clickable meal summary block rendered inline in chat.
 * Shows checkbox, meal names, prep time, and analysis button.
 * Click opens the shared MealEditor in an overlay.
 */
export default function MealBlock({ meal, checked, onCheck, onSave, onAnalyze, analyzing, onSchedule, scheduling }) {
  const [panelOpen, setPanelOpen] = useState(false)
  const [favSaving, setFavSaving] = useState(false)
  const [favAdded, setFavAdded] = useState(false)

  const [emoji] = useState(pickEmoji)

  const menuItems = meal?.menu
  const isMenuFormat = menuItems && menuItems.length > 0

  // Display text: menu item names if new format, else flat ingredients
  const displayNames = isMenuFormat
    ? menuItems.map(i => i.name).join(', ')
    : (meal?.ingredients || []).length > 0
      ? (meal.ingredients).map(formatIngredient).join(', ')
      : meal?.meal_name || 'Meal'

  const mealName = meal?.menu_name || meal?.meal_name || 'Meal'

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
        meal_name: mealName,
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
      <div style={s.blockWrapper}>
        <div style={s.titleBar} onClick={() => { setPanelOpen(true); setFavAdded(false) }}>
          <span style={s.titleIcon}>{emoji}</span>
          <span style={s.titleName}>{mealName}</span>
          {meal?.prep_time_min && <span style={s.titlePrep}>⏱ {meal.prep_time_min}m</span>}
          {meal?.id && <span style={s.titleId}>#{meal.id}</span>}
        </div>
        <div style={s.blockRow}>
          <button
            style={s.analyzeBtn(scheduling)}
            onClick={(e) => { e.stopPropagation(); onSchedule?.() }}
            disabled={scheduling}
            title="Prep timeline"
          >
            {scheduling ? '⏳' : '📋'}
          </button>
          <button
            style={s.analyzeBtn(analyzing)}
            onClick={(e) => { e.stopPropagation(); onAnalyze?.() }}
            disabled={analyzing}
            title="Nutrition analysis"
          >
            {analyzing ? '⏳' : '📊'}
          </button>
          <button
            style={s.checkbox(checked)}
            onClick={(e) => { e.stopPropagation(); onCheck?.() }}
            title={checked ? 'Selected as today\'s meal' : 'Select as today\'s meal'}
          >
            {checked ? '☑' : '☐'}
          </button>
          <div style={s.block} onClick={() => { setPanelOpen(true); setFavAdded(false) }}>
            <span style={s.blockText}>{displayNames}</span>
          </div>
        </div>
      </div>

      {panelOpen && (
        <div style={s.overlay} onClick={handleOverlayClick}>
          <div style={s.panel}>
            <MealEditor
              meal={{ ...meal, meal_name: mealName }}
              onSave={handleEditorSave}
              onClose={() => setPanelOpen(false)}
              showPrepTime={true}
              editPrepTime={true}
              showId={true}
              menuMode={isMenuFormat}
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
