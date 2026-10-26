import { useState, useEffect } from 'react'
import {
  getPreferences, setPreference, deletePreference,
  getHabits, addHabit, deleteHabit,
} from '../services/api'
import * as s from './PreferencesPanel.styles'

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
  const [newAvoid, setNewAvoid] = useState('')
  const [newHabit, setNewHabit] = useState('')
  const [error, setError] = useState(null)

  const load = async () => {
    try {
      setError(null)
      const [p, h] = await Promise.all([getPreferences(), getHabits()])
      setPrefs(p)
      setHabits(h)
    } catch {
      setError('Failed to load preferences')
    }
  }

  useEffect(() => { load() }, [])

  const favorites = prefs.filter((p) => p.key.startsWith('fav:'))
  const dislikes = prefs.filter((p) => p.key.startsWith('dislike:'))
  const avoidList = prefs.filter((p) => p.key.startsWith('avoid:'))

  const handleAddPref = async (prefix, value, clearInput) => {
    const v = value.trim()
    if (!v) return
    try {
      setError(null)
      await setPreference(`${prefix}:${v}`, v)
      clearInput('')
      load()
    } catch {
      setError('Failed to save preference')
    }
  }

  const handleDeletePref = async (key) => {
    setPrefs((prev) => prev.filter((p) => p.key !== key))
    try {
      await deletePreference(key)
    } catch {
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
    } catch {
      setError('Failed to save habit')
    }
  }

  const handleDeleteHabit = async (id) => {
    setHabits((prev) => prev.filter((h) => h.id !== id))
    try {
      await deleteHabit(id)
    } catch {
      setError('Failed to delete habit')
      load()
    }
  }

  return (
    <div style={s.container}>
      <div style={s.brandHeader}>break FAST</div>

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

        {/* Avoid List */}
        <div style={s.section}>
          <div style={s.sectionLabel}>Avoid List</div>
          <TagList
            items={avoidList}
            onDelete={(key) => handleDeletePref(key)}
            keyField="key"
            labelField="value"
          />
          <div style={s.addRow}>
            <input
              style={s.input}
              value={newAvoid}
              onChange={(e) => setNewAvoid(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleAddPref('avoid', newAvoid, setNewAvoid)}
              placeholder="Add avoided ingredient…"
            />
            <button style={s.addBtn} onClick={() => handleAddPref('avoid', newAvoid, setNewAvoid)}>+</button>
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
