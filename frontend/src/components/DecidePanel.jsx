import { useState, useEffect, useCallback } from 'react'
import { getRatings, createRating, logMeal } from '../services/api'
import * as s from './DecidePanel.styles'

/**
 * Get the display name of an ingredient (works for both string and structured forms).
 */
function getName(item) {
  if (typeof item === 'object' && item !== null) return item.name || ''
  return String(item)
}

/**
 * Clamp a quantity string to max 2 decimal places and return as number.
 * Returns null if the input is empty or invalid.
 */
function parseQuantity(val) {
  if (val === '' || val === null || val === undefined) return null
  const num = parseFloat(val)
  if (isNaN(num)) return null
  return Math.round(num * 100) / 100
}

export default function DecidePanel({ meal, onClose, onConfirm }) {
  // Phase: 'edit' = editing ingredients, 'rate' = rating products
  const [phase, setPhase] = useState('edit')
  const [items, setItems] = useState([])
  const [prepTime, setPrepTime] = useState('')
  const [newItem, setNewItem] = useState('')
  const [ratings, setRatings] = useState({})
  const [existingRatings, setExistingRatings] = useState([])
  const [saving, setSaving] = useState(false)

  // Initialize items from meal ingredients — normalize to structured form
  useEffect(() => {
    if (meal?.ingredients) {
      const normalized = meal.ingredients.map(item => {
        if (typeof item === 'object' && item !== null && item.name) {
          return { name: item.name, quantity: item.quantity ?? 1, unit: item.unit || 'adet' }
        }
        return { name: String(item), quantity: 1, unit: 'adet' }
      })
      setItems(normalized)
    } else {
      setItems([])
    }
    setPrepTime(meal?.prep_time_min ?? '')
    setPhase('edit')
    setRatings({})
  }, [meal])

  // Load existing ratings to skip already-rated products
  useEffect(() => {
    getRatings()
      .then(setExistingRatings)
      .catch(() => setExistingRatings([]))
  }, [])

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
      const parsed = parseQuantity(item.quantity)
      return { ...item, quantity: parsed !== null ? parsed : 1 }
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

  const handleProceedToRating = useCallback(() => {
    if (items.length === 0) return
    const ratedNames = new Set(existingRatings.map(r => r.product_name.toLowerCase()))
    const unrated = items.filter(item => !ratedNames.has(item.name.toLowerCase()))
    if (unrated.length === 0) {
      handleSave()
      return
    }
    const defaultRatings = {}
    unrated.forEach(item => { defaultRatings[item.name] = 10 })
    setRatings(defaultRatings)
    setPhase('rate')
  }, [items, existingRatings])

  const handleSave = useCallback(async () => {
    setSaving(true)
    try {
      for (const [name, rating] of Object.entries(ratings)) {
        try {
          await createRating(name, rating)
        } catch { /* Already rated or error — skip */ }
      }
      // Finalize quantities before saving
      const finalItems = items.map(item => ({
        ...item,
        quantity: parseQuantity(item.quantity) ?? 1,
      }))
      const finalPrepTime = typeof prepTime === 'number' ? prepTime : (parseInt(prepTime, 10) || null)
      await logMeal({
        meal_name: meal?.meal_name || 'Kahvaltı',
        description: meal?.description || '',
        ingredients: finalItems,
        steps: meal?.steps || [],
        prep_time_min: finalPrepTime,
        nutrition_note: meal?.nutrition_note || '',
      })
      onConfirm?.()
    } catch { /* Error saving */ }
    setSaving(false)
  }, [ratings, items, meal, onConfirm])

  const handleOverlayClick = (e) => {
    if (e.target === e.currentTarget) onClose()
  }

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
                <div style={s.starsRow}>
                  {Array.from({ length: 10 }, (_, i) => i + 1).map(n => (
                    <div
                      key={n}
                      style={s.starCell}
                      onClick={() => setRatings(prev => ({ ...prev, [item]: n }))}
                    >
                      <span style={s.starNum}>{n}</span>
                      <span style={s.star(n <= ratings[item])}>★</span>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
          <div style={s.actions}>
            <button style={s.backBtn} onClick={() => setPhase('edit')}>Back</button>
            <button style={s.confirmBtn} onClick={handleSave} disabled={saving}>
              {saving ? '...' : 'Save'}
            </button>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div style={s.overlay} onClick={handleOverlayClick}>
      <div style={s.panel}>
        <div style={s.panelHeader}>Today I ate...</div>
        <div style={s.prepTimeRow}>
          <span style={s.prepTimeLabel}>⏱</span>
          <input
            style={s.prepTimeInput}
            type="text"
            inputMode="numeric"
            value={prepTime}
            onChange={(e) => {
              const v = e.target.value
              if (v === '') { setPrepTime(''); return }
              const n = parseInt(v, 10)
              if (!isNaN(n) && n >= 0 && n <= 999) setPrepTime(n)
            }}
            placeholder="—"
          />
          <span style={s.prepTimeUnit}>min</span>
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
          <button style={s.cancelBtn} onClick={onClose}>Close</button>
          <button
            style={s.confirmBtn}
            onClick={handleProceedToRating}
            disabled={items.length === 0}
          >
            Confirm
          </button>
        </div>
      </div>
    </div>
  )
}
