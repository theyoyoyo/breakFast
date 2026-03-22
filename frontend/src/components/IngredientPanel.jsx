import { useState, useEffect } from 'react'
import { getIngredients, addIngredient, deleteIngredient } from '../services/api'
import * as s from './IngredientPanel.styles'

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
