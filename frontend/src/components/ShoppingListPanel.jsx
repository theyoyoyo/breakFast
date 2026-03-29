import { useState, useEffect } from 'react'
import { Trash2, ShoppingCart, X, Plus } from 'lucide-react'
import { getShoppingList, addShoppingItem, deleteShoppingItem, buyShoppingItems } from '../services/api'
import * as s from './ShoppingListPanel.styles'

export default function ShoppingListPanel({ open, onClose, onBought }) {
  const [items, setItems] = useState([])
  const [checked, setChecked] = useState({})
  const [expiryDates, setExpiryDates] = useState({}) // { itemId: 'YYYY-MM-DD' }
  const [newItem, setNewItem] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const load = async () => {
    try {
      setLoading(true)
      setError(null)
      const data = await getShoppingList()
      setItems(data)
    } catch {
      setError('Could not reach server')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (open) {
      setError(null)
      setChecked({})
      setExpiryDates({})
      load()
    }
  }, [open]) // eslint-disable-line react-hooks/exhaustive-deps

  const handleAdd = async () => {
    const name = newItem.trim()
    if (!name) return
    try {
      setError(null)
      await addShoppingItem(name)
      setNewItem('')
      load()
    } catch {
      setError('Could not add item — check server connection')
    }
  }

  const handleDelete = async (id) => {
    setItems(prev => prev.filter(i => i.id !== id))
    try {
      await deleteShoppingItem(id)
    } catch {
      setError('Failed to delete item')
      load()
    }
  }

  const toggleCheck = (id) => {
    const newChecked = { ...checked, [id]: !checked[id] }
    setChecked(newChecked)
    // Clear expiry date if unchecked
    if (!newChecked[id]) {
      setExpiryDates(prev => {
        const next = { ...prev }
        delete next[id]
        return next
      })
    }
  }

  const setExpiryDate = (id, date) => {
    setExpiryDates(prev => ({ ...prev, [id]: date }))
  }

  const handleBought = async () => {
    const selectedIds = Object.entries(checked)
      .filter(([, v]) => v)
      .map(([id]) => Number(id))
    if (selectedIds.length === 0) { onClose?.(); return }

    // Build expiry_dates mapping: { item_name: date }
    const dateMap = {}
    for (const id of selectedIds) {
      const item = items.find(i => i.id === id)
      const date = expiryDates[id]
      if (item && date) {
        dateMap[item.item_name] = date
      }
    }

    try {
      setError(null)
      await buyShoppingItems(selectedIds, Object.keys(dateMap).length > 0 ? dateMap : null)
      setChecked({})
      setExpiryDates({})
      onBought?.()
      onClose?.()
    } catch {
      setError('Failed to process bought items')
    }
  }

  const checkedCount = Object.values(checked).filter(Boolean).length

  if (!open) return null

  return (
    <div style={s.overlay} onClick={onClose}>
      <div style={s.panel} onClick={(e) => e.stopPropagation()}>
        <div style={s.header}>
          <ShoppingCart size={16} />
          <span style={s.title}>Shopping List</span>
          <button style={s.closeBtn} onClick={onClose}><X size={16} /></button>
        </div>

        <div style={s.list}>
          {error && <div style={s.error}>{error}</div>}
          {loading && <div style={s.empty}>Loading…</div>}
          {!loading && items.length === 0 && (
            <div style={s.empty}>Shopping list is empty</div>
          )}
          {items.map(item => (
            <div key={item.id}>
              <label style={s.row}>
                <input
                  type="checkbox"
                  checked={!!checked[item.id]}
                  onChange={() => toggleCheck(item.id)}
                  style={s.checkbox}
                />
                <span style={{
                  ...s.itemName,
                  textDecoration: checked[item.id] ? 'line-through' : 'none',
                  opacity: checked[item.id] ? 0.5 : 1,
                }}>{item.item_name}</span>
                <button style={s.deleteBtn} onClick={(e) => { e.preventDefault(); handleDelete(item.id) }}>
                  <Trash2 size={12} />
                </button>
              </label>
              {checked[item.id] && (
                <div style={s.expiryDateRow}>
                  <span style={s.expiryDateLabel}>Expiry:</span>
                  <input
                    type="date"
                    style={s.expiryDateInput}
                    value={expiryDates[item.id] || ''}
                    onChange={(e) => setExpiryDate(item.id, e.target.value)}
                    onClick={(e) => e.stopPropagation()}
                  />
                </div>
              )}
            </div>
          ))}
        </div>

        {/* Add item row */}
        <div style={s.addRow}>
          <input
            style={s.addInput}
            value={newItem}
            onChange={(e) => setNewItem(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleAdd()}
            placeholder="Add item…"
          />
          <button style={s.addBtn} onClick={handleAdd}><Plus size={14} /></button>
        </div>

        {/* Done button — buys checked items or closes panel */}
        {items.length > 0 && (
          <button
            style={{ ...s.doneBtn, cursor: 'pointer' }}
            onClick={handleBought}
          >
            Done{checkedCount > 0 ? ` (${checkedCount})` : ''} ✓
          </button>
        )}
      </div>
    </div>
  )
}
