import { useState, useEffect } from 'react'
import { normalizeItem } from '../utils/ingredients'
import * as s from './MealEditor.styles'

/**
 * Shared meal editor component used by MealBlock, FavoritesPanel, and SettingsPanel.
 *
 * Props:
 *   meal         — meal object { meal_name, ingredients, steps, prep_time_min, ... }
 *   onSave       — (updatedMeal) => void — called with the edited meal
 *   onClose      — () => void — close the editor
 *   showPrepTime — boolean — whether to show prep_time_min input (default true)
 *   editPrepTime — boolean — whether prep time is editable (default true)
 *   extraActions — ReactNode — extra buttons to render in the actions row
 *   title        — optional header text (defaults to editable name input)
 *   showId       — boolean — show meal ID badge (default false)
 */
export default function MealEditor({
  meal,
  onSave,
  onClose,
  showPrepTime = true,
  editPrepTime = true,
  extraActions,
  showId = false,
}) {
  const [items, setItems] = useState(() => (meal?.ingredients || []).map(normalizeItem))
  const [mealName, setMealName] = useState(meal?.meal_name || 'Meal')
  const [prepTime, setPrepTime] = useState(meal?.prep_time_min ?? '')
  const [newItem, setNewItem] = useState('')

  // Sync when meal prop changes (e.g. expanding a different favorite)
  useEffect(() => {
    setItems((meal?.ingredients || []).map(normalizeItem))
    setMealName(meal?.meal_name || 'Meal')
    setPrepTime(meal?.prep_time_min ?? '')
    setNewItem('')
  }, [meal])

  const handleDelete = (idx) => {
    setItems(prev => prev.filter((_, i) => i !== idx))
  }

  const handleQuantityChange = (idx, val) => {
    if (val !== '' && !/^\d*\.?\d{0,2}$/.test(val)) return
    setItems(prev => prev.map((item, i) =>
      i === idx ? { ...item, quantity: val === '' ? '' : val } : item
    ))
  }

  const handleQuantityBlur = (idx) => {
    setItems(prev => prev.map((item, i) => {
      if (i !== idx) return item
      const num = parseFloat(item.quantity)
      return { ...item, quantity: (!isNaN(num) && num > 0) ? Math.round(num * 100) / 100 : 1 }
    }))
  }

  const handleQuantityStep = (idx, delta) => {
    setItems(prev => prev.map((item, i) => {
      if (i !== idx) return item
      const current = typeof item.quantity === 'number' ? item.quantity : parseFloat(item.quantity) || 1
      const next = Math.round((current + delta) * 100) / 100
      return { ...item, quantity: next > 0 ? next : current }
    }))
  }

  const handleAdd = () => {
    const v = newItem.trim()
    if (!v) return
    if (items.some(item => item.name.toLowerCase() === v.toLowerCase())) return
    setItems(prev => [...prev, { name: v, quantity: 1, unit: 'adet' }])
    setNewItem('')
  }

  const handlePrepTimeChange = (val) => {
    if (val === '') { setPrepTime(''); return }
    const num = parseInt(val, 10)
    if (!isNaN(num) && num >= 0 && num <= 999) setPrepTime(num)
  }

  const handleSave = () => {
    const finalItems = items.map(item => ({
      ...item,
      quantity: (() => {
        const num = parseFloat(item.quantity)
        return (!isNaN(num) && num > 0) ? Math.round(num * 100) / 100 : 1
      })(),
    }))
    const finalPrepTime = typeof prepTime === 'number' ? prepTime : (parseInt(prepTime, 10) || null)
    const updated = {
      ...meal,
      meal_name: mealName.trim() || meal?.meal_name || 'Meal',
      ingredients: finalItems,
      prep_time_min: finalPrepTime,
    }
    onSave?.(updated)
  }

  return (
    <div style={s.editorContainer}>
      <div style={s.editorHeader}>
        <input
          style={s.nameInput}
          value={mealName}
          onChange={(e) => { if (e.target.value.length <= 100) setMealName(e.target.value) }}
          onBlur={() => { if (!mealName.trim()) setMealName(meal?.meal_name || 'Meal') }}
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
          <div key={idx} style={s.itemRow}>
            <div style={s.qtyGroup}>
              <button style={s.arrowBtn} onClick={() => handleQuantityStep(idx, -1)}>▼</button>
              <input
                style={s.qtyInput}
                type="text"
                inputMode="decimal"
                value={item.quantity}
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
        ))}
      </div>

      <div style={s.addRow}>
        <input
          style={s.addInput}
          value={newItem}
          onChange={(e) => setNewItem(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleAdd()}
          placeholder="Add item…"
        />
        <button style={s.addBtn} onClick={handleAdd}>+</button>
      </div>

      <div style={s.actions}>
        <button style={s.closeBtn} onClick={onClose}>Close</button>
        {extraActions}
        <button style={s.saveBtn} onClick={handleSave}>Save</button>
      </div>
    </div>
  )
}
