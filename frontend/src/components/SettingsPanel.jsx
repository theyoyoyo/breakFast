import { useState, useEffect } from 'react'
import {
  getRatings, createRating, updateRating, deleteRating,
  getProfile, upsertProfile,
  getSupplements, createSupplement, updateSupplement, deleteSupplement,
  getMeals, updateMeal, deleteMeal, deleteOldMeals,
  getHealthRules, createHealthRule, updateHealthRule, deleteHealthRule,
  getFavorites, addFavorite, deleteFavorite,
} from '../services/api'
import WeeklySummary from './WeeklySummary'
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
  const [mealItems, setMealItems] = useState([])
  const [mealName, setMealName] = useState('')
  const [newMealItem, setNewMealItem] = useState('')
  const [favIds, setFavIds] = useState({}) // { mealName: favId } for quick lookup

  // Health rules state
  const [healthRules, setHealthRules] = useState([])
  const [newRuleText, setNewRuleText] = useState('')
  const [pendingRuleDeletes, setPendingRuleDeletes] = useState(new Set())

  // Meal pending deletes
  const [pendingMealDeletes, setPendingMealDeletes] = useState(new Set())

  const load = async () => {
    try {
      setError(null)
      const [r, prof, supps, rules, m, favs] = await Promise.all([
        getRatings(), getProfile(), getSupplements(), getHealthRules(), getMeals(), getFavorites(),
      ])
      setRatings(r)
      setMeals(m)
      // Build a lookup: meal_name -> fav id (for the star toggle in meal history)
      const favLookup = {}
      for (const f of favs) { favLookup[f.meal_name] = f.id }
      setFavIds(favLookup)
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
    setMealName(meal.meal_name)
    // Normalize ingredients to structured form
    const normalized = (meal.ingredients || []).map(item => {
      if (typeof item === 'object' && item !== null && item.name) {
        return { name: item.name, quantity: item.quantity ?? 1, unit: item.unit || 'adet' }
      }
      return { name: String(item), quantity: 1, unit: 'adet' }
    })
    setMealItems(normalized)
    setNewMealItem('')
  }

  const handleDeleteMealItem = (idx) => {
    setMealItems(prev => prev.filter((_, i) => i !== idx))
  }

  const handleMealQtyChange = (idx, val) => {
    if (val !== '' && !/^\d*\.?\d{0,2}$/.test(val)) return
    setMealItems(prev => prev.map((item, i) =>
      i === idx ? { ...item, quantity: val === '' ? '' : val } : item
    ))
  }

  const handleMealQtyBlur = (idx) => {
    setMealItems(prev => prev.map((item, i) => {
      if (i !== idx) return item
      const num = parseFloat(item.quantity)
      return { ...item, quantity: (!isNaN(num) && num > 0) ? Math.round(num * 100) / 100 : 1 }
    }))
  }

  const handleMealQtyStep = (idx, delta) => {
    setMealItems(prev => prev.map((item, i) => {
      if (i !== idx) return item
      const current = typeof item.quantity === 'number' ? item.quantity : parseFloat(item.quantity) || 1
      const next = Math.round((current + delta) * 100) / 100
      return { ...item, quantity: next > 0 ? next : current }
    }))
  }

  const handleAddMealItem = () => {
    const v = newMealItem.trim()
    if (!v) return
    const itemName = (item) => typeof item === 'object' ? item.name : item
    if (mealItems.some(item => itemName(item).toLowerCase() === v.toLowerCase())) return
    setMealItems(prev => [...prev, { name: v, quantity: 1, unit: 'adet' }])
    setNewMealItem('')
  }

  const handleSaveMeal = async (meal) => {
    try {
      setError(null)
      await updateMeal(meal.id, {
        meal_name: mealName,
        ingredients: mealItems,
        description: meal.description,
        steps: meal.steps,
        prep_time_min: meal.prep_time_min,
        nutrition_note: meal.nutrition_note,
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

  const handleToggleMealFavorite = async (meal) => {
    const existing = favIds[meal.meal_name]
    try {
      if (existing) {
        await deleteFavorite(existing)
        setFavIds(prev => { const next = { ...prev }; delete next[meal.meal_name]; return next })
      } else {
        const ingredients = Array.isArray(meal.ingredients) ? meal.ingredients : []
        const result = await addFavorite({
          meal_name: meal.meal_name,
          description: meal.description,
          ingredients,
          steps: Array.isArray(meal.steps) ? meal.steps : [],
          prep_time_min: meal.prep_time_min,
          nutrition_note: meal.nutrition_note,
        })
        setFavIds(prev => ({ ...prev, [meal.meal_name]: result.id }))
      }
    } catch { /* ignore */ }
  }

  // --- Weekly Summary sub-page ---
  if (view === 'weekly') {
    return <WeeklySummary onBack={() => setView('settings')} />
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
                    <div style={s.mealNameEdit}>
                      <label style={s.mealFieldLabel}>Name</label>
                      <input
                        style={s.input}
                        value={mealName}
                        onChange={(e) => setMealName(e.target.value)}
                      />
                    </div>

                    <label style={s.mealFieldLabel}>Ingredients</label>
                    <div style={s.mealItemList}>
                      {mealItems.map((item, idx) => (
                        <div key={idx} style={s.mealItemRow}>
                          <div style={s.mealQtyGroup}>
                            <button style={s.mealArrowBtn} onClick={() => handleMealQtyStep(idx, -1)}>▼</button>
                            <input
                              style={s.mealQtyInput}
                              type="text"
                              inputMode="decimal"
                              value={item.quantity}
                              onChange={(e) => handleMealQtyChange(idx, e.target.value)}
                              onBlur={() => handleMealQtyBlur(idx)}
                            />
                            <button style={s.mealArrowBtn} onClick={() => handleMealQtyStep(idx, 1)}>▲</button>
                          </div>
                          <span style={s.mealUnitLabel}>{item.unit}</span>
                          <span style={s.mealItemText}>{item.name}</span>
                          <div style={s.mealItemActions}>
                            <button style={s.deleteMealBtn} onClick={() => handleDeleteMealItem(idx)} title="Delete">🗑️</button>
                          </div>
                        </div>
                      ))}
                    </div>

                    <div style={s.addRow}>
                      <input
                        style={s.input}
                        value={newMealItem}
                        onChange={(e) => setNewMealItem(e.target.value)}
                        onKeyDown={(e) => e.key === 'Enter' && handleAddMealItem()}
                        placeholder="Add item…"
                      />
                      <button style={s.addBtn} onClick={handleAddMealItem}>+</button>
                    </div>

                    <div style={{ display: 'flex', gap: 6, marginTop: 8, alignItems: 'center' }}>
                      <button style={s.saveBtn} onClick={() => handleSaveMeal(meal)}>Save</button>
                      <button
                        style={s.favToggle(!!favIds[meal.meal_name])}
                        onClick={() => handleToggleMealFavorite(meal)}
                        title={favIds[meal.meal_name] ? 'Remove from favorites' : 'Add to favorites'}
                      >
                        {favIds[meal.meal_name] ? '⭐' : '☆'}
                      </button>
                      <button style={s.cancelEditBtn} onClick={() => setExpandedMealId(null)}>Cancel</button>
                    </div>
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
              <span style={s.suppName}>{sup.name}</span>
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
