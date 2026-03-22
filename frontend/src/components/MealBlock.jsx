import { useState } from 'react'
import * as s from './MealBlock.styles'

/**
 * Clickable meal summary block rendered inline in chat.
 * Shows checkbox, meal names, prep time, and analysis button.
 * Click opens an editable overlay panel.
 */
export default function MealBlock({ meal, checked, onCheck, onSave, onAnalyze, analyzing }) {
  const [panelOpen, setPanelOpen] = useState(false)
  const [items, setItems] = useState(meal?.ingredients || [])
  const [newItem, setNewItem] = useState('')
  const [editIdx, setEditIdx] = useState(null)
  const [editValue, setEditValue] = useState('')
  const displayNames = items.length > 0
    ? items.join(', ')
    : meal?.meal_name || 'Meal'

  const handleOverlayClick = (e) => {
    if (e.target === e.currentTarget) setPanelOpen(false)
  }

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
    if (items.some(item => item.toLowerCase() === v.toLowerCase())) return
    setItems(prev => [...prev, v])
    setNewItem('')
  }

  const handleSave = () => {
    const updated = {
      ...meal,
      ingredients: items,
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
                    <button style={s.editBtn} onClick={() => handleStartEdit(idx)} title="Edit">✏️</button>
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
