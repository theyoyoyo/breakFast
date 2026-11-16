import { useState, useEffect } from 'react'
import {
  getRatings, createRating, updateRating, deleteRating,
  getProfile, upsertProfile,
  getSupplements, createSupplement, updateSupplement, deleteSupplement,
  getMeals, updateMeal, deleteMeal, deleteOldMeals,
  getHealthRules, createHealthRule, updateHealthRule, deleteHealthRule,
  addFavorite, deleteFavorite,
  getPreferences, setPreference,
  analyzeMeal,
  getRemovedSuggestionCount, bringBackRemovedSuggestions,
} from '../services/api'
import WeeklySummary from './WeeklySummary'
import KitchenSettings from './KitchenSettings'
import ConfirmPrompt from './ConfirmPrompt'
import MealEditor from './MealEditor'
import StarRating from './StarRating'
import { THEMES, applyTheme, storedTheme } from '../utils/theme'
import { applyLanguage } from '../utils/language'
import { COUNTRIES, countryCode } from '../utils/countries'
import { useLanguage } from '../hooks/useLanguage'
import { useSyncNotice } from '../hooks/useSyncNotice'
import * as s from './SettingsPanel.styles'

// Display names for the stored supplement frequency values
const FREQUENCY_LABELS = { daily: 'Daily', sometimes: 'Occasional' }

