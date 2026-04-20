import { useState, useEffect } from 'react'
import { normalizeItem } from '../utils/ingredients'
import * as s from './MealEditor.styles'

/**
 * Shared meal editor component used by MealBlock, FavoritesPanel, and SettingsPanel.
 *
 * Props:
 *   meal         — meal object { meal_name, ingredients, menu, steps, prep_time_min, ... }
 *   onSave       — (updatedMeal) => void — called with the edited meal
 *   onClose      — () => void — close the editor
 *   showPrepTime — boolean — whether to show prep_time_min input (default true)
 *   editPrepTime — boolean — whether prep time is editable (default true)
 *   extraActions — ReactNode — extra buttons to render in the actions row
 *   showId       — boolean — show meal ID badge (default false)
 *   menuMode     — boolean — edit meal.menu (multi-item) instead of meal.ingredients
 */
export default function MealEditor({
  meal,
  onSave,
  onClose,
  showPrepTime = true,
  editPrepTime = true,
  extraActions,
  showId = false,
  menuMode = false,
}) {
  // In menu mode: items are menu entries {name, amount?, unit?, ingredients: []}
  // In normal mode: items are flat ingredients {name, quantity, unit}
  const [items, setItems] = useState(() => initItems(meal, menuMode))
  const [mealName, setMealName] = useState(meal?.meal_name || meal?.menu_name || 'Meal')
  const [prepTime, setPrepTime] = useState(meal?.prep_time_min ?? '')
  const [newItem, setNewItem] = useState('')

  useEffect(() => {
    setItems(initItems(meal, menuMode))
    setMealName(meal?.meal_name || meal?.menu_name || 'Meal')
    setPrepTime(meal?.prep_time_min ?? '')
    setNewItem('')
  }, [meal, menuMode])

  // ── Normal mode helpers ──────────────────────────────────────────────────

  const handleDelete = (idx) => setItems(prev => prev.filter((_, i) => i !== idx))

  const handleQuantityChange = (idx, val) => {
    if (val !== '' && !/^\d*\.?\d{0,2}$/.test(val)) return
    setItems(prev => prev.map((item, i) =>
      i === idx ? { ...item, [menuMode ? 'amount' : 'quantity']: val === '' ? '' : val } : item
    ))
  }

  const handleQuantityBlur = (idx) => {
    const key = menuMode ? 'amount' : 'quantity'
    setItems(prev => prev.map((item, i) => {
      if (i !== idx) return item
      const num = parseFloat(item[key])
      return { ...item, [key]: (!isNaN(num) && num > 0) ? Math.round(num * 100) / 100 : 1 }
    }))
  }

  const handleQuantityStep = (idx, delta) => {
    const key = menuMode ? 'amount' : 'quantity'
    setItems(prev => prev.map((item, i) => {
      if (i !== idx) return item
      const current = typeof item[key] === 'number' ? item[key] : parseFloat(item[key]) || 1
      const next = Math.round((current + delta) * 100) / 100
      return { ...item, [key]: next > 0 ? next : current }
    }))
  }

  const handleAdd = (isDish = false) => {
    const v = newItem.trim()
    if (!v) return
    if (items.some(item => item.name.toLowerCase() === v.toLowerCase())) return
    if (menuMode) {
      const entry = isDish
        ? { name: v, ingredients: [] }
        : { name: v, amount: 1, unit: 'adet', ingredients: [] }
      setItems(prev => [...prev, entry])
    } else {
      setItems(prev => [...prev, { name: v, quantity: 1, unit: 'adet' }])
    }
    setNewItem('')
  }

  const handlePrepTimeChange = (val) => {
    if (val === '') { setPrepTime(''); return }
    const num = parseInt(val, 10)
    if (!isNaN(num) && num >= 0 && num <= 999) setPrepTime(num)
  }

  const handleSave = () => {
    const finalPrepTime = typeof prepTime === 'number' ? prepTime : (parseInt(prepTime, 10) || null)
    const name = mealName.trim() || meal?.meal_name || meal?.menu_name || 'Meal'

    if (menuMode) {
      const finalMenu = items.map(item => {
        if (isSimpleItem(item)) {
          const num = parseFloat(item.amount)
          return { ...item, amount: (!isNaN(num) && num > 0) ? Math.round(num * 100) / 100 : 1 }
        }
        return item
      })
      onSave?.({ ...meal, meal_name: name, menu_name: name, menu: finalMenu, prep_time_min: finalPrepTime })
    } else {
      const finalItems = items.map(item => ({
        ...item,
        quantity: (() => {
          const num = parseFloat(item.quantity)
          return (!isNaN(num) && num > 0) ? Math.round(num * 100) / 100 : 1
        })(),
      }))
      onSave?.({ ...meal, meal_name: name, ingredients: finalItems, prep_time_min: finalPrepTime })
    }
  }

  return (
    <div style={s.editorContainer}>
      <div style={s.editorHeader}>
        <input
          style={s.nameInput}
          value={mealName}
          onChange={(e) => { if (e.target.value.length <= 100) setMealName(e.target.value) }}
          onBlur={() => { if (!mealName.trim()) setMealName(meal?.meal_name || meal?.menu_name || 'Meal') }}
          placeholder="Meal name"
        />
        {showId && <span style={s.mealId}>#{meal?.id || 0}</span>}
        {showPrepTime && (
          <div style={s.prepTimeGroup}>
            <span style={s.prepTimeLabel}>⏱</span>
            {editPrepTime ? (
              <input
                style={s.prepTimeInput}
                type="text"
                inputMode="numeric"
                value={prepTime}
                onChange={(e) => handlePrepTimeChange(e.target.value)}
                placeholder="—"
              />
            ) : (
              <span style={s.prepTimeValue}>{prepTime || '—'}</span>
            )}
            <span style={s.prepTimeUnit}>m</span>
          </div>
        )}
      </div>

      <div style={s.itemList}>
        {items.map((item, idx) => (
          menuMode && !isSimpleItem(item)
            ? (
              // Dish row — no qty stepper
              <div key={idx} style={s.itemRow}>
                <span style={s.dishBadge}>🍳</span>
                <span style={{ ...s.itemText, fontWeight: 500 }}>{item.name}</span>
                <div style={s.itemActions}>
                  <button style={s.deleteBtn} onClick={() => handleDelete(idx)} title="Delete">🗑️</button>
                </div>
              </div>
            ) : (
              // Simple item row — with qty stepper
              <div key={idx} style={s.itemRow}>
                <div style={s.qtyGroup}>
                  <button style={s.arrowBtn} onClick={() => handleQuantityStep(idx, -1)}>▼</button>
                  <input
                    style={s.qtyInput}
                    type="text"
                    inputMode="decimal"
                    value={menuMode ? (item.amount ?? 1) : item.quantity}
                    onChange={(e) => handleQuantityChange(idx, e.target.value)}
                    onBlur={() => handleQuantityBlur(idx)}
                  />
                  <button style={s.arrowBtn} onClick={() => handleQuantityStep(idx, 1)}>▲</button>
                </div>
                <span style={s.unitLabel}>{item.unit}</span>
                <span style={s.itemText}>{item.name}</span>
                <div style={s.itemActions}>
                  <button style={s.deleteBtn} onClick={() => handleDelete(idx)} title="Delete">🗑️</button>
                </div>
              </div>
            )
        ))}
      </div>

      <div style={s.addRow}>
        <input
          style={s.addInput}
          value={newItem}
          onChange={(e) => setNewItem(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleAdd(false)}
          placeholder={menuMode ? 'Item or dish name…' : 'Add item…'}
        />
        {menuMode ? (
          <>
            <button style={s.addBtn} onClick={() => handleAdd(false)} title="Add simple item (peynir, zeytin…)">＋ Item</button>
            <button style={s.addBtn} onClick={() => handleAdd(true)} title="Add complex dish (menemen, omlet…)">＋ Dish</button>
          </>
        ) : (
          <button style={s.addBtn} onClick={() => handleAdd(false)}>+</button>
        )}
      </div>

      <div style={s.actions}>
        <button style={s.closeBtn} onClick={onClose}>Close</button>
        {extraActions}
        <button style={s.saveBtn} onClick={handleSave}>Save</button>
      </div>
    </div>
  )
}

// ── Helpers ────────────────────────────────────────────────────────────────

function initItems(meal, menuMode) {
  if (menuMode) {
    return (meal?.menu || []).map(item => ({ ...item }))
  }
  return (meal?.ingredients || []).map(normalizeItem)
}

/**
 * Simple menu items are served as-is (peynir, zeytin, meyve) — they have a top-level amount.
 * Dish items (menemen, omlet) have no top-level amount and carry sub-ingredients.
 */
function isSimpleItem(item) {
  return item.amount != null
}
