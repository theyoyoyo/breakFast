import { useState, useEffect, useCallback, useImperativeHandle, forwardRef } from 'react'
import { getIngredients, addIngredient, deleteIngredient, getExpiredIngredients, confirmExpiredThrown } from '../services/api'
import * as s from './IngredientPanel.styles'

const IngredientPanel = forwardRef(function IngredientPanel({ refreshTrigger }, ref) {
  const [ingredients, setIngredients] = useState([])
  const [newName, setNewName] = useState('')
  const [newExpiry, setNewExpiry] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  // Expiry state
  const [expiredItems, setExpiredItems] = useState([])
  const [expiryPanelOpen, setExpiryPanelOpen] = useState(false)
  const [expiryEditList, setExpiryEditList] = useState([])
  const [expiryCovered, setExpiryCovered] = useState(false)

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
        setExpiryEditList(expired)
        setExpiryCovered(false)
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
      setExpiryEditList(fakeExpired)
      setExpiryCovered(false)
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

  const handleThrown = async () => {
    const realIds = expiryEditList.filter(i => i.id > 0).map(i => i.id)
    try {
      if (realIds.length > 0) {
        await confirmExpiredThrown(realIds)
      }
      setExpiryCovered(true)
      setExpiryPanelOpen(false)
      load()
    } catch {
      setError('Failed to remove expired items')
    }
  }

  const removeFromExpiryList = (id) => {
    setExpiryEditList(prev => prev.filter(i => i.id !== id))
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

  return (
    <div style={s.container}>
      <div style={s.header}>Ingredients</div>

      {/* Ingredient list */}
      <div style={s.list}>
        {error && <div style={s.error}>{error}</div>}
        {loading && <div style={s.empty}>Loading…</div>}
        {!loading && ingredients.length === 0 && (
          <div style={s.empty}>No ingredients yet. Tell me what you have!</div>
        )}
        {ingredients.map((ing) => (
          <div
            key={ing.id}
            style={{ ...s.row, padding: '7px 16px' }}
          >
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
              style={s.deleteBtn}
              onClick={() => handleDelete(ing.id)}
              title="Remove"
            >
              ×
            </button>
          </div>
        ))}
      </div>

      {/* Expiry widget */}
      {expiredItems.length > 0 && (
        <div
          style={{
            ...s.expiryWidget,
            ...(expiryCovered ? s.expiryWidgetCovered : {}),
          }}
          onClick={() => !expiryCovered && setExpiryPanelOpen(true)}
        >
          <span>{expiryCovered ? '✓ Handled' : `⚠ ${expiredItems.length} expired item${expiredItems.length > 1 ? 's' : ''}`}</span>
        </div>
      )}

      {/* Expiry detail panel */}
      {expiryPanelOpen && (
        <div style={s.expiryPanel}>
          <div style={s.expiryPanelHeader}>
            <span>Expired Items</span>
            <button style={s.closeBtn} onClick={() => setExpiryPanelOpen(false)}>×</button>
          </div>
          <div style={s.expiryPanelList}>
            {expiryEditList.map(item => (
              <div key={item.id} style={s.expiryRow}>
                <span style={{ flex: 1, fontSize: 13 }}>{item.name}</span>
                {item.expiry_date && (
                  <span style={s.expiryBadge}>{formatExpiry(item.expiry_date)}</span>
                )}
                <button
                  style={s.deleteBtn}
                  onClick={() => removeFromExpiryList(item.id)}
                  title="Remove from list"
                >×</button>
              </div>
            ))}
            {expiryEditList.length === 0 && (
              <div style={s.empty}>All items removed from list</div>
            )}
          </div>
          <button
            style={s.thrownBtn}
            onClick={handleThrown}
            disabled={expiryEditList.length === 0}
          >
            Thrown
          </button>
        </div>
      )}

      {/* Add ingredient row */}
      <div style={s.addRow}>
        <input
          style={s.input}
          value={newName}
          onChange={(e) => setNewName(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleAdd()}
          placeholder="Add ingredient…"
        />
        <input
          type="date"
          style={s.dateInput}
          value={newExpiry}
          onChange={(e) => setNewExpiry(e.target.value)}
          title="Expiry date (optional)"
        />
        <button style={s.addBtn} onClick={handleAdd} title="Add">+</button>
      </div>
    </div>
  )
})

export default IngredientPanel
