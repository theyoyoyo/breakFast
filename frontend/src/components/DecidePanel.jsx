import { useState, useEffect, useCallback } from 'react'
import { getRatings, createRating, logMeal } from '../services/api'
import * as s from './DecidePanel.styles'

export default function DecidePanel({ meal, onClose, onConfirm }) {
  // Phase: 'edit' = editing ingredients, 'rate' = rating products
  const [phase, setPhase] = useState('edit')
  const [items, setItems] = useState([])
  const [newItem, setNewItem] = useState('')
  const [editIdx, setEditIdx] = useState(null)
  const [editValue, setEditValue] = useState('')
  const [ratings, setRatings] = useState({})
  const [existingRatings, setExistingRatings] = useState([])
  const [saving, setSaving] = useState(false)

  // Initialize items from meal ingredients
  useEffect(() => {
    if (meal?.ingredients) {
      setItems([...meal.ingredients])
    } else {
      setItems([])
    }
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

  const handleStartEdit = (idx) => {
    setEditIdx(idx)
    setEditValue(items[idx])
  }

  const handleSaveEdit = () => {
    if (editValue.trim() && editIdx !== null) {
      setItems(prev => prev.map((item, i) => i === editIdx ? editValue.trim() : item))
    }
    setEditIdx(null)
    setEditValue('')
  }

  const handleAdd = () => {
    const v = newItem.trim()
    if (!v) return
    setItems(prev => [...prev, v])
    setNewItem('')
  }

  const handleProceedToRating = useCallback(() => {
    if (items.length === 0) return
    // Find items not already rated
    const ratedNames = new Set(existingRatings.map(r => r.product_name.toLowerCase()))
    const unrated = items.filter(item => !ratedNames.has(item.toLowerCase()))
    if (unrated.length === 0) {
      // All already rated, skip to save
      handleSave()
      return
    }
    // Pre-fill default rating of 10
    const defaultRatings = {}
    unrated.forEach(item => { defaultRatings[item] = 10 })
    setRatings(defaultRatings)
    setPhase('rate')
  }, [items, existingRatings])

  const handleSave = useCallback(async () => {
    setSaving(true)
    try {
      // Save ratings for new products
      for (const [name, rating] of Object.entries(ratings)) {
        try {
          await createRating(name, rating)
        } catch { /* Already rated or error — skip */ }
      }
      // Log meal
      await logMeal({
        meal_name: meal?.meal_name || 'Kahvaltı',
        description: meal?.description || '',
        ingredients: items,
        steps: meal?.steps || [],
        prep_time_min: meal?.prep_time_min || null,
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
          <div style={s.panelHeader}>Puanla</div>
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
            <button style={s.backBtn} onClick={() => setPhase('edit')}>Geri</button>
            <button style={s.confirmBtn} onClick={handleSave} disabled={saving}>
              {saving ? '...' : 'Kaydet'}
            </button>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div style={s.overlay} onClick={handleOverlayClick}>
      <div style={s.panel}>
        <div style={s.panelHeader}>Karar Verdim</div>
        <div style={s.itemList}>
          {items.map((item, idx) => (
            <div key={idx} style={s.itemRow}>
              {editIdx === idx ? (
                <input
                  style={s.editInput}
                  value={editValue}
                  onChange={(e) => setEditValue(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleSaveEdit()}
                  onBlur={handleSaveEdit}
                  autoFocus
                />
              ) : (
                <span style={s.itemText}>{item}</span>
              )}
              <div style={s.itemActions}>
                <button style={s.editBtn} onClick={() => handleStartEdit(idx)} title="Düzenle">✏️</button>
                <button style={s.deleteBtn} onClick={() => handleDelete(idx)} title="Sil">🗑️</button>
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
            placeholder="Ürün ekle…"
          />
          <button style={s.addBtn} onClick={handleAdd}>+</button>
        </div>
        <div style={s.actions}>
          <button style={s.cancelBtn} onClick={onClose}>Kapat</button>
          <button
            style={s.confirmBtn}
            onClick={handleProceedToRating}
            disabled={items.length === 0}
          >
            Onayla
          </button>
        </div>
      </div>
    </div>
  )
}
