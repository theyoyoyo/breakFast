import { useState, useEffect } from 'react'
import {
  getRatings, createRating, updateRating, deleteRating,
  getProfile, upsertProfile,
  getSupplements, createSupplement, updateSupplement, deleteSupplement,
  getMeals, updateMeal, deleteMeal, deleteOldMeals,
  getHealthRules, createHealthRule, updateHealthRule, deleteHealthRule,
} from '../services/api'
import * as s from './SettingsPanel.styles'

const PRIORITY_OPTIONS = [
  { value: 'low', label: "Don't really care" },
  { value: 'high', label: 'Care a lot' },
  { value: 'critical', label: 'Top priority' },
]

export default function SettingsPanel() {
  const [ratings, setRatings] = useState([])
  const [view, setView] = useState('settings')
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

  // Meal history state
  const [meals, setMeals] = useState([])
  const [editingMealId, setEditingMealId] = useState(null)
  const [editMealName, setEditMealName] = useState('')
  const [editMealIngredients, setEditMealIngredients] = useState('')

  // Health rules state
  const [healthRules, setHealthRules] = useState([])
  const [newRuleText, setNewRuleText] = useState('')

  const load = async () => {
    try {
      setError(null)
      const [r, prof, supps, rules, m] = await Promise.all([
        getRatings(), getProfile(), getSupplements(), getHealthRules(), getMeals(),
      ])
      setRatings(r)
      setMeals(m)
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
      setHealthRules(rules)
      setProfileDirty(false)
    } catch {
      setError('Failed to load settings')
    }
  }

  useEffect(() => { load() }, [])

  // Rating handlers
  const handleAddRating = async () => {
    const v = newProduct.trim()
    if (!v) return
    try {
      setError(null)
      await createRating(v, 10)
      setNewProduct('')
      load()
    } catch {
      setError('Product already rated or failed to save')
    }
  }

  const handleUpdateRating = async (id, value) => {
    const n = parseInt(value, 10)
    if (isNaN(n) || n < 1 || n > 10) return
    setRatings((prev) => prev.map((r) => r.id === id ? { ...r, rating: n } : r))
    try {
      await updateRating(id, n)
    } catch {
      setError('Failed to update rating')
      load()
    }
  }

  const handleDeleteRating = async (id) => {
    setRatings((prev) => prev.filter((r) => r.id !== id))
    try {
      await deleteRating(id)
    } catch {
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
    } catch {
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
    } catch {
      setError('Supplement already exists or failed to save')
    }
  }

  const handleToggleFrequency = async (sup) => {
    const newFreq = sup.frequency === 'daily' ? 'sometimes' : 'daily'
    setSupplements((prev) => prev.map((s) => s.id === sup.id ? { ...s, frequency: newFreq } : s))
    try {
      await updateSupplement(sup.id, { name: sup.name, contents: sup.contents, frequency: newFreq })
    } catch {
      setError('Failed to update supplement')
      load()
    }
  }

  const handleDeleteSupplement = async (id) => {
    setSupplements((prev) => prev.filter((s) => s.id !== id))
    try {
      await deleteSupplement(id)
    } catch {
      setError('Failed to delete supplement')
      load()
    }
  }

  // Health rule handlers
  const handleAddRule = async () => {
    const text = newRuleText.trim()
    if (!text) return
    try {
      setError(null)
      await createHealthRule(text, 'high')
      setNewRuleText('')
      load()
    } catch {
      setError('Failed to add health rule')
    }
  }

  const handleUpdateRulePriority = async (id, priority) => {
    setHealthRules((prev) => prev.map((r) => r.id === id ? { ...r, priority } : r))
    try {
      await updateHealthRule(id, { priority })
    } catch {
      setError('Failed to update health rule')
      load()
    }
  }

  const handleDeleteRule = async (id) => {
    setHealthRules((prev) => prev.filter((r) => r.id !== id))
    try {
      await deleteHealthRule(id)
    } catch {
      setError('Failed to delete health rule')
      load()
    }
  }

  // Meal history handlers
  const handleStartEditMeal = (meal) => {
    setEditingMealId(meal.id)
    setEditMealName(meal.meal_name)
    setEditMealIngredients((meal.ingredients || []).join(', '))
  }

  const handleSaveEditMeal = async (meal) => {
    try {
      setError(null)
      await updateMeal(meal.id, {
        meal_name: editMealName,
        ingredients: editMealIngredients.split(',').map(s => s.trim()).filter(Boolean),
        description: meal.description,
        steps: meal.steps,
        prep_time_min: meal.prep_time_min,
        nutrition_note: meal.nutrition_note,
      })
      setEditingMealId(null)
      load()
    } catch {
      setError('Failed to update meal')
    }
  }

  const handleDeleteMeal = async (id) => {
    setMeals(prev => prev.filter(m => m.id !== id))
    try {
      await deleteMeal(id)
    } catch {
      setError('Failed to delete meal')
      load()
    }
  }

  // --- Meal History sub-page ---
  if (view === 'meals') {
    return (
      <div style={s.container}>
        <div style={{ ...s.header, display: 'flex', alignItems: 'center', gap: 8 }}>
          <button style={s.backBtn} onClick={() => setView('settings')}>←</button>
          <span>Meal History ({meals.length})</span>
        </div>
        <div style={s.body}>
          {error && <div style={s.error}>{error}</div>}
          {meals.length === 0 && <span style={s.empty}>No meals logged yet</span>}
          {meals.map((meal) => (
            <div key={meal.id} style={s.mealRow}>
              {editingMealId === meal.id ? (
                <div style={s.mealEditForm}>
                  <input
                    style={s.input}
                    value={editMealName}
                    onChange={(e) => setEditMealName(e.target.value)}
                    placeholder="Meal name"
                  />
                  <input
                    style={s.input}
                    value={editMealIngredients}
                    onChange={(e) => setEditMealIngredients(e.target.value)}
                    placeholder="Ingredients (comma separated)"
                  />
                  <div style={{ display: 'flex', gap: 6 }}>
                    <button style={s.saveBtn} onClick={() => handleSaveEditMeal(meal)}>Save</button>
                    <button style={s.cancelEditBtn} onClick={() => setEditingMealId(null)}>Cancel</button>
                  </div>
                </div>
              ) : (
                <>
                  <div style={s.mealInfo}>
                    <span style={s.mealName}>{meal.meal_name}</span>
                    <span style={s.mealDate}>{new Date(meal.logged_at).toLocaleDateString('tr-TR', { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' })}</span>
                    {meal.ingredients?.length > 0 && (
                      <span style={s.mealIngredients}>{meal.ingredients.join(', ')}</span>
                    )}
                  </div>
                  <div style={s.mealActions}>
                    <button style={s.editMealBtn} onClick={() => handleStartEditMeal(meal)} title="Edit">✏️</button>
                    <button style={s.deleteMealBtn} onClick={() => handleDeleteMeal(meal.id)} title="Delete">🗑️</button>
                  </div>
                </>
              )}
            </div>
          ))}
        </div>
      </div>
    )
  }

  // --- Health Rules sub-page ---
  if (view === 'health-rules') {
    return (
      <div style={s.container}>
        <div style={{ ...s.header, display: 'flex', alignItems: 'center', gap: 8 }}>
          <button style={s.backBtn} onClick={() => setView('settings')}>←</button>
          <span>Health Rules ({healthRules.length})</span>
        </div>
        <div style={s.body}>
          {error && <div style={s.error}>{error}</div>}
          {healthRules.length === 0 && <span style={s.empty}>No health rules yet</span>}
          {healthRules.map((rule) => (
            <div key={rule.id} style={s.ruleRow}>
              <div style={s.ruleTop}>
                <span style={s.ruleName}>{rule.rule_text}</span>
                <button style={s.tagX} onClick={() => handleDeleteRule(rule.id)}>×</button>
              </div>
              <div style={s.priorityRow}>
                {PRIORITY_OPTIONS.map((opt) => (
                  <button
                    key={opt.value}
                    style={s.priorityBtn(rule.priority === opt.value, opt.value)}
                    onClick={() => handleUpdateRulePriority(rule.id, opt.value)}
                  >
                    {opt.label}
                  </button>
                ))}
              </div>
            </div>
          ))}
          <div style={s.addRow}>
            <input
              style={s.input}
              value={newRuleText}
              onChange={(e) => setNewRuleText(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleAddRule()}
              placeholder="e.g. Avoid refined sugars, Favor omega-3 sources…"
            />
            <button style={s.addBtn} onClick={handleAddRule}>+</button>
          </div>
        </div>
      </div>
    )
  }

  // --- Ratings sub-page ---
  if (view === 'ratings') {
    return (
      <div style={s.container}>
        <div style={{ ...s.header, display: 'flex', alignItems: 'center', gap: 8 }}>
          <button style={s.backBtn} onClick={() => setView('settings')}>←</button>
          <span>Ratings ({ratings.length})</span>
        </div>
        <div style={s.body}>
          {error && <div style={s.error}>{error}</div>}
          {ratings.length === 0 && <span style={s.empty}>No ratings yet</span>}
          {ratings.map((r) => (
            <div key={r.id} style={s.ratingRow}>
              <div style={s.ratingTop}>
                <span style={s.ratingName}>{r.product_name}</span>
                <button style={s.tagX} onClick={() => handleDeleteRating(r.id)}>×</button>
              </div>
              <div style={s.starsRow}>
                {Array.from({ length: 10 }, (_, i) => i + 1).map(n => (
                  <div
                    key={n}
                    style={s.starCell}
                    onClick={() => handleUpdateRating(r.id, n)}
                  >
                    <span style={s.starNum}>{n}</span>
                    <span style={s.star(n <= r.rating)}>★</span>
                  </div>
                ))}
              </div>
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
      </div>
    )
  }

  // --- Main settings view ---
  return (
    <div style={s.container}>
      <div style={s.header}>Settings</div>

      <div style={s.body}>
        {error && <div style={s.error}>{error}</div>}

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
              <button style={s.suppFreq} onClick={() => handleToggleFrequency(sup)} title="Click to toggle">{sup.frequency}</button>
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
                placeholder="e.g. Vitamin D3 1000IU, K2 100mcg, Zinc 15mg"
              />
              <button style={s.addBtn} onClick={handleAddSupplement}>+</button>
            </div>
          </div>
        </div>

        {/* Meal History — navigates to sub-page */}
        <div style={s.section}>
          <button style={s.healthRulesBtn} onClick={() => setView('meals')}>
            Meal History ({meals.length}) →
          </button>
        </div>

        {/* Health Rules — navigates to sub-page */}
        <div style={s.section}>
          <button style={s.healthRulesBtn} onClick={() => setView('health-rules')}>
            Health Rules ({healthRules.length}) →
          </button>
        </div>

        {/* Ratings — navigates to sub-page */}
        <div style={s.section}>
          <button style={s.ratingsBtn} onClick={() => setView('ratings')}>
            Ratings ({ratings.length}) →
          </button>
        </div>

        {/* Data management */}
        <div style={s.section}>
          <div style={s.sectionLabel}>Data</div>
          <button
            style={s.dangerBtn}
            onClick={async () => {
              try {
                setError(null)
                const result = await deleteOldMeals()
                setError(result.deleted > 0
                  ? `${result.deleted} old meal(s) deleted`
                  : 'No meals older than 1 year')
              } catch {
                setError('Failed to delete old meals')
              }
            }}
          >
            🗑 Delete meals older than 1 year
          </button>
        </div>
      </div>
    </div>
  )
}
