import { useState, useEffect } from 'react'
import { Trash2, ShoppingCart, X, Plus } from 'lucide-react'
import { getShoppingList, addShoppingItem, deleteShoppingItem, buyShoppingItems } from '../services/api'
import * as s from './ShoppingListPanel.styles'

export default function ShoppingListPanel({ open, onClose, onBought }) {
  const [items, setItems] = useState([])
  const [checked, setChecked] = useState({})
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
    setChecked(prev => ({ ...prev, [id]: !prev[id] }))
  }

  const handleBought = async () => {
    const selectedIds = Object.entries(checked)
      .filter(([, v]) => v)
      .map(([id]) => Number(id))
    if (selectedIds.length === 0) return
    try {
      setError(null)
      await buyShoppingItems(selectedIds)
      setChecked({})
      load()
      onBought?.()
    } catch {
      setError('Failed to process bought items')
    }
  }

  const checkedCount = Object.values(checked).filter(Boolean).length

  if (!open) return null

  return (
    <div style={s.overlay}>
      <div style={s.panel}>
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
            <label key={item.id} style={s.row}>
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

        {/* Bought button */}
        {items.length > 0 && (
          <button
            style={{
              ...s.boughtBtn,
              opacity: checkedCount === 0 ? 0.4 : 1,
              cursor: checkedCount === 0 ? 'default' : 'pointer',
            }}
            onClick={handleBought}
            disabled={checkedCount === 0}
          >
            Bought{checkedCount > 0 ? ` (${checkedCount})` : ''}
          </button>
        )}
      </div>
    </div>
  )
}
