import { useState, useMemo } from 'react'
import { addFavorite, deleteFavorite } from '../services/api'
import { formatIngredient } from '../utils/ingredients'
import { mealEmoji } from '../utils/emoji'
import { useMealReadiness } from '../hooks/useMealReadiness'
import { useLanguage } from '../hooks/useLanguage'
import MealEditor from './MealEditor'
import ReadinessIcon from './ReadinessIcon'
import * as s from './MealBlock.styles'

/**
 * Clickable meal summary block rendered inline in chat.
 * Shows checkbox, meal names, prep time, and analysis button.
 * Click opens the shared MealEditor in an overlay.
 * The icon's ring shows readiness: green when everything is in the fridge (or marked
 * as obtained), yellow when something is still missing. fridgeCheckKey re-runs the check.
 */
export default function MealBlock({ meal, checked, onCheck, onSave, onAnalyze, analyzing, onSchedule, scheduling, fridgeCheckKey }) {
  const [panelOpen, setPanelOpen] = useState(false)

  const { readiness, stillMissing } = useMealReadiness(meal, fridgeCheckKey)
  const language = useLanguage()

  const menuItems = meal?.menu
  const isMenuFormat = menuItems && menuItems.length > 0

  const displayNames = isMenuFormat
    ? menuItems.map(i => i.name).join(', ')
    : (meal?.ingredients || []).length > 0
      ? meal.ingredients.map(ing => formatIngredient(ing, language)).join(', ')
      : meal?.meal_name || 'Meal'

  const mealName = meal?.menu_name || meal?.meal_name || 'Meal'
  // The icon the server gave the card (#244); an older card without one gets the same icon from its name
  const emoji = mealEmoji(meal, mealName)
  // Stable object: MealEditor resets its edits whenever it receives a new meal
  const editorMeal = useMemo(() => ({ ...meal, meal_name: mealName }), [meal, mealName])

  const handleOverlayClick = (e) => {
    if (e.target === e.currentTarget) setPanelOpen(false)
  }

  const handleEditorSave = (updated) => {
    onSave?.(updated)
    setPanelOpen(false)
  }

  // Called by MealEditor with the current edited state — always saves what user sees.
  // Returns the favorite's id, so a second tap on the star can remove it.
  const handleFavorite = async (currentMeal) => {
    const { id } = await addFavorite({
      meal_name: currentMeal.menu_name || currentMeal.meal_name || mealName,
      description: currentMeal.description,
      ingredients: currentMeal.ingredients || [],
      steps: currentMeal.steps || [],
      prep_time_min: currentMeal.prep_time_min,
      nutrition_note: currentMeal.nutrition_note,
      menu_items: currentMeal.menu || currentMeal.menu_items || null,
      emoji: currentMeal.emoji || emoji,
    })
    return id
  }

  return (
    <>
      <div style={s.blockWrapper}>
        <div style={s.titleBar} onClick={() => setPanelOpen(true)}>
          <ReadinessIcon emoji={emoji} readiness={readiness} stillMissing={stillMissing} />
          <span style={s.titleName}>{mealName}</span>
          {meal?.prep_time_min && <span style={s.titlePrep}>⏱ {meal.prep_time_min}m</span>}
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
            title={checked ? 'Selected as today\'s meal — tap to unselect' : 'Select as today\'s meal'}
          >
            {checked ? '☑' : '☐'}
          </button>
          <div style={s.block} onClick={() => setPanelOpen(true)}>
            <span style={s.blockText}>{displayNames}</span>
          </div>
        </div>
      </div>

      {panelOpen && (
        <div style={s.overlay} onClick={handleOverlayClick}>
          <div style={s.panel}>
            <MealEditor
              meal={editorMeal}
              onSave={handleEditorSave}
              onClose={() => setPanelOpen(false)}
              showPrepTime={true}
              editPrepTime={true}
              menuMode={isMenuFormat}
              onFavorite={handleFavorite}
              onUnfavorite={deleteFavorite}
              checkFridge
            />
          </div>
        </div>
      )}
    </>
  )
}
