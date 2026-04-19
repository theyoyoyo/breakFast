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

/** Format a menu sub-ingredient: {name, amount, unit} → "2 adet Yumurta" */
function formatSubIngredient(ing) {
  if (typeof ing === 'string') return ing
  const amt = ing.amount != null ? ing.amount : (ing.quantity != null ? ing.quantity : '')
  const unit = ing.unit || ''
  return `${amt} ${unit} ${ing.name}`.trim()
}

/** Menu item row with expandable sub-ingredients for complex dishes. */
function MenuItemRow({ item }) {
  const [open, setOpen] = useState(false)
  const hasIngredients = item.ingredients && item.ingredients.length > 0
  const simpleLabel = item.amount != null
    ? `${item.amount} ${item.unit || ''} ${item.name}`.trim()
    : item.name

  return (
    <div style={s.menuItemRow}>
      <div style={s.menuItemHeader} onClick={() => hasIngredients && setOpen(o => !o)}>
        <span style={s.menuItemName}>{simpleLabel}</span>
        {hasIngredients && (
          <span style={s.menuItemToggle}>{open ? '▲' : '▼'}</span>
        )}
      </div>
      {open && hasIngredients && (
        <div style={s.menuItemIngredients}>
          {item.ingredients.map((ing, i) => (
            <span key={i} style={s.menuSubIngredient}>{formatSubIngredient(ing)}</span>
          ))}
        </div>
      )}
    </div>
  )
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
  // Display text: menu item names if new format, else ingredients
  const displayNames = menuItems && menuItems.length > 0
    ? menuItems.map(i => i.name).join(', ')
    : (meal?.ingredients || []).length > 0
      ? (meal.ingredients).map(formatIngredient).join(', ')
      : meal?.meal_name || 'Meal'

  const handleOverlayClick = (e) => {
    if (e.target === e.currentTarget) setPanelOpen(false)
  }

  const handleEditorSave = (updated) => {
    // Preserve menu if user didn't explicitly clear it
    if (menuItems && !updated.menu) {
      updated = { ...updated, menu: menuItems }
    }
    onSave?.(updated)
    setPanelOpen(false)
  }

  const handleCopyToFavorites = async () => {
    setFavSaving(true)
    try {
      await addFavorite({
        meal_name: meal?.meal_name || meal?.menu_name || 'Meal',
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

  const mealName = meal?.menu_name || meal?.meal_name || 'Meal'

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
            {menuItems && menuItems.length > 0 && (
              <div style={s.menuSection}>
                {menuItems.map((item, i) => (
                  <MenuItemRow key={i} item={item} />
                ))}
              </div>
            )}
            <MealEditor
              meal={{ ...meal, meal_name: mealName }}
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
