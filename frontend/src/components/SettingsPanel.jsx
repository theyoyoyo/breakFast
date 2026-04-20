import { useState, useEffect } from 'react'
import {
  getRatings, createRating, updateRating, deleteRating,
  getProfile, upsertProfile,
  getSupplements, createSupplement, updateSupplement, deleteSupplement,
  getMeals, updateMeal, deleteMeal, deleteOldMeals,
  getHealthRules, createHealthRule, updateHealthRule, deleteHealthRule,
  addFavorite,
} from '../services/api'
import WeeklySummary from './WeeklySummary'
import KitchenSettings from './KitchenSettings'
import MealEditor from './MealEditor'
import StarRating from './StarRating'
import * as s from './SettingsPanel.styles'

const PRIORITY_OPTIONS = [
  { value: 'low', label: "Don't really care" },
  { value: 'high', label: 'Care a lot' },
  { value: 'critical', label: 'Top priority' },
]

export default function SettingsPanel({ visible }) {
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
  const [expandedMealId, setExpandedMealId] = useState(null)

  // Health rules state
  const [healthRules, setHealthRules] = useState([])
  const [newRuleText, setNewRuleText] = useState('')
  const [pendingRuleDeletes, setPendingRuleDeletes] = useState(new Set())

  // Meal pending deletes
  const [pendingMealDeletes, setPendingMealDeletes] = useState(new Set())

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

  useEffect(() => { load() }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // Reload data when the Settings tab becomes visible
  useEffect(() => { if (visible) load() }, [visible]) // eslint-disable-line react-hooks/exhaustive-deps

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

  const handleClearProfileField = (field) => {
    setProfile((prev) => ({ ...prev, [field]: '' }))
    setProfileDirty(true)
  }

  const handleSaveProfile = async () => {
    const age = profile.age ? parseInt(profile.age, 10) : null
    const height_cm = profile.height_cm ? parseInt(profile.height_cm, 10) : null
    const weight_kg = profile.weight_kg ? parseFloat(profile.weight_kg) : null
    if (age !== null && age < 1) { setError('Age must be a positive number'); return }
    if (height_cm !== null && height_cm < 1) { setError('Height must be a positive number'); return }
    if (weight_kg !== null && weight_kg <= 0) { setError('Weight must be a positive number'); return }
    try {
      setError(null)
      await upsertProfile({
        age,
        gender: profile.gender || null,
        height_cm,
        weight_kg,
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

  const handleToggleRuleDelete = (id) => {
    setPendingRuleDeletes(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id); else next.add(id)
      return next
    })
  }

  const handleSaveRules = async () => {
    if (pendingRuleDeletes.size === 0) return
    try {
      setError(null)
      for (const id of pendingRuleDeletes) {
        await deleteHealthRule(id)
      }
      setPendingRuleDeletes(new Set())
      load()
    } catch {
      setError('Failed to delete health rule(s)')
      load()
    }
  }

  // Meal history handlers
  const handleExpandMeal = (meal) => {
    if (expandedMealId === meal.id) {
      setExpandedMealId(null)
      return
    }
    setExpandedMealId(meal.id)
  }

  const handleSaveMeal = async (meal) => {
    try {
      setError(null)
      await updateMeal(meal.id, {
        meal_name: meal.menu_name || meal.meal_name,
        ingredients: meal.ingredients,
        description: meal.description,
        steps: meal.steps,
        prep_time_min: meal.prep_time_min,
        nutrition_note: meal.nutrition_note,
        menu_items: meal.menu || meal.menu_items || null,
      })
      setExpandedMealId(null)
      load()
    } catch {
      setError('Failed to update meal')
    }
  }

  const handleToggleMealDelete = (id) => {
    if (expandedMealId === id) setExpandedMealId(null)
    setPendingMealDeletes(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id); else next.add(id)
      return next
    })
  }

  const handleSaveMealDeletes = async () => {
    if (pendingMealDeletes.size === 0) return
    try {
      setError(null)
      for (const id of pendingMealDeletes) {
        await deleteMeal(id)
      }
      setPendingMealDeletes(new Set())
      load()
    } catch {
      setError('Failed to delete meal(s)')
      load()
    }
  }

  // Receives current editor state (not stale meal prop) via MealEditor's onFavorite
  const handleCopyToFavorites = async (currentMeal) => {
    await addFavorite({
      meal_name: currentMeal.menu_name || currentMeal.meal_name,
      description: currentMeal.description,
      ingredients: Array.isArray(currentMeal.ingredients) ? currentMeal.ingredients : [],
      steps: Array.isArray(currentMeal.steps) ? currentMeal.steps : [],
      prep_time_min: currentMeal.prep_time_min,
      nutrition_note: currentMeal.nutrition_note,
      menu_items: currentMeal.menu || currentMeal.menu_items || null,
    })
  }

  // --- Weekly Summary sub-page ---
  if (view === 'weekly') {
    return <WeeklySummary onBack={() => setView('settings')} />
  }

  // --- Kitchen sub-page ---
  if (view === 'kitchen') {
    return <KitchenSettings onBack={() => setView('settings')} />
  }

  // --- Meal History sub-page ---
  if (view === 'meals') {
    return (
      <div style={s.container}>
        <div style={{ ...s.header, display: 'flex', alignItems: 'center', gap: 8 }}>
          <button style={s.backBtn} onClick={() => { setPendingMealDeletes(new Set()); setView('settings') }}>←</button>
          <span>Meal History ({meals.length})</span>
        </div>
        <div style={s.body}>
          {error && <div style={s.error}>{error}</div>}
          {meals.length === 0 && <span style={s.empty}>No meals logged yet</span>}
          {meals.map((meal) => {
            const markedForDelete = pendingMealDeletes.has(meal.id)
            return (
              <div key={meal.id} style={{ ...s.mealCard, opacity: markedForDelete ? 0.4 : 1 }}>
                <div style={s.mealHeader} onClick={() => !markedForDelete && handleExpandMeal(meal)}>
                  <div style={s.mealInfo}>
                    <span style={{ ...s.mealName, textDecoration: markedForDelete ? 'line-through' : 'none' }}>{meal.meal_name}</span>
                    <span style={s.mealDate}>{new Date(meal.logged_at).toLocaleDateString('tr-TR', { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' })}</span>
                  </div>
                  <div style={s.mealActions}>
                    {!markedForDelete && <span style={s.expandIcon}>{expandedMealId === meal.id ? '▼' : '▶'}</span>}
                    <button style={s.deleteMealBtn} onClick={(e) => { e.stopPropagation(); handleToggleMealDelete(meal.id) }} title={markedForDelete ? 'Undo delete' : 'Delete meal'}>
                      {markedForDelete ? '↩' : '🗑️'}
                    </button>
                  </div>
                </div>

                {expandedMealId === meal.id && !markedForDelete && (
                  <div style={s.mealExpanded}>
                    <MealEditor
                      meal={{ ...meal, menu: meal.menu_items || undefined }}
                      onSave={(updated) => handleSaveMeal({ ...meal, ...updated })}
                      onClose={() => setExpandedMealId(null)}
                      showPrepTime={true}
                      editPrepTime={true}
                      menuMode={!!(meal.menu_items && meal.menu_items.length > 0)}
                      onFavorite={handleCopyToFavorites}
                    />
                  </div>
                )}
              </div>
            )
          })}
          {pendingMealDeletes.size > 0 && (
            <button style={{ ...s.saveBtn, alignSelf: 'stretch', textAlign: 'center' }} onClick={handleSaveMealDeletes}>
              Save ({pendingMealDeletes.size} to delete)
            </button>
          )}
        </div>
      </div>
    )
  }

  // --- Health Rules sub-page ---
  if (view === 'health-rules') {
    return (
      <div style={s.container}>
        <div style={{ ...s.header, display: 'flex', alignItems: 'center', gap: 8 }}>
          <button style={s.backBtn} onClick={() => { setPendingRuleDeletes(new Set()); setView('settings') }}>←</button>
          <span>Health Rules ({healthRules.length})</span>
        </div>
        <div style={s.body}>
          {error && <div style={s.error}>{error}</div>}
          {healthRules.length === 0 && <span style={s.empty}>No health rules yet</span>}
          {healthRules.map((rule) => {
            const markedForDelete = pendingRuleDeletes.has(rule.id)
            return (
              <div key={rule.id} style={{ ...s.ruleRow, opacity: markedForDelete ? 0.4 : 1, textDecoration: markedForDelete ? 'line-through' : 'none' }}>
                <div style={s.ruleTop}>
                  <span style={s.ruleName}>{rule.rule_text}</span>
                  <button style={s.tagX} onClick={() => handleToggleRuleDelete(rule.id)}>{markedForDelete ? '↩' : '×'}</button>
                </div>
                {!markedForDelete && (
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
                )}
              </div>
            )
          })}
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
          {pendingRuleDeletes.size > 0 && (
            <button style={s.saveBtn} onClick={handleSaveRules}>
              Save ({pendingRuleDeletes.size} to delete)
            </button>
          )}
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
              <StarRating
                value={r.rating}
                size={18}
                numSize={9}
                onChange={(n) => handleUpdateRating(r.id, n)}
              />
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
              <div style={s.profileInputRow}>
                <input
                  type="number"
                  min="1"
                  style={s.input}
                  value={profile.age}
                  onChange={(e) => handleProfileChange('age', e.target.value)}
                  placeholder="—"
                />
                {profile.age !== '' && <button style={s.clearFieldBtn} onClick={() => handleClearProfileField('age')}>×</button>}
              </div>
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
              <div style={s.profileInputRow}>
                <input
                  type="number"
                  min="1"
                  style={s.input}
                  value={profile.height_cm}
                  onChange={(e) => handleProfileChange('height_cm', e.target.value)}
                  placeholder="—"
                />
                {profile.height_cm !== '' && <button style={s.clearFieldBtn} onClick={() => handleClearProfileField('height_cm')}>×</button>}
              </div>
            </div>
            <div style={s.profileField}>
              <label style={s.profileLabel}>Weight (kg)</label>
              <div style={s.profileInputRow}>
                <input
                  type="number"
                  min="0.1"
                  step="0.1"
                  style={s.input}
                  value={profile.weight_kg}
                  onChange={(e) => handleProfileChange('weight_kg', e.target.value)}
                  placeholder="—"
                />
                {profile.weight_kg !== '' && <button style={s.clearFieldBtn} onClick={() => handleClearProfileField('weight_kg')}>×</button>}
              </div>
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
              <span style={{ ...s.suppName, flex: sup.contents ? undefined : 1 }}>{sup.name}</span>
              {sup.contents && <span style={s.suppContents}>{sup.contents}</span>}
              <button style={s.suppFreq(sup.frequency)} onClick={() => handleToggleFrequency(sup)} title="Click to toggle">{sup.frequency}</button>
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

        {/* Kitchen — navigates to sub-page */}
        <div style={s.section}>
          <button style={s.navBtn} onClick={() => setView('kitchen')}>
            Kitchen →
          </button>
        </div>

        {/* Weekly Summary — navigates to sub-page */}
        <div style={s.section}>
          <button style={s.healthRulesBtn} onClick={() => setView('weekly')}>
            Weekly Summary →
          </button>
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

        {/* Spacer to push delete button to bottom */}
        <div style={{ flex: 1 }} />

        <button
          style={s.dangerBtn}
          onClick={async () => {
            try {
              setError(null)
              const result = await deleteOldMeals()
              const msg = result.deleted > 0
                ? `${result.deleted} old meal(s) deleted`
                : 'No meals older than 1 year'
              setError(msg)
              setTimeout(() => setError(prev => prev === msg ? null : prev), 3000)
            } catch {
              setError('Failed to delete old meals')
            }
          }}
        >
          🗑 Delete meals older than 1 year
        </button>
      </div>
    </div>
  )
}
