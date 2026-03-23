import { useState } from 'react'
import * as s from './MealBlock.styles'

/**
 * Normalize an ingredient to structured form {name, quantity, unit}.
 */
function normalizeItem(item) {
  if (typeof item === 'object' && item !== null && item.name) {
    return { name: item.name, quantity: item.quantity ?? 1, unit: item.unit || 'adet' }
  }
  return { name: String(item), quantity: 1, unit: 'adet' }
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
 * Click opens an editable overlay panel.
 */
export default function MealBlock({ meal, checked, onCheck, onSave, onAnalyze, analyzing }) {
  const [panelOpen, setPanelOpen] = useState(false)
  const [items, setItems] = useState(() => (meal?.ingredients || []).map(normalizeItem))
  const [newItem, setNewItem] = useState('')
  const displayNames = items.length > 0
    ? items.map(formatIngredient).join(', ')
    : meal?.meal_name || 'Meal'

  const handleOverlayClick = (e) => {
    if (e.target === e.currentTarget) setPanelOpen(false)
  }

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

  const handleSave = () => {
    const finalItems = items.map(item => ({
      ...item,
      quantity: (() => {
        const num = parseFloat(item.quantity)
        return (!isNaN(num) && num > 0) ? Math.round(num * 100) / 100 : 1
      })(),
    }))
    const updated = {
      ...meal,
      ingredients: finalItems,
    }
    onSave?.(updated)
    setPanelOpen(false)
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
        <div style={s.block} onClick={() => setPanelOpen(true)}>
          <span style={s.blockIcon}>🍳</span>
          <span style={s.blockText}>{displayNames}</span>
          {meal?.prep_time_min && <span style={s.prepBadge}>⏱ {meal.prep_time_min}m</span>}
          <span style={s.mealId}>#{meal?.id || 0}</span>
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
            <div style={s.panelHeader}>
              {meal?.meal_name || 'Meal'}
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
              <button style={s.cancelBtn} onClick={() => setPanelOpen(false)}>Close</button>
              <button style={s.saveBtn} onClick={handleSave}>Save</button>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