// Profile numbers are typed in compact text boxes (no spinner), like the meal editor's amounts:
// whole numbers up to 3 digits, and weight with one decimal ("72.5"; a comma works too)
function cleanProfileNumber(field, value) {
  const text = value.replace(',', '.').replace(field === 'weight_kg' ? /[^\d.]/g : /\D/g, '')
  const [whole, ...decimals] = text.split('.')
  return decimals.length ? `${whole.slice(0, 3)}.${decimals.join('').slice(0, 1)}` : whole.slice(0, 3)
}

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
  const [profile, setProfile] = useState({ age: '', gender: '', height_cm: '', weight_kg: '', activity_level: '', country: '' })
  const [profileDirty, setProfileDirty] = useState(false)
  const [profileLoaded, setProfileLoaded] = useState(false)

  // Supplements state
  const [supplements, setSupplements] = useState([])
  const [newSuppName, setNewSuppName] = useState('')
  const [newSuppContents, setNewSuppContents] = useState('')
  // Supplement open in the ✏️ editor: { id, name, contents, frequency, error }
  const [editingSupp, setEditingSupp] = useState(null)

  // Meal history state
  const [meals, setMeals] = useState([])
  const [editingMealId, setEditingMealId] = useState(null)
  const [analyzingMealId, setAnalyzingMealId] = useState(null)
  const [expandedAnalysisId, setExpandedAnalysisId] = useState(null)
  const [llmFallbackLyric, setLlmFallbackLyric] = useState(null) // shown when LLM is down

  // Health rules state
  const [healthRules, setHealthRules] = useState([])
  const [newRuleText, setNewRuleText] = useState('')
  const [pendingRuleDeletes, setPendingRuleDeletes] = useState(new Set())

  // Meal pending deletes
  const [pendingMealDeletes, setPendingMealDeletes] = useState(new Set())

  // AI response language ('tr' = Turkish, 'en' = English) — saved per user, cached per device; units follow it
  const language = useLanguage()
  // Theme (orange / purple / green) — saved per user, cached per device
  const [theme, setTheme] = useState(storedTheme)

  // Weekly summary in suggestions toggle (default off)
  const [weeklySummaryInSuggestions, setWeeklySummaryInSuggestions] = useState(false)

  // Shopping suggestions removed with × that new suggestions leave out (7 days), and the open "Are you sure?"
  const [removedCount, setRemovedCount] = useState(0)
  const [askBringBack, setAskBringBack] = useState(false)

  // Delete meals older than one month: the open "Are you sure?", then the note with how many went
  const [askDeleteOld, setAskDeleteOld] = useState(false)
  const [oldMealsNote, setOldMealsNote] = useState(null)

  const loadRemovedCount = () => {
    getRemovedSuggestionCount().then(r => setRemovedCount(r.count)).catch(() => {})
  }

  const load = async () => {
    loadRemovedCount() // on its own, so a failure here doesn't fail the whole page
    try {
      setError(null)
      const [r, prof, supps, rules, m, prefs] = await Promise.all([
        getRatings(), getProfile(), getSupplements(), getHealthRules(), getMeals(), getPreferences(),
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
          country: prof.country ?? '',
        })
      }
      setSupplements(supps)
      setHealthRules(rules)
      setProfileDirty(false)
      setProfileLoaded(true)
      const langPref = prefs.find(p => p.key === 'response_language')
      applyLanguage(langPref?.value)
      if (!langPref) {
        // No preference stored yet — persist the default so the backend uses it
        setPreference('response_language', 'en').catch(() => {})
      }
      const weeklySummaryPref = prefs.find(p => p.key === 'weekly_summary_in_suggestions')
      setWeeklySummaryInSuggestions(weeklySummaryPref?.value === 'true')
      const themePref = prefs.find(p => p.key === 'theme')
      if (themePref) setTheme(applyTheme(themePref.value))
    } catch {
      setError('Failed to load settings')
    }
  }

  const handleLanguageToggle = async () => {
    const next = language === 'tr' ? 'en' : 'tr'
    applyLanguage(next)
    try {
      await setPreference('response_language', next)
    } catch {
      applyLanguage(language)
    }
  }

  const handleThemeChange = async (key) => {
    const previous = theme
    setTheme(applyTheme(key))
    try {
      await setPreference('theme', key)
    } catch {
      setTheme(applyTheme(previous))
    }
  }

  const handleWeeklySummaryToggle = async () => {
    const next = !weeklySummaryInSuggestions
    setWeeklySummaryInSuggestions(next)
    try {
      await setPreference('weekly_summary_in_suggestions', next ? 'true' : 'false')
    } catch {
      setWeeklySummaryInSuggestions(weeklySummaryInSuggestions)
    }
  }

  useEffect(() => { load() }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // Reload data when the Settings tab becomes visible
  useEffect(() => { if (visible) load() }, [visible]) // eslint-disable-line react-hooks/exhaustive-deps

  // Another device changed a supplement: reload only the supplements, so an unsaved profile edit stays
  useSyncNotice('supplements_updated', () => {
    getSupplements().then(setSupplements).catch(() => {})
  })

  // A × on any device, or the chat socket (re)opened: reload the removed suggestions count
  useSyncNotice(['shopping_suggestions_updated', 'sync_connected'], loadRemovedCount)

  const handleBringBack = async () => {
    setAskBringBack(false)
    try {
      setError(null)
      await bringBackRemovedSuggestions()
      setRemovedCount(0)
    } catch {
      setError('Failed to bring back removed suggestions')
    }
  }

  const handleDeleteOldMeals = async () => {
    setAskDeleteOld(false)
    try {
      setError(null)
      const result = await deleteOldMeals()
      setOldMealsNote(result.deleted > 0
        ? `${result.deleted} ${result.deleted === 1 ? 'meal' : 'meals'} older than one month deleted`
        : 'No meals older than one month')
    } catch {
      setOldMealsNote('Failed to delete old meals')
    }
  }

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

  const handleProfileNumber = (field, value) => handleProfileChange(field, cleanProfileNumber(field, value))

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
        country: profile.country || null,
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
      // New supplements start as Daily; the toggle on the row switches them
      await createSupplement(name, newSuppContents.trim(), 'daily')
      setNewSuppName('')
      setNewSuppContents('')
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

  // ✏️ editor: fix a supplement's name or contents without deleting it
  const handleSaveSupplementEdit = async () => {
    const name = editingSupp.name.trim()
    if (!name) return
    try {
      await updateSupplement(editingSupp.id, { name, contents: editingSupp.contents.trim(), frequency: editingSupp.frequency })
      setEditingSupp(null)
      load()
    } catch (e) {
      const error = String(e?.message).includes('409')
        ? 'Another supplement already has this name'
        : 'Failed to save supplement'
      setEditingSupp(prev => prev && { ...prev, error })
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
      setEditingMealId(null)
      setExpandedAnalysisId(prev => prev === meal.id ? null : prev) // clear expanded if this meal was open
      load()
    } catch {
      setError('Failed to update meal')
    }
  }

  const handleToggleMealDelete = (id) => {
    if (editingMealId === id) setEditingMealId(null)
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

  // Receives current editor state (not stale meal prop) via MealEditor's onFavorite;
  // returns the favorite's id, so a second tap on the star can remove it
  const handleCopyToFavorites = async (currentMeal) => {
    const { id } = await addFavorite({
      meal_name: currentMeal.menu_name || currentMeal.meal_name,
      description: currentMeal.description,
      ingredients: Array.isArray(currentMeal.ingredients) ? currentMeal.ingredients : [],
      steps: Array.isArray(currentMeal.steps) ? currentMeal.steps : [],
      prep_time_min: currentMeal.prep_time_min,
      nutrition_note: currentMeal.nutrition_note,
      menu_items: currentMeal.menu || currentMeal.menu_items || null,
    })
    return id
  }

  const handleAnalyzeMeal = async (meal) => {
    setAnalyzingMealId(meal.id)
    setLlmFallbackLyric(null)
    try {
      const result = await analyzeMeal(meal.meal_name, meal.ingredients, meal.id)
      if (result.fallback) {
        // LLM unavailable — show lyric, don't touch cached_nutrition so meal reverts to "Analyze"
        setLlmFallbackLyric(result.analysis_text)
      } else {
        setLlmFallbackLyric(null)
        setMeals(prev => prev.map(m =>
          m.id === meal.id
            ? { ...m, cached_nutrition: { analysis_text: result.analysis_text, analysis_data: result.analysis_data } }
            : m
        ))
      }
    } catch { /* network error — fail silently */ }
    setAnalyzingMealId(null)
  }

  const profileIncomplete = profileLoaded && (
    !profile.age || !profile.gender || !profile.height_cm || !profile.weight_kg || !profile.activity_level
  )
  const missingField = (val) => profileIncomplete && !val
    ? { borderColor: '#e74c3c' } : {}

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
        <div style={s.subPageHeader}>
          <button style={s.backBtn} onClick={() => { setPendingMealDeletes(new Set()); setLlmFallbackLyric(null); setView('settings') }}>←</button>
          <span>Meal History ({meals.length})</span>
        </div>
        <div style={s.body}>
          {error && <div style={s.error}>{error}</div>}
          {llmFallbackLyric && (
            <div style={{ fontSize: 12, color: 'var(--text-muted)', fontStyle: 'italic', padding: '8px 12px', background: 'var(--surface2)', borderRadius: 8, lineHeight: 1.5 }}>
              🎵 {llmFallbackLyric}
            </div>
          )}
          {meals.length === 0 && <span style={s.empty}>No meals logged yet</span>}
          {meals.map((meal) => {
            const markedForDelete = pendingMealDeletes.has(meal.id)
            const editing = editingMealId === meal.id
            const isMenuFormat = !!(meal.menu_items && meal.menu_items.length > 0)
            return (
              <div key={meal.id} style={{ ...s.mealCard, opacity: markedForDelete ? 0.4 : 1 }}>
                <div style={{ ...s.mealHeader, cursor: 'default' }}>
                  <div style={s.mealInfo}>
                    <span style={{ ...s.mealName, textDecoration: markedForDelete ? 'line-through' : 'none' }}>{meal.meal_name}</span>
                    <span style={s.mealDate}>{new Date(meal.logged_at).toLocaleDateString('tr-TR', { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' })}</span>
                  </div>
                  <div style={s.mealActions}>
                    {!markedForDelete && analyzingMealId === meal.id && (
                      <span style={{ fontSize: 11, color: 'var(--text-muted)', padding: '2px 4px' }}>Analyzing…</span>
                    )}
                    {!markedForDelete && analyzingMealId !== meal.id && !meal.cached_nutrition && (
                      <button
                        style={{ ...s.editMealBtn, fontSize: 11, padding: '2px 8px', color: 'var(--accent)' }}
                        onClick={(e) => { e.stopPropagation(); handleAnalyzeMeal(meal) }}
                      >
                        Analyze
                      </button>
                    )}
                    {!markedForDelete && analyzingMealId !== meal.id && meal.cached_nutrition && (
                      <button
                        style={{ ...s.editMealBtn, fontSize: 11, padding: '2px 8px', color: 'var(--accent)' }}
                        onClick={(e) => { e.stopPropagation(); setExpandedAnalysisId(expandedAnalysisId === meal.id ? null : meal.id) }}
                      >
                        Analysis {expandedAnalysisId === meal.id ? '▼' : '▶'}
                      </button>
                    )}
                    {!markedForDelete && (
                      <button style={s.editMealBtn} onClick={() => setEditingMealId(editing ? null : meal.id)} title="Edit meal">✏️</button>
                    )}
                    <button style={s.deleteMealBtn} onClick={(e) => { e.stopPropagation(); handleToggleMealDelete(meal.id) }} title={markedForDelete ? 'Undo delete' : 'Delete meal'}>
                      {markedForDelete ? '↩' : '🗑️'}
                    </button>
                  </div>
                </div>

                {/* Inline analysis dropdown */}
                {expandedAnalysisId === meal.id && meal.cached_nutrition && !markedForDelete && (() => {
                  const n = meal.cached_nutrition
                  const d = n.analysis_data
                  return (
                    <div style={s.analysisDropdown}>
                      {d?.macros && (
                        <div style={s.analysisMacroRow}>
                          {d.macros.calories_kcal != null && <span style={s.analysisMacroTag}>{d.macros.calories_kcal} kcal</span>}
                          {d.macros.protein_g != null && <span style={s.analysisMacroTag}>{d.macros.protein_g}g protein</span>}
                          {d.macros.carbs_g != null && <span style={s.analysisMacroTag}>{d.macros.carbs_g}g carbs</span>}
                          {d.macros.fat_g != null && <span style={s.analysisMacroTag}>{d.macros.fat_g}g fat</span>}
                          {d.macros.fiber_g != null && <span style={s.analysisMacroTag}>{d.macros.fiber_g}g fiber</span>}
                        </div>
                      )}
                      {(d?.narrative || n.analysis_text) && (
                        <div style={s.analysisNarrative}>
                          {d?.narrative || n.analysis_text?.replace(/`+json[\s\S]*?(`+|$)/g, '').trim()}
                        </div>
                      )}
                    </div>
                  )
                })()}

                {editing && !markedForDelete && (
                  <div style={s.overlay} onClick={(e) => { if (e.target === e.currentTarget) setEditingMealId(null) }}>
                    <div style={s.overlayPanel}>
                      <MealEditor
                        meal={{ ...meal, menu: meal.menu_items || undefined }}
                        onSave={(updated) => handleSaveMeal({ ...meal, ...updated })}
                        onClose={() => setEditingMealId(null)}
                        showPrepTime={true}
                        editPrepTime={true}
                        menuMode={isMenuFormat}
                        onFavorite={handleCopyToFavorites}
                        onUnfavorite={deleteFavorite}
                      />
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
        <div style={s.subPageHeader}>
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
        <div style={s.subPageHeader}>
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
      <div style={s.brandHeaderRow}>
        <span>break FAST</span>
        <span style={s.tabName}>Settings</span>
      </div>

      <div style={s.body}>
        {error && <div style={s.error}>{error}</div>}

        {/* Profile */}
        <div style={s.section}>
          <div style={s.sectionLabel}>
            Profile
            {profileIncomplete && <span style={{ color: '#e74c3c', marginLeft: 6, fontSize: 10 }}>●</span>}
          </div>
          {/* Age + Gender and Height + Weight: four in a row where they fit, two by two on a phone */}
          <div style={s.profileRow}>
            <div style={s.profilePair}>
              <div style={s.profileField}>
                <label style={s.profileLabel} htmlFor="profile-age">Age</label>
                <div style={s.profileInputRow}>
                  <input
                    id="profile-age"
                    type="text"
                    inputMode="numeric"
                    style={{ ...s.profileNumber(3), ...missingField(profile.age) }}
                    value={profile.age}
                    onChange={(e) => handleProfileNumber('age', e.target.value)}
                    placeholder="—"
                  />
                  {profile.age !== '' && <button style={s.clearFieldBtn} onClick={() => handleClearProfileField('age')}>×</button>}
                </div>
              </div>
              <div style={s.profileField}>
                <label style={s.profileLabel} htmlFor="profile-gender">Gender</label>
                <select
                  id="profile-gender"
                  style={{ ...s.profileSelect, ...missingField(profile.gender) }}
                  value={profile.gender}
                  onChange={(e) => handleProfileChange('gender', e.target.value)}
                >
                  <option value="">—</option>
                  <option value="male">Male</option>
                  <option value="female">Female</option>
                </select>
              </div>
            </div>
            <div style={s.profilePair}>
              <div style={s.profileField}>
                <label style={s.profileLabel} htmlFor="profile-height">Height (cm)</label>
                <div style={s.profileInputRow}>
                  <input
                    id="profile-height"
                    type="text"
                    inputMode="numeric"
                    style={{ ...s.profileNumber(3), ...missingField(profile.height_cm) }}
                    value={profile.height_cm}
                    onChange={(e) => handleProfileNumber('height_cm', e.target.value)}
                    placeholder="—"
                  />
                  {profile.height_cm !== '' && <button style={s.clearFieldBtn} onClick={() => handleClearProfileField('height_cm')}>×</button>}
                </div>
              </div>
              <div style={s.profileField}>
                <label style={s.profileLabel} htmlFor="profile-weight">Weight (kg)</label>
                <div style={s.profileInputRow}>
                  <input
                    id="profile-weight"
                    type="text"
                    inputMode="decimal"
                    style={{ ...s.profileNumber(5), ...missingField(profile.weight_kg) }}
                    value={profile.weight_kg}
                    onChange={(e) => handleProfileNumber('weight_kg', e.target.value)}
                    placeholder="—"
                  />
                  {profile.weight_kg !== '' && <button style={s.clearFieldBtn} onClick={() => handleClearProfileField('weight_kg')}>×</button>}
                </div>
              </div>
            </div>
          </div>
          <div style={s.profileWideRow}>
            <div style={s.profileWideField}>
              <label style={s.profileLabel} htmlFor="profile-activity">Activity Level</label>
              <select
                id="profile-activity"
                style={{ ...s.profileWideSelect, ...missingField(profile.activity_level) }}
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
            {/* Optional: tells the AI what's in season; not part of the incomplete-profile dot.
                The list shows "Germany (DE)", the closed box only "DE"; the name is what's saved. */}
            <div style={s.profileField}>
              <label style={s.profileLabel} htmlFor="profile-country">Country</label>
              <span style={s.countryPicker}>
                <span style={s.countryText} aria-hidden="true">
                  {countryCode(profile.country) || profile.country || '—'}
                </span>
                <span aria-hidden="true">▾</span>
                <select
                  id="profile-country"
                  style={s.countrySelect}
                  value={profile.country}
                  onChange={(e) => handleProfileChange('country', e.target.value)}
                >
                  <option value="">—</option>
                  {profile.country && !countryCode(profile.country) && (
                    <option value={profile.country}>{profile.country}</option>
                  )}
                  {COUNTRIES.map(({ name, code }) => <option key={code} value={name}>{name} ({code})</option>)}
                </select>
              </span>
            </div>
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
              <button
                style={s.suppFreq(sup.frequency)}
                onClick={() => handleToggleFrequency(sup)}
                title="Tap to switch between Daily and Occasional"
              >{FREQUENCY_LABELS[sup.frequency] || sup.frequency}</button>
              <button
                style={s.editBtn}
                onClick={() => setEditingSupp({ id: sup.id, name: sup.name, contents: sup.contents || '', frequency: sup.frequency, error: null })}
                title="Edit supplement"
              >✏️</button>
              <button style={s.tagX} onClick={() => handleDeleteSupplement(sup.id)}>×</button>
            </div>
          ))}
          {editingSupp && (
            <div style={s.overlay} onClick={(e) => { if (e.target === e.currentTarget) setEditingSupp(null) }}>
              <div style={s.overlayPanel}>
                <div style={s.overlayTitle}>Edit supplement</div>
                <div style={s.overlayForm}>
                  <label style={s.profileLabel} htmlFor="supp-edit-name">Name</label>
                  <input
                    id="supp-edit-name"
                    style={s.input}
                    value={editingSupp.name}
                    onChange={(e) => setEditingSupp(prev => ({ ...prev, name: e.target.value, error: null }))}
                    autoFocus
                  />
                  <label style={s.profileLabel} htmlFor="supp-edit-contents">Contents</label>
                  <input
                    id="supp-edit-contents"
                    style={s.input}
                    value={editingSupp.contents}
                    onChange={(e) => setEditingSupp(prev => ({ ...prev, contents: e.target.value, error: null }))}
                    onKeyDown={(e) => e.key === 'Enter' && handleSaveSupplementEdit()}
                    placeholder="e.g. Vitamin D3 1000IU, K2 100mcg, Zinc 15mg"
                  />
                  {editingSupp.error && <div style={s.error}>{editingSupp.error}</div>}
                </div>
                <div style={s.overlayActions}>
                  <button style={s.overlayCloseBtn} onClick={() => setEditingSupp(null)}>Close</button>
                  <button
                    style={s.overlaySaveBtn}
                    onClick={handleSaveSupplementEdit}
                    disabled={!editingSupp.name.trim()}
                  >Save</button>
                </div>
              </div>
            </div>
          )}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <div style={s.addRow}>
              <input
                style={s.input}
                value={newSuppName}
                onChange={(e) => setNewSuppName(e.target.value)}
                placeholder="Supplement name…"
              />
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

        {/* AI settings: reply language, weekly review, removed shopping suggestions */}
        <div style={s.section}>
          <div style={s.sectionLabel}>AI settings</div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginTop: 8 }}>
            <span style={{ fontSize: 13, color: language === 'en' ? 'var(--accent)' : 'var(--text-muted)' }}>English</span>
            <button
              style={{
                width: 44, height: 24, borderRadius: 12, border: '1px solid var(--border)',
                background: language === 'tr' ? 'var(--accent)' : 'var(--surface2)',
                cursor: 'pointer', position: 'relative', transition: 'background 0.2s',
              }}
              onClick={handleLanguageToggle}
              title={`Switch to ${language === 'en' ? 'Turkish' : 'English'}`}
            >
              <span style={{
                position: 'absolute', top: 3, width: 16, height: 16, borderRadius: 8,
                background: '#fff', transition: 'left 0.2s',
                left: language === 'tr' ? 24 : 4,
              }} />
            </button>
            <span style={{ fontSize: 13, color: language === 'tr' ? 'var(--accent)' : 'var(--text-muted)' }}>Turkish</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginTop: 12 }}>
            <span style={{ fontSize: 13, color: 'var(--text-muted)', flex: 1 }}>Weekly review in suggestions</span>
            <button
              style={{
                width: 44, height: 24, borderRadius: 12, border: '1px solid var(--border)',
                background: weeklySummaryInSuggestions ? 'var(--accent)' : 'var(--surface2)',
                cursor: 'pointer', position: 'relative', transition: 'background 0.2s',
              }}
              onClick={handleWeeklySummaryToggle}
              title={weeklySummaryInSuggestions ? 'Disable' : 'Enable'}
            >
              <span style={{
                position: 'absolute', top: 3, width: 16, height: 16, borderRadius: 8,
                background: '#fff', transition: 'left 0.2s',
                left: weeklySummaryInSuggestions ? 24 : 4,
              }} />
            </button>
          </div>
          {/* Items removed with × stay out of shopping suggestions for 7 days; this lets them back sooner */}
          <div style={s.aiRow}>
            <span style={s.aiRowLabel}>Removed shopping suggestions</span>
            <button
              style={s.bringBackBtn(removedCount > 0)}
              disabled={removedCount === 0}
              onClick={() => setAskBringBack(true)}
            >
              Bring back ({removedCount})
            </button>
          </div>
          {askBringBack && removedCount > 0 && (
            <div style={s.bringBackPrompt}>
              <ConfirmPrompt
                label="Bring back removed suggestions"
                message={`Are you sure you want to allow ${removedCount} removed ${removedCount === 1 ? 'item' : 'items'} back in suggestions?`}
                confirmLabel="Allow"
                onConfirm={handleBringBack}
                onCancel={() => setAskBringBack(false)}
              />
            </div>
          )}
        </div>

        {/* Theme — only the accent colors change */}
        <div style={s.section}>
          <div style={s.sectionLabel}>Theme</div>
          <div style={s.themeRow}>
            {THEMES.map(t => (
              <button
                key={t.key}
                style={s.themeBtn(theme === t.key)}
                onClick={() => handleThemeChange(t.key)}
                aria-pressed={theme === t.key}
              >
                <span style={s.themeSwatch(t.swatch)} />
                {t.label}
              </button>
            ))}
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
          onClick={() => { setOldMealsNote(null); setAskDeleteOld(true) }}
        >
          🗑 Delete meals older than one month
        </button>
        {askDeleteOld && (
          <div style={s.bringBackPrompt}>
            <ConfirmPrompt
              label="Delete old meals"
              message="Are you sure you want to delete every meal older than one month?"
              confirmLabel="Delete"
              danger
              onConfirm={handleDeleteOldMeals}
              onCancel={() => setAskDeleteOld(false)}
            />
          </div>
        )}
        {oldMealsNote && <div style={s.oldMealsNote}>{oldMealsNote}</div>}
      </div>
    </div>
  )
}
