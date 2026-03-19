import { useState, useEffect } from 'react'
import { getIngredients, addIngredient, deleteIngredient } from '../services/api'

const s = {
  container: {
    background: 'var(--surface)',
    borderRadius: 'var(--radius)',
    display: 'flex',
    flexDirection: 'column',
    height: '100%',
    overflow: 'hidden',
  },
  header: {
    padding: '14px 16px',
    fontWeight: 700,
    fontSize: 13,
    textTransform: 'uppercase',
    letterSpacing: '0.08em',
    color: 'var(--text-muted)',
    borderBottom: '1px solid var(--border)',
  },
  list: {
    flex: 1,
    overflowY: 'auto',
    padding: '8px 0',
  },
  row: {
    display: 'flex',
    alignItems: 'center',
    padding: '6px 16px',
    gap: 8,
  },
  name: {
    flex: 1,
    fontSize: 13,
    color: 'var(--text)',
  },
  qty: {
    fontSize: 12,
    color: 'var(--text-muted)',
  },
  deleteBtn: {
    background: 'none',
    border: 'none',
    color: 'var(--text-muted)',
    fontSize: 14,
    padding: '2px 4px',
    borderRadius: 4,
    opacity: 0.5,
    transition: 'opacity 0.1s',
  },
  addRow: {
    display: 'flex',
    gap: 6,
    padding: '10px 12px',
    borderTop: '1px solid var(--border)',
  },
  input: {
    flex: 1,
    background: 'var(--surface2)',
    border: '1px solid var(--border)',
    borderRadius: 8,
    padding: '6px 10px',
    color: 'var(--text)',
    fontSize: 13,
    outline: 'none',
  },
  addBtn: {
    background: 'var(--accent)',
    border: 'none',
    borderRadius: 8,
    color: '#fff',
    fontWeight: 700,
    fontSize: 18,
    width: 32,
    height: 32,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
  },
  empty: {
    padding: 20,
    color: 'var(--text-muted)',
    fontSize: 13,
    textAlign: 'center',
  },
  error: {
    padding: '8px 16px',
    fontSize: 12,
    color: '#e76f51',
  },
}

export default function IngredientPanel({ refreshTrigger }) {
  const [ingredients, setIngredients] = useState([])
  const [newName, setNewName] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

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

  useEffect(() => { load() }, [refreshTrigger])

  const handleAdd = async () => {
    const name = newName.trim()
    if (!name) return
    try {
      setError(null)
      await addIngredient(name, null, null)
      setNewName('')
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

  return (
    <div style={s.container}>
      <div style={s.header}>Ingredients</div>

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
            {(ing.quantity || ing.unit) && (
              <span style={s.qty}>
                {[ing.quantity, ing.unit].filter(Boolean).join(' ')}
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

      <div style={s.addRow}>
        <input
          style={s.input}
          value={newName}
          onChange={(e) => setNewName(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleAdd()}
          placeholder="Add ingredient…"
        />
        <button style={s.addBtn} onClick={handleAdd} title="Add">+</button>
      </div>
    </div>
  )
}
