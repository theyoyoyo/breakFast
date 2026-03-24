import { useState, useEffect, useCallback, useImperativeHandle, forwardRef } from 'react'
import { Trash2, Pencil, Plus, X, AlertTriangle } from 'lucide-react'
import { getIngredients, addIngredient, updateIngredient, deleteIngredient, getExpiredIngredients, confirmExpiredThrown } from '../services/api'
import * as s from './IngredientPanel.styles'

const IngredientPanel = forwardRef(function IngredientPanel({ refreshTrigger }, ref) {
  const [ingredients, setIngredients] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  // Add panel state
  const [addPanelOpen, setAddPanelOpen] = useState(false)
  const [newName, setNewName] = useState('')
  const [newExpiry, setNewExpiry] = useState('')

  // Edit state
  const [editingId, setEditingId] = useState(null)
  const [editName, setEditName] = useState('')
  const [editExpiry, setEditExpiry] = useState('')

  // Expiry state
  const [expiredItems, setExpiredItems] = useState([])
  const [expiryPanelOpen, setExpiryPanelOpen] = useState(false)
  const [expiryChecked, setExpiryChecked] = useState({})

  const load = async () => {
    try {
      setError(null)
      const data = await getIngredients()
      setIngredients(data)
    } catch (e) {
      setError('Failed to load ingredients')
    } finally {
      setLoading(false)
    }
  }

  const checkExpired = useCallback(async () => {
    try {
      const expired = await getExpiredIngredients()
      if (expired.length > 0) {
        setExpiredItems(expired)
        // All checked by default
        const checked = {}
        expired.forEach(i => { checked[i.id] = true })
        setExpiryChecked(checked)
      }
    } catch {
      // silently ignore expiry check errors
    }
  }, [])

  useEffect(() => { load(); checkExpired() }, [refreshTrigger]) // eslint-disable-line react-hooks/exhaustive-deps

  // Expose injectDemoExpiry for the demo username click
  useImperativeHandle(ref, () => ({
    injectDemoExpiry: () => {
      const fakeExpired = [
        { id: -1, name: 'Yogurt (demo)', expiry_date: new Date().toISOString().split('T')[0], added_at: '', updated_at: '' },
        { id: -2, name: 'Milk (demo)', expiry_date: new Date().toISOString().split('T')[0], added_at: '', updated_at: '' },
      ]
      setExpiredItems(fakeExpired)
      const checked = {}
      fakeExpired.forEach(i => { checked[i.id] = true })
      setExpiryChecked(checked)
    }
  }))

  const handleAdd = async () => {
    const name = newName.trim()
    if (!name) return
    try {
      setError(null)
      await addIngredient(name, newExpiry || null)
      setNewName('')
      setNewExpiry('')
      setAddPanelOpen(false)
      load()
    } catch (e) {
      setError('Failed to add ingredient')
    }
  }

  const handleDelete = async (id) => {
    setIngredients((prev) => prev.filter((i) => i.id !== id))
    try {
      await deleteIngredient(id)
    } catch (e) {
      setError('Failed to delete ingredient')
      load()
    }
  }

  const startEdit = (ing) => {
    setEditingId(ing.id)
    setEditName(ing.name)
    setEditExpiry(ing.expiry_date || '')
  }

  const cancelEdit = () => {
    setEditingId(null)
    setEditName('')
    setEditExpiry('')
  }

  const handleEdit = async () => {
    if (!editName.trim()) return
    try {
      setError(null)
      await updateIngredient(editingId, {
        name: editName.trim(),
        expiry_date: editExpiry || '',
      })
      cancelEdit()
      load()
    } catch (e) {
      setError('Failed to update ingredient')
    }
  }

  const handleDiscard = async () => {
    const selectedIds = Object.entries(expiryChecked)
      .filter(([, checked]) => checked)
      .map(([id]) => Number(id))
    const realIds = selectedIds.filter(id => id > 0)
    try {
      if (realIds.length > 0) {
        await confirmExpiredThrown(realIds)
      }
      // Remove discarded items from expired list
      const remaining = expiredItems.filter(i => !selectedIds.includes(i.id))
      setExpiredItems(remaining)
      if (remaining.length === 0) {
        setExpiryPanelOpen(false)
      } else {
        const checked = {}
        remaining.forEach(i => { checked[i.id] = true })
        setExpiryChecked(checked)
      }
      load()
    } catch {
      setError('Failed to remove expired items')
    }
  }

  const toggleExpiryCheck = (id) => {
    setExpiryChecked(prev => ({ ...prev, [id]: !prev[id] }))
  }

  const formatExpiry = (dateStr) => {
    if (!dateStr) return null
    try {
      const d = new Date(dateStr + 'T00:00:00')
      return d.toLocaleDateString('tr-TR', { day: 'numeric', month: 'short' })
    } catch {
      return dateStr
    }
  }

  const isExpired = (dateStr) => {
    if (!dateStr) return false
    return dateStr <= new Date().toISOString().split('T')[0]
  }

  const checkedCount = Object.values(expiryChecked).filter(Boolean).length

  return (
    <div style={s.container}>
      {/* Header with expired + add buttons */}
      <div style={s.headerRow}>
        <span style={s.headerText}>Ingredients</span>
        <div style={s.headerBtns}>
          {expiredItems.length > 0 && (
            <button
              style={s.headerExpiredBtn}
              onClick={() => setExpiryPanelOpen(!expiryPanelOpen)}
              title="Expired items"
            >
              <AlertTriangle size={13} />
              <span>{expiredItems.length}</span>
            </button>
          )}
          <button
            style={s.headerAddBtn}
            onClick={() => { setAddPanelOpen(!addPanelOpen); setError(null) }}
            title="Add ingredient"
          >
            {addPanelOpen ? <X size={14} /> : <><Plus size={14} /> <span>Add Item</span></>}
          </button>
        </div>
      </div>

      {/* Add panel (slides open below header) */}
      {addPanelOpen && (
        <div style={s.addPanel}>
          <input
            style={s.addInput}
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleAdd()}
            placeholder="Ingredient name…"
            autoFocus
          />
          <div style={s.addPanelRow}>
            <input
              type="date"
              style={s.addDateInput}
              value={newExpiry}
              onChange={(e) => setNewExpiry(e.target.value)}
            />
            <button style={s.addPanelBtn} onClick={handleAdd}>Add</button>
          </div>
        </div>
      )}

      {/* Ingredient list */}
      <div style={s.list}>
        {error && <div style={s.error}>{error}</div>}
        {loading && <div style={s.empty}>Loading…</div>}
        {!loading && ingredients.length === 0 && (
          <div style={s.empty}>No ingredients yet. Tell me what you have!</div>
        )}
        {ingredients.map((ing) => (
          editingId === ing.id ? (
            /* Edit mode row */
            <div key={ing.id} style={s.editRow}>
              <input
                style={s.editInput}
                value={editName}
                onChange={(e) => setEditName(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') handleEdit()
                  if (e.key === 'Escape') cancelEdit()
                }}
                autoFocus
              />
              <input
                type="date"
                style={s.editDateInput}
                value={editExpiry}
                onChange={(e) => setEditExpiry(e.target.value)}
              />
              <button style={s.editSaveBtn} onClick={handleEdit}>Save</button>
              <button style={s.editCancelBtn} onClick={cancelEdit}>
                <X size={14} />
              </button>
            </div>
          ) : (
            /* Normal row */
            <div key={ing.id} style={{ ...s.row, padding: '7px 16px' }}>
              <span style={s.name}>{ing.name}</span>
              {ing.expiry_date && (
                <span style={{
                  ...s.expiryBadge,
                  color: isExpired(ing.expiry_date) ? 'var(--error, #e74c3c)' : 'var(--text-muted)',
                }}>
                  {formatExpiry(ing.expiry_date)}
                </span>
              )}
              <button
                style={s.iconBtn}
                onClick={() => startEdit(ing)}
                title="Edit"
              >
                <Pencil size={12} />
              </button>
              <button
                style={s.iconBtn}
                onClick={() => handleDelete(ing.id)}
                title="Delete"
              >
                <Trash2 size={12} />
              </button>
            </div>
          )
        ))}
      </div>

      {/* Expiry detail panel */}
      {expiryPanelOpen && (
        <div style={s.expiryPanel}>
          <div style={s.expiryPanelHeader}>
            <button style={s.closeBtn} onClick={() => setExpiryPanelOpen(false)}>
              <X size={16} />
            </button>
            <span style={s.expiryPanelTitle}>Expired Items</span>
            <div style={{ width: 24 }} />
          </div>
          <div style={s.expiryPanelList}>
            {expiredItems.map(item => (
              <label key={item.id} style={s.expiryRow}>
                <input
                  type="checkbox"
                  checked={!!expiryChecked[item.id]}
                  onChange={() => toggleExpiryCheck(item.id)}
                  style={s.checkbox}
                />
                <span style={{ flex: 1, fontSize: 13, color: 'var(--text)' }}>{item.name}</span>
                {item.expiry_date && (
                  <span style={s.expiryBadge}>{formatExpiry(item.expiry_date)}</span>
                )}
              </label>
            ))}
          </div>
          <button
            style={{
              ...s.discardBtn,
              opacity: checkedCount === 0 ? 0.4 : 1,
              cursor: checkedCount === 0 ? 'default' : 'pointer',
            }}
            onClick={handleDiscard}
            disabled={checkedCount === 0}
          >
            Discard{checkedCount > 0 ? ` (${checkedCount})` : ''}
          </button>
        </div>
      )}
    </div>
  )
})

export default IngredientPanel
