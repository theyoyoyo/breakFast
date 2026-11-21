import { useState, useEffect } from 'react'
import { Trash2, ShoppingCart, X, Plus, CheckSquare, Square } from 'lucide-react'
import { getShoppingList, addShoppingItem, deleteShoppingItem, buyShoppingItems, clearShoppingList } from '../services/api'
import ConfirmPrompt from './ConfirmPrompt'
import * as s from './ShoppingListPanel.styles'

export default function ShoppingListPanel({ open, onClose, onBought }) {
  const [items, setItems] = useState([])
  const [checked, setChecked] = useState({})
  const [expiryDates, setExpiryDates] = useState({}) // { itemId: 'YYYY-MM-DD' }
  const [newItem, setNewItem] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [askClearAll, setAskClearAll] = useState(false) // Delete all's "Are you sure?"

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
      setAskClearAll(false)
      load()
    }
  }, [open])

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

  // Header helpers, like the Fridge's suggestions list: check or uncheck every item, and delete them
  // all after an "Are you sure?" (the list is typed in by hand)
  const allChecked = items.length > 0 && items.every(i => checked[i.id])

  const toggleAll = () => {
    setChecked(allChecked ? {} : Object.fromEntries(items.map(i => [i.id, true])))
    if (allChecked) setExpiryDates({})
  }

  const handleClearAll = async () => {
    setAskClearAll(false)
    setItems([])
    setChecked({})
    setExpiryDates({})
    try {
      await clearShoppingList()
    } catch {
      setError('Failed to delete the list')
      load()
    }
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
          {items.length > 0 && (
            <span style={s.headerHelpers}>
              <button
                style={s.helperBtn}
                onClick={toggleAll}
                title={allChecked ? 'Unselect all' : 'Select all'}
                aria-label={allChecked ? 'Unselect all' : 'Select all'}
              >
                {allChecked ? <Square size={13} /> : <CheckSquare size={13} />}
              </button>
              <button style={s.clearAllBtn} onClick={() => setAskClearAll(true)} title="Delete all" aria-label="Delete all">
                <Trash2 size={13} />
              </button>
            </span>
          )}
          <button style={s.closeBtn} onClick={onClose} aria-label="Close"><X size={16} /></button>
        </div>

        <div style={s.list}>
          {error && <div style={s.error}>{error}</div>}
          {askClearAll && items.length > 0 && (
            <div style={s.confirm}>
              <ConfirmPrompt
                label="Delete the shopping list"
                message={`Are you sure you want to delete all ${items.length} ${items.length === 1 ? 'item' : 'items'} from your shopping list?`}
                confirmLabel="Delete"
                danger
                onConfirm={handleClearAll}
                onCancel={() => setAskClearAll(false)}
              />
            </div>
          )}
          {loading && <div style={s.empty}>Loading…</div>}
          {!loading && items.length === 0 && (
            <div style={s.empty}>Shopping list is empty</div>
          )}
          {/* A checked item gets its best before date on the same row; × removes an item (not bought
              yet, so no trash can) */}
          {items.map(item => (
            <div key={item.id} style={s.row}>
              <label style={s.rowLabel}>
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
              </label>
              {checked[item.id] && (
                <label style={s.bbd}>
                  <span style={s.bbdLabel}>BBD:</span>
                  <input
                    type="date"
                    style={s.bbdInput}
                    value={expiryDates[item.id] || ''}
                    onChange={(e) => setExpiryDate(item.id, e.target.value)}
                    aria-label={`Best before date for ${item.item_name}`}
                  />
                </label>
              )}
              <button
                style={s.removeBtn}
                onClick={() => handleDelete(item.id)}
                title="Remove"
                aria-label={`Remove ${item.item_name}`}
              >×</button>
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
