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
  const [items, setItems] = useState(() => initItems(meal, menuMode))
  const [mealName, setMealName] = useState(meal?.meal_name || meal?.menu_name || 'Meal')
  const [prepTime, setPrepTime] = useState(meal?.prep_time_min ?? '')
  const [newItem, setNewItem] = useState('')
  // Which dish row has its sub-ingredient dropdown open (index or null)
  const [openDishIdx, setOpenDishIdx] = useState(null)
  // Input value for the sub-ingredient add field (shared — only one open at a time)
  const [newSubItem, setNewSubItem] = useState('')

  useEffect(() => {
    setItems(initItems(meal, menuMode))
    setMealName(meal?.meal_name || meal?.menu_name || 'Meal')
    setPrepTime(meal?.prep_time_min ?? '')
    setNewItem('')
    setOpenDishIdx(null)
    setNewSubItem('')
  }, [meal, menuMode])

  // ── Top-level item handlers ──────────────────────────────────────────────

  const handleDelete = (idx) => {
    if (openDishIdx === idx) setOpenDishIdx(null)
    else if (openDishIdx !== null && openDishIdx > idx) setOpenDishIdx(i => i - 1)
    setItems(prev => prev.filter((_, i) => i !== idx))
  }

  const handleQtyChange = (idx, val) => {
    if (val !== '' && !/^\d*\.?\d{0,2}$/.test(val)) return
    const key = menuMode ? 'amount' : 'quantity'
    setItems(prev => prev.map((item, i) =>
      i === idx ? { ...item, [key]: val === '' ? '' : val } : item
    ))
  }

  const handleQtyBlur = (idx) => {
    const key = menuMode ? 'amount' : 'quantity'
    setItems(prev => prev.map((item, i) => {
      if (i !== idx) return item
      const num = parseFloat(item[key])
      return { ...item, [key]: (!isNaN(num) && num > 0) ? Math.round(num * 100) / 100 : 1 }
    }))
  }

  const handleQtyStep = (idx, delta) => {
    const key = menuMode ? 'amount' : 'quantity'
    setItems(prev => prev.map((item, i) => {
      if (i !== idx) return item
      const cur = typeof item[key] === 'number' ? item[key] : parseFloat(item[key]) || 1
      const next = Math.round((cur + delta) * 100) / 100
      return { ...item, [key]: next > 0 ? next : cur }
    }))
  }

  const handleAdd = (isDish = false) => {
    const v = newItem.trim()
    if (!v) return
    if (items.some(item => item.name.toLowerCase() === v.toLowerCase())) return
    const entry = menuMode
      ? (isDish
        ? { name: v, ingredients: [] }
        : { name: v, amount: 1, unit: 'adet', ingredients: [] })
      : { name: v, quantity: 1, unit: 'adet' }
    setItems(prev => [...prev, entry])
    setNewItem('')
  }

  // ── Dish toggle ──────────────────────────────────────────────────────────

  const toggleDish = (idx) => {
    setOpenDishIdx(prev => prev === idx ? null : idx)
    setNewSubItem('')
  }

  // ── Sub-ingredient handlers ──────────────────────────────────────────────

  const updateSubs = (dishIdx, fn) =>
    setItems(prev => prev.map((item, i) =>
      i === dishIdx ? { ...item, ingredients: fn(item.ingredients || []) } : item
    ))

  const handleSubDelete = (dishIdx, subIdx) =>
    updateSubs(dishIdx, subs => subs.filter((_, i) => i !== subIdx))

  const handleSubQtyChange = (dishIdx, subIdx, val) => {
    if (val !== '' && !/^\d*\.?\d{0,2}$/.test(val)) return
    updateSubs(dishIdx, subs => subs.map((s, i) =>
      i === subIdx ? { ...s, amount: val === '' ? '' : val } : s
    ))
  }

  const handleSubQtyBlur = (dishIdx, subIdx) =>
    updateSubs(dishIdx, subs => subs.map((s, i) => {
      if (i !== subIdx) return s
      const num = parseFloat(s.amount)
      return { ...s, amount: (!isNaN(num) && num > 0) ? Math.round(num * 100) / 100 : 1 }
    }))

  const handleSubQtyStep = (dishIdx, subIdx, delta) =>
    updateSubs(dishIdx, subs => subs.map((s, i) => {
      if (i !== subIdx) return s
      const cur = typeof s.amount === 'number' ? s.amount : parseFloat(s.amount) || 1
      const next = Math.round((cur + delta) * 100) / 100
      return { ...s, amount: next > 0 ? next : cur }
    }))

  const handleSubAdd = (dishIdx) => {
    const v = newSubItem.trim()
    if (!v) return
    updateSubs(dishIdx, subs => {
      if (subs.some(s => s.name.toLowerCase() === v.toLowerCase())) return subs
      return [...subs, { name: v, amount: 1, unit: 'adet' }]
    })
    setNewSubItem('')
  }

  // ── Prep time ────────────────────────────────────────────────────────────

  const handlePrepTimeChange = (val) => {
    if (val === '') { setPrepTime(''); return }
    const num = parseInt(val, 10)
    if (!isNaN(num) && num >= 0 && num <= 999) setPrepTime(num)
  }

  // ── Save ─────────────────────────────────────────────────────────────────

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

  // ── Render ───────────────────────────────────────────────────────────────

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
        {items.map((item, idx) => {
          const isDish = menuMode && !isSimpleItem(item)
          const isOpen = openDishIdx === idx

          return (
            <div key={idx}>
              {isDish ? (
                // ── Dish row ──────────────────────────────────────────────
                <div style={s.itemRow}>
                  <span style={s.dishBadge}>🍳</span>
                  <span style={{ ...s.itemText, fontWeight: 500 }}>{item.name}</span>
                  <div style={s.itemActions}>
                    <button
                      style={s.expandBtn(isOpen)}
                      onClick={() => toggleDish(idx)}
                      title={isOpen ? 'Close ingredients' : 'Edit ingredients'}
                    >
                      {isOpen ? '▲' : '▶'}
                    </button>
                    <button style={s.deleteBtn} onClick={() => handleDelete(idx)} title="Delete">🗑️</button>
                  </div>
                </div>
              ) : (
                // ── Simple item row ───────────────────────────────────────
                <div style={s.itemRow}>
                  <div style={s.qtyGroup}>
                    <button style={s.arrowBtn} onClick={() => handleQtyStep(idx, -1)}>▼</button>
                    <input
                      style={s.qtyInput}
                      type="text"
                      inputMode="decimal"
                      value={menuMode ? (item.amount ?? 1) : item.quantity}
                      onChange={(e) => handleQtyChange(idx, e.target.value)}
                      onBlur={() => handleQtyBlur(idx)}
                    />
                    <button style={s.arrowBtn} onClick={() => handleQtyStep(idx, 1)}>▲</button>
                  </div>
                  <span style={s.unitLabel}>{item.unit}</span>
                  <span style={s.itemText}>{item.name}</span>
                  <div style={s.itemActions}>
                    <button style={s.deleteBtn} onClick={() => handleDelete(idx)} title="Delete">🗑️</button>
                  </div>
                </div>
              )}

              {/* ── Sub-ingredient dropdown (dish only) ─────────────────── */}
              {isDish && isOpen && (
                <div style={s.subList}>
                  {(item.ingredients || []).map((sub, si) => (
                    <div key={si} style={s.subRow}>
                      <div style={s.qtyGroup}>
                        <button style={s.arrowBtn} onClick={() => handleSubQtyStep(idx, si, -1)}>▼</button>
                        <input
                          style={s.qtyInput}
                          type="text"
                          inputMode="decimal"
                          value={sub.amount ?? 1}
                          onChange={(e) => handleSubQtyChange(idx, si, e.target.value)}
                          onBlur={() => handleSubQtyBlur(idx, si)}
                        />
                        <button style={s.arrowBtn} onClick={() => handleSubQtyStep(idx, si, 1)}>▲</button>
                      </div>
                      <span style={s.unitLabel}>{sub.unit || 'adet'}</span>
                      <span style={s.itemText}>{sub.name}</span>
                      <div style={s.itemActions}>
                        <button style={s.deleteBtn} onClick={() => handleSubDelete(idx, si)} title="Delete">🗑️</button>
                      </div>
                    </div>
                  ))}
                  {/* Always-visible add field at the bottom of the dropdown */}
                  <div style={s.subAddRow}>
                    <input
                      style={s.addInput}
                      value={newSubItem}
                      onChange={(e) => setNewSubItem(e.target.value)}
                      onKeyDown={(e) => e.key === 'Enter' && handleSubAdd(idx)}
                      placeholder="Add ingredient…"
                      autoFocus
                    />
                    <button style={s.addBtn} onClick={() => handleSubAdd(idx)}>＋ Item</button>
                  </div>
                </div>
              )}
            </div>
          )
        })}
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
    return (meal?.menu || []).map(item => ({
      ...item,
      ingredients: (item.ingredients || []).map(s => ({ ...s })),
    }))
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
