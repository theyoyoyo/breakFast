import { useState, useEffect } from 'react'
import {
  getPreferences, setPreference, deletePreference,
  getHabits, addHabit, deleteHabit,
  getRatings, createRating, updateRating, deleteRating,
  getProfile, upsertProfile,
  getSupplements, createSupplement, deleteSupplement,
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
  ratingsBtn: {
    width: '100%',
    padding: '12px 16px',
    background: 'var(--accent)',
    border: 'none',
    borderRadius: 8,
    color: '#fff',
    fontWeight: 700,
    fontSize: 14,
    cursor: 'pointer',
    textTransform: 'uppercase',
    letterSpacing: '0.05em',
  },
  ratingsPanel: {
    display: 'flex',
    flexDirection: 'column',
    gap: 8,
  },
  ratingRow: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    background: 'var(--surface2)',
    border: '1px solid var(--border)',
    borderRadius: 8,
    padding: '6px 10px',
    fontSize: 13,
  },
  ratingName: {
    flex: 1,
    color: 'var(--text)',
  },
  ratingInput: {
    width: 45,
    background: 'var(--surface)',
    border: '1px solid var(--border)',
    borderRadius: 6,
    padding: '3px 6px',
    color: 'var(--text)',
    fontSize: 13,
    textAlign: 'center',
    outline: 'none',
  },
  profileGrid: {
    display: 'grid',
    gridTemplateColumns: '1fr 1fr',
    gap: 8,
  },
  profileField: {
    display: 'flex',
    flexDirection: 'column',
    gap: 3,
  },
  profileLabel: {
    fontSize: 10,
    fontWeight: 700,
    textTransform: 'uppercase',
    color: 'var(--text-muted)',
  },
  select: {
    background: 'var(--surface2)',
    border: '1px solid var(--border)',
    borderRadius: 8,
    padding: '6px 10px',
    color: 'var(--text)',
    fontSize: 12,
    outline: 'none',
  },
  saveBtn: {
    background: 'var(--accent)',
    border: 'none',
    borderRadius: 8,
    color: '#fff',
    fontWeight: 700,
    fontSize: 12,
    padding: '8px 16px',
    cursor: 'pointer',
    alignSelf: 'flex-end',
  },
  suppRow: {
    display: 'flex',
    alignItems: 'center',
    gap: 6,
    background: 'var(--surface2)',
    border: '1px solid var(--border)',
    borderRadius: 8,
    padding: '6px 10px',
    fontSize: 12,
  },
  suppName: {
    fontWeight: 600,
    color: 'var(--text)',
  },
  suppContents: {
    flex: 1,
    color: 'var(--text-muted)',
    fontSize: 11,
  },
  suppFreq: {
    fontSize: 10,
    fontWeight: 700,
    textTransform: 'uppercase',
    padding: '2px 6px',
    borderRadius: 4,
    background: 'var(--surface)',
    color: 'var(--text-muted)',
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
  const [ratings, setRatings] = useState([])
  const [showRatings, setShowRatings] = useState(false)
  const [newFav, setNewFav] = useState('')
  const [newDislike, setNewDislike] = useState('')
  const [newHabit, setNewHabit] = useState('')
  const [newProduct, setNewProduct] = useState('')
  const [error, setError] = useState(null)

  // Profile state
  const [profile, setProfile] = useState({ age: '', gender: '', height_cm: '', weight_kg: '', activity_level: '' })
  const [profileDirty, setProfileDirty] = useState(false)

  // Supplements state
  const [supplements, setSupplements] = useState([])
  const [newSuppName, setNewSuppName] = useState('')
  const [newSuppContents, setNewSuppContents] = useState('')
  const [newSuppFreq, setNewSuppFreq] = useState('daily')

  const load = async () => {
    try {
      setError(null)
      const [p, h, r, prof, supps] = await Promise.all([
        getPreferences(), getHabits(), getRatings(), getProfile(), getSupplements(),
      ])
      setPrefs(p)
      setHabits(h)
      setRatings(r)
      if (prof) {
        setProfile({
          age: prof.age ?? '',
          gender: prof.gender ?? '',
          height_cm: prof.height_cm ?? '',
          weight_kg: prof.weight_kg ?? '',
          activity_level: prof.activity_level ?? '',
        })
      }
      setSupplements(supps)
      setProfileDirty(false)
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

  const handleAddRating = async () => {
    const v = newProduct.trim()
    if (!v) return
    try {
      setError(null)
      await createRating(v, 10)
      setNewProduct('')
      load()
    } catch (e) {
      setError('Product already rated or failed to save')
    }
  }

  const handleUpdateRating = async (id, value) => {
    const n = parseInt(value, 10)
    if (isNaN(n) || n < 1 || n > 10) return
    setRatings((prev) => prev.map((r) => r.id === id ? { ...r, rating: n } : r))
    try {
      await updateRating(id, n)
    } catch (e) {
      setError('Failed to update rating')
      load()
    }
  }

  const handleDeleteRating = async (id) => {
    setRatings((prev) => prev.filter((r) => r.id !== id))
    try {
      await deleteRating(id)
    } catch (e) {
      setError('Failed to delete rating')
      load()
    }
  }

  // Profile handlers
  const handleProfileChange = (field, value) => {
    setProfile((prev) => ({ ...prev, [field]: value }))
    setProfileDirty(true)
  }

  const handleSaveProfile = async () => {
    try {
      setError(null)
      await upsertProfile({
        age: profile.age ? parseInt(profile.age, 10) : null,
        gender: profile.gender || null,
        height_cm: profile.height_cm ? parseInt(profile.height_cm, 10) : null,
        weight_kg: profile.weight_kg ? parseFloat(profile.weight_kg) : null,
        activity_level: profile.activity_level || null,
      })
      setProfileDirty(false)
    } catch (e) {
      setError('Failed to save profile')
    }
  }

  // Supplement handlers
  const handleAddSupplement = async () => {
    const name = newSuppName.trim()
    if (!name) return
    try {
      setError(null)
      await createSupplement(name, newSuppContents.trim(), newSuppFreq)
      setNewSuppName('')
      setNewSuppContents('')
      setNewSuppFreq('daily')
      load()
    } catch (e) {
      setError('Supplement already exists or failed to save')
    }
  }

  const handleDeleteSupplement = async (id) => {
    setSupplements((prev) => prev.filter((s) => s.id !== id))
    try {
      await deleteSupplement(id)
    } catch (e) {
      setError('Failed to delete supplement')
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

        {/* Ratings */}
        <div style={s.section}>
          <button style={s.ratingsBtn} onClick={() => setShowRatings(!showRatings)}>
            Ratings ({ratings.length})
          </button>
          {showRatings && (
            <div style={s.ratingsPanel}>
              {ratings.length === 0 && <span style={s.empty}>No ratings yet</span>}
              {ratings.map((r) => (
                <div key={r.id} style={s.ratingRow}>
                  <span style={s.ratingName}>{r.product_name}</span>
                  <input
                    type="number"
                    min="1"
                    max="10"
                    style={s.ratingInput}
                    value={r.rating}
                    onChange={(e) => handleUpdateRating(r.id, e.target.value)}
                  />
                  <button style={s.tagX} onClick={() => handleDeleteRating(r.id)}>×</button>
                </div>
              ))}
              <div style={s.addRow}>
                <input
                  style={s.input}
                  value={newProduct}
                  onChange={(e) => setNewProduct(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleAddRating()}
                  placeholder="Add product…"
                />
                <button style={s.addBtn} onClick={handleAddRating}>+</button>
              </div>
            </div>
          )}
        </div>

        {/* Profile */}
        <div style={s.section}>
          <div style={s.sectionLabel}>Profile</div>
          <div style={s.profileGrid}>
            <div style={s.profileField}>
              <label style={s.profileLabel}>Age</label>
              <input
                type="number"
                style={s.input}
                value={profile.age}
                onChange={(e) => handleProfileChange('age', e.target.value)}
                placeholder="—"
              />
            </div>
            <div style={s.profileField}>
              <label style={s.profileLabel}>Gender</label>
              <select
                style={s.select}
                value={profile.gender}
                onChange={(e) => handleProfileChange('gender', e.target.value)}
              >
                <option value="">—</option>
                <option value="male">Male</option>
                <option value="female">Female</option>
              </select>
            </div>
            <div style={s.profileField}>
              <label style={s.profileLabel}>Height (cm)</label>
              <input
                type="number"
                style={s.input}
                value={profile.height_cm}
                onChange={(e) => handleProfileChange('height_cm', e.target.value)}
                placeholder="—"
              />
            </div>
            <div style={s.profileField}>
              <label style={s.profileLabel}>Weight (kg)</label>
              <input
                type="number"
                step="0.1"
                style={s.input}
                value={profile.weight_kg}
                onChange={(e) => handleProfileChange('weight_kg', e.target.value)}
                placeholder="—"
              />
            </div>
          </div>
          <div style={s.profileField}>
            <label style={s.profileLabel}>Activity Level</label>
            <select
              style={s.select}
              value={profile.activity_level}
              onChange={(e) => handleProfileChange('activity_level', e.target.value)}
            >
              <option value="">—</option>
              <option value="sedentary">Sedentary</option>
              <option value="light">Light</option>
              <option value="moderate">Moderate</option>
              <option value="active">Active</option>
              <option value="very_active">Very Active</option>
            </select>
          </div>
          {profileDirty && (
            <button style={s.saveBtn} onClick={handleSaveProfile}>Save Profile</button>
          )}
        </div>

        {/* Supplements */}
        <div style={s.section}>
          <div style={s.sectionLabel}>Supplements</div>
          {supplements.length === 0 && <span style={s.empty}>No supplements yet</span>}
          {supplements.map((sup) => (
            <div key={sup.id} style={s.suppRow}>
              <span style={s.suppName}>{sup.name}</span>
              {sup.contents && <span style={s.suppContents}>{sup.contents}</span>}
              <span style={s.suppFreq}>{sup.frequency}</span>
              <button style={s.tagX} onClick={() => handleDeleteSupplement(sup.id)}>×</button>
            </div>
          ))}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <div style={s.addRow}>
              <input
                style={s.input}
                value={newSuppName}
                onChange={(e) => setNewSuppName(e.target.value)}
                placeholder="Supplement name…"
              />
              <select
                style={{ ...s.select, width: 90, flex: 'none' }}
                value={newSuppFreq}
                onChange={(e) => setNewSuppFreq(e.target.value)}
              >
                <option value="daily">Daily</option>
                <option value="sometimes">Sometimes</option>
              </select>
            </div>
            <div style={s.addRow}>
              <input
                style={s.input}
                value={newSuppContents}
                onChange={(e) => setNewSuppContents(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleAddSupplement()}
                placeholder="Contents (optional)…"
              />
              <button style={s.addBtn} onClick={handleAddSupplement}>+</button>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
