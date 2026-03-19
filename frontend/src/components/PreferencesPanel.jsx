import { useState, useEffect } from 'react'
import {
  getPreferences, setPreference, deletePreference,
  getHabits, addHabit, deleteHabit,
} from '../services/api'

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
  body: {
    flex: 1,
    overflowY: 'auto',
    padding: '12px 16px',
    display: 'flex',
    flexDirection: 'column',
    gap: 20,
  },
  section: {
    display: 'flex',
    flexDirection: 'column',
    gap: 8,
  },
  sectionLabel: {
    fontSize: 11,
    fontWeight: 700,
    textTransform: 'uppercase',
    letterSpacing: '0.08em',
    color: 'var(--text-muted)',
  },
  tag: {
    display: 'inline-flex',
    alignItems: 'center',
    gap: 6,
    background: 'var(--surface2)',
    border: '1px solid var(--border)',
    borderRadius: 20,
    padding: '4px 12px',
    fontSize: 12,
    color: 'var(--text)',
  },
  tagX: {
    background: 'none',
    border: 'none',
    color: 'var(--text-muted)',
    fontSize: 14,
    cursor: 'pointer',
    padding: 0,
    lineHeight: 1,
  },
  tagList: {
    display: 'flex',
    flexWrap: 'wrap',
    gap: 6,
  },
  addRow: {
    display: 'flex',
    gap: 6,
  },
  input: {
    flex: 1,
    background: 'var(--surface2)',
    border: '1px solid var(--border)',
    borderRadius: 8,
    padding: '6px 10px',
    color: 'var(--text)',
    fontSize: 12,
    outline: 'none',
  },
  addBtn: {
    background: 'var(--accent)',
    border: 'none',
    borderRadius: 8,
    color: '#fff',
    fontWeight: 700,
    fontSize: 16,
    width: 28,
    height: 28,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
  },
  empty: {
    fontSize: 12,
    color: 'var(--text-muted)',
    fontStyle: 'italic',
  },
  error: {
    padding: '8px 0',
    fontSize: 12,
    color: '#e76f51',
  },
}

function TagList({ items, onDelete, keyField = 'id', labelField = 'value' }) {
  if (!items.length) return <span style={s.empty}>None yet</span>
  return (
    <div style={s.tagList}>
      {items.map((item) => (
        <div key={item[keyField]} style={s.tag}>
          <span>{item[labelField]}</span>
          <button style={s.tagX} onClick={() => onDelete(item[keyField])}>×</button>
        </div>
      ))}
    </div>
  )
}

export default function PreferencesPanel() {
  const [prefs, setPrefs] = useState([])
  const [habits, setHabits] = useState([])
  const [newFav, setNewFav] = useState('')
  const [newDislike, setNewDislike] = useState('')
  const [newHabit, setNewHabit] = useState('')
  const [error, setError] = useState(null)

  const load = async () => {
    try {
      setError(null)
      const [p, h] = await Promise.all([getPreferences(), getHabits()])
      setPrefs(p)
      setHabits(h)
    } catch (e) {
      setError('Failed to load preferences')
    }
  }

  useEffect(() => { load() }, [])

  const favorites = prefs.filter((p) => p.key.startsWith('fav:'))
  const dislikes = prefs.filter((p) => p.key.startsWith('dislike:'))

  const handleAddPref = async (prefix, value, clearInput) => {
    const v = value.trim()
    if (!v) return
    try {
      setError(null)
      await setPreference(`${prefix}:${v}`, v)
      clearInput('')
      load()
    } catch (e) {
      setError('Failed to save preference')
    }
  }

  const handleDeletePref = async (key) => {
    setPrefs((prev) => prev.filter((p) => p.key !== key))
    try {
      await deletePreference(key)
    } catch (e) {
      setError('Failed to delete preference')
      load()
    }
  }

  const handleAddHabit = async () => {
    const v = newHabit.trim()
    if (!v) return
    try {
      setError(null)
      await addHabit(v)
      setNewHabit('')
      load()
    } catch (e) {
      setError('Failed to save habit')
    }
  }

  const handleDeleteHabit = async (id) => {
    setHabits((prev) => prev.filter((h) => h.id !== id))
    try {
      await deleteHabit(id)
    } catch (e) {
      setError('Failed to delete habit')
      load()
    }
  }

  return (
    <div style={s.container}>
      <div style={s.header}>Preferences</div>

      <div style={s.body}>
        {error && <div style={s.error}>{error}</div>}
        {/* Favorites */}
        <div style={s.section}>
          <div style={s.sectionLabel}>Favorites</div>
          <TagList
            items={favorites}
            onDelete={(key) => handleDeletePref(key)}
            keyField="key"
            labelField="value"
          />
          <div style={s.addRow}>
            <input
              style={s.input}
              value={newFav}
              onChange={(e) => setNewFav(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleAddPref('fav', newFav, setNewFav)}
              placeholder="Add favorite…"
            />
            <button style={s.addBtn} onClick={() => handleAddPref('fav', newFav, setNewFav)}>+</button>
          </div>
        </div>

        {/* Dislikes */}
        <div style={s.section}>
          <div style={s.sectionLabel}>Dislikes</div>
          <TagList
            items={dislikes}
            onDelete={(key) => handleDeletePref(key)}
            keyField="key"
            labelField="value"
          />
          <div style={s.addRow}>
            <input
              style={s.input}
              value={newDislike}
              onChange={(e) => setNewDislike(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleAddPref('dislike', newDislike, setNewDislike)}
              placeholder="Add dislike…"
            />
            <button style={s.addBtn} onClick={() => handleAddPref('dislike', newDislike, setNewDislike)}>+</button>
          </div>
        </div>

        {/* Habits */}
        <div style={s.section}>
          <div style={s.sectionLabel}>Habits</div>
          <TagList
            items={habits}
            onDelete={handleDeleteHabit}
            keyField="id"
            labelField="description"
          />
          <div style={s.addRow}>
            <input
              style={s.input}
              value={newHabit}
              onChange={(e) => setNewHabit(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleAddHabit()}
              placeholder="Add habit…"
            />
            <button style={s.addBtn} onClick={handleAddHabit}>+</button>
          </div>
        </div>
      </div>
    </div>
  )
}
