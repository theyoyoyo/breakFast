import { useState, useEffect } from 'react'
import { normalizeItem, unitsFor, countUnit, localizeUnit, resolveUnit, rememberUnit } from '../utils/ingredients'
import { checkMissingIngredients } from '../services/api'
import { useLanguage } from '../hooks/useLanguage'
import * as s from './MealEditor.styles'

const MISSING_HINT = 'Not in your fridge — tap once you have it'
const OBTAINED_HINT = 'Marked as obtained — tap to undo'
const TEMPLATE_MISSING_HINT = 'Not in your fridge'
const DISH_MISSING_HINT = 'Some ingredients are not in your fridge'
const DISH_OBTAINED_HINT = 'Missing ingredients are marked as obtained'

/**
 * Shared meal editor component used by MealBlock, FavoritesPanel, and SettingsPanel.
 *
 * Props:
 *   meal         — meal object { meal_name, ingredients, menu, steps, prep_time_min, ... }
 *   onSave       — (updatedMeal) => void — called with the edited meal; no Save button without it
 *   onClose      — () => void — close the editor
 *   showPrepTime — boolean — whether to show prep_time_min input (default true)
 *   editPrepTime — boolean — whether prep time is editable (default true)
 *   extraActions — ReactNode — extra buttons to render in the actions row
 *   showId       — boolean — show meal ID badge (default false)
 *   menuMode     — boolean — edit meal.menu (multi-item) instead of meal.ingredients
 *   checkFridge  — boolean — underline ingredients that aren't in the fridge (checked by the backend);
 *                  tapping one marks it as obtained for this meal (green), saved as meal.obtained
 *   canMarkObtained — boolean — allow tapping missing items to mark them as obtained (default true);
 *                  off for templates like favorites, where items are only underlined
 *   onMissingChange — (names) => void — missing ingredients not marked as obtained, after each check
 *   onChange     — (currentMeal) => void — called with the live editor state after each change
 *
 * extraActions may be a function: (buildCurrentMeal, { markAllObtained }) => ReactNode
 */
export default function MealEditor({
  meal,
  onSave,
  onClose,
  showPrepTime = true,
  editPrepTime = true,
  extraActions,
  showId = false,
  menuMode = false,
  onFavorite,        // (currentMeal) => void — called with current editor state
  checkFridge = false,
  canMarkObtained = true,
  onMissingChange,
  onChange,
}) {
  const [items, setItems] = useState(() => initItems(meal, menuMode))
  const [mealName, setMealName] = useState(meal?.meal_name || meal?.menu_name || 'Meal')
  const [prepTime, setPrepTime] = useState(meal?.prep_time_min ?? '')
  const [newItem, setNewItem] = useState('')
  const [openDishIdx, setOpenDishIdx] = useState(null)
  const [newSubItem, setNewSubItem] = useState('')
  const [favSaving, setFavSaving] = useState(false)
  const [favAdded, setFavAdded] = useState(false)
  // Missing ingredients the user marked as obtained for this meal (yellow → green)
  const [obtained, setObtained] = useState(() => new Set(meal?.obtained || []))
  // Units follow the AI language: known ones are shown in it, unknown ones as written
  const language = useLanguage()
  const units = unitsFor(language)

  useEffect(() => {
    setItems(initItems(meal, menuMode))
    setMealName(meal?.meal_name || meal?.menu_name || 'Meal')
    setPrepTime(meal?.prep_time_min ?? '')
    setNewItem('')
    setOpenDishIdx(null)
    setNewSubItem('')
    setFavAdded(false)
    setObtained(new Set(meal?.obtained || []))
  }, [meal, menuMode])

  // Ask the backend which ingredients aren't in the fridge — on open and shortly after each edit.
  // null until the first answer, so nothing is reported (or unblocked) before the check is done.
  const [missing, setMissing] = useState(null)
  useEffect(() => {
    if (!checkFridge) return
    let cancelled = false
    const timer = setTimeout(async () => {
      let names = []
      try {
        const res = await checkMissingIngredients(menuMode ? { menu: items } : { ingredients: items })
        names = res?.missing || []
      } catch { /* offline — don't flag anything */ }
      if (!cancelled) setMissing(new Set(names))
    }, 300)
    return () => { cancelled = true; clearTimeout(timer) }
  }, [checkFridge, items, menuMode])

  // Report what still blocks the meal: missing and not marked as obtained
  useEffect(() => {
    if (missing) onMissingChange?.([...missing].filter(name => !(canMarkObtained && obtained.has(name))))
  }, [missing, obtained]) // eslint-disable-line react-hooks/exhaustive-deps

  const key = (name) => (name || '').trim()
  const isMissing = (name) => !!missing?.has(key(name))
  const isObtained = (name) => canMarkObtained && obtained.has(key(name))
  const toggleObtained = (name) => setObtained(prev => {
    const next = new Set(prev)
    if (next.has(key(name))) next.delete(key(name))
    else next.add(key(name))
    return next
  })
  const markAllObtained = () => {
    if (canMarkObtained) setObtained(prev => new Set([...prev, ...(missing || [])]))
  }

  // Missing names are tappable: yellow until marked as obtained, then green
  // (templates only show the yellow underline)
  const nameProps = (name, extraStyle = {}) => {
    if (!isMissing(name)) return { style: { ...s.itemText, ...extraStyle } }
    if (!canMarkObtained) {
      return { style: { ...s.itemText, ...extraStyle, ...s.missingName() }, title: TEMPLATE_MISSING_HINT }
    }
    const got = isObtained(name)
    return {
      style: { ...s.itemText, ...extraStyle, ...s.missingName({ obtained: got }), cursor: 'pointer' },
      title: got ? OBTAINED_HINT : MISSING_HINT,
      role: 'button',
      onClick: () => toggleObtained(name),
    }
  }

  // ── Top-level item handlers ──────────────────────────────────────────────

  const handleDelete = (idx) => {
    if (openDishIdx === idx) setOpenDishIdx(null)
    else if (openDishIdx !== null && openDishIdx > idx) setOpenDishIdx(i => i - 1)
    setItems(prev => prev.filter((_, i) => i !== idx))
  }

  const handleQtyChange = (idx, val) => {
    if (val !== '' && !/^\d*\.?\d{0,2}$/.test(val)) return
    const key = menuMode ? 'amount' : 'quantity'
    setItems(prev => prev.map((item, i) =>
      i === idx ? { ...item, [key]: val === '' ? '' : val } : item
    ))
  }

  const handleQtyBlur = (idx) => {
    const key = menuMode ? 'amount' : 'quantity'
    setItems(prev => prev.map((item, i) => {
      if (i !== idx) return item
      const num = parseFloat(item[key])
      return { ...item, [key]: (!isNaN(num) && num > 0) ? Math.round(num * 100) / 100 : 1 }
    }))
  }

  const handleQtyStep = (idx, delta) => {
    const key = menuMode ? 'amount' : 'quantity'
    setItems(prev => prev.map((item, i) => {
      if (i !== idx) return item
      const cur = typeof item[key] === 'number' ? item[key] : parseFloat(item[key]) || 1
      const next = Math.round((cur + delta) * 100) / 100
      return { ...item, [key]: next > 0 ? next : cur }
    }))
  }

  const handleAdd = (isDish = false) => {
    const v = newItem.trim()
    if (!v) return
    if (items.some(item => item.name.toLowerCase() === v.toLowerCase())) return
    const entry = menuMode
      ? (isDish
        ? { name: v, ingredients: [] }
        : { name: v, amount: 1, unit: resolveUnit(v, language), ingredients: [] })
      : { name: v, quantity: 1, unit: resolveUnit(v, language) }
    setItems(prev => [...prev, entry])
    setNewItem('')
  }

  // ── Dish toggle ──────────────────────────────────────────────────────────

  const toggleDish = (idx) => {
    setOpenDishIdx(prev => prev === idx ? null : idx)
    setNewSubItem('')
  }

  // ── Sub-ingredient handlers ──────────────────────────────────────────────

  const updateSubs = (dishIdx, fn) =>
    setItems(prev => prev.map((item, i) =>
      i === dishIdx ? { ...item, ingredients: fn(item.ingredients || []) } : item
    ))

  const handleSubDelete = (dishIdx, subIdx) =>
    updateSubs(dishIdx, subs => subs.filter((_, i) => i !== subIdx))

  const handleSubQtyChange = (dishIdx, subIdx, val) => {
    if (val !== '' && !/^\d*\.?\d{0,2}$/.test(val)) return
    updateSubs(dishIdx, subs => subs.map((s, i) =>
      i === subIdx ? { ...s, amount: val === '' ? '' : val } : s
    ))
  }

  const handleSubQtyBlur = (dishIdx, subIdx) =>
    updateSubs(dishIdx, subs => subs.map((s, i) => {
      if (i !== subIdx) return s
      const num = parseFloat(s.amount)
      return { ...s, amount: (!isNaN(num) && num > 0) ? Math.round(num * 100) / 100 : 1 }
    }))

  const handleSubQtyStep = (dishIdx, subIdx, delta) =>
    updateSubs(dishIdx, subs => subs.map((s, i) => {
      if (i !== subIdx) return s
      const cur = typeof s.amount === 'number' ? s.amount : parseFloat(s.amount) || 1
      const next = Math.round((cur + delta) * 100) / 100
      return { ...s, amount: next > 0 ? next : cur }
    }))

  const handleSubAdd = (dishIdx) => {
    const v = newSubItem.trim()
    if (!v) return
    updateSubs(dishIdx, subs => {
      if (subs.some(s => s.name.toLowerCase() === v.toLowerCase())) return subs
      return [...subs, { name: v, amount: 1, unit: resolveUnit(v, language) }]
    })
    setNewSubItem('')
  }

  // ── Unit change (saves preference to localStorage) ───────────────────────

  const handleUnitChange = (idx, unit) => {
    setItems(prev => prev.map((item, i) => {
      if (i !== idx) return item
      rememberUnit(item.name, unit)
      return { ...item, unit }
    }))
  }

  const handleSubUnitChange = (dishIdx, subIdx, unit) => {
    updateSubs(dishIdx, subs => subs.map((s, i) => {
      if (i !== subIdx) return s
      rememberUnit(s.name, unit)
      return { ...s, unit }
    }))
  }

  // ── Prep time ────────────────────────────────────────────────────────────

  const handlePrepTimeChange = (val) => {
    if (val === '') { setPrepTime(''); return }
    const num = parseInt(val, 10)
    if (!isNaN(num) && num >= 0 && num <= 999) setPrepTime(num)
  }

  // ── Build + Save ─────────────────────────────────────────────────────────

  const buildCurrentMeal = () => {
    const finalPrepTime = typeof prepTime === 'number' ? prepTime : (parseInt(prepTime, 10) || null)
    const name = mealName.trim() || meal?.meal_name || meal?.menu_name || 'Meal'
    // Keep obtained marks only for names still in the meal
    const names = new Set(items.flatMap(item => [item.name, ...(item.ingredients || []).map(sub => sub.name)]).map(key))
    const keptObtained = [...obtained].filter(n => names.has(n))
    if (menuMode) {
      const finalMenu = items.map(item => {
        if (isSimpleItem(item)) {
          const num = parseFloat(item.amount)
          return { ...item, amount: (!isNaN(num) && num > 0) ? Math.round(num * 100) / 100 : 1 }
        }
        return item
      })
      return { ...meal, meal_name: name, menu_name: name, menu: finalMenu, menu_items: finalMenu, prep_time_min: finalPrepTime, obtained: keptObtained }
    } else {
      const finalItems = items.map(item => ({
        ...item,
        quantity: (() => {
          const num = parseFloat(item.quantity)
          return (!isNaN(num) && num > 0) ? Math.round(num * 100) / 100 : 1
        })(),
      }))
      return { ...meal, meal_name: name, ingredients: finalItems, prep_time_min: finalPrepTime, obtained: keptObtained }
    }
  }

  // Live state for callers that keep a draft ("Today I ate")
  useEffect(() => {
    onChange?.(buildCurrentMeal())
  }, [items, mealName, prepTime, obtained]) // eslint-disable-line react-hooks/exhaustive-deps

  const handleSave = () => onSave?.(buildCurrentMeal())

  const handleFavorite = async () => {
    setFavSaving(true)
    try {
      await onFavorite?.(buildCurrentMeal())
      setFavAdded(true)
    } catch { /* ignore */ }
    setFavSaving(false)
  }

  // ── Render ───────────────────────────────────────────────────────────────

  return (
    <div style={s.editorContainer}>
      <div style={s.editorHeader}>
        <input
          style={s.nameInput}
          value={mealName}
          onChange={(e) => { if (e.target.value.length <= 100) setMealName(e.target.value) }}
          onBlur={() => { if (!mealName.trim()) setMealName(meal?.meal_name || meal?.menu_name || 'Meal') }}
          placeholder="Meal name"
        />
        {showId && <span style={s.mealId}>#{meal?.id || 0}</span>}
        {showPrepTime && (
          <div style={s.prepTimeGroup}>
            <span style={s.prepTimeLabel}>⏱</span>
            {editPrepTime ? (
              <input
                style={s.prepTimeInput}
                type="text"
                inputMode="numeric"
                value={prepTime}
                onChange={(e) => handlePrepTimeChange(e.target.value)}
                placeholder="—"
              />
            ) : (
              <span style={s.prepTimeValue}>{prepTime || '—'}</span>
            )}
            <span style={s.prepTimeUnit}>m</span>
          </div>
        )}
      </div>

      <div style={s.itemList}>
        {items.map((item, idx) => {
          const isDish = menuMode && !isSimpleItem(item)
          const isOpen = openDishIdx === idx
          // A dish's mark sums up its hidden sub-ingredients: dotted yellow if any still missing,
          // dotted green if all missing ones are marked as obtained
          const subsMissing = isDish ? (item.ingredients || []).filter(sub => isMissing(sub.name)) : []
          const subsResolved = subsMissing.every(sub => isObtained(sub.name))
          const dishNameMissing = isDish && isMissing(item.name)

          return (
            <div key={idx}>
              {isDish ? (
                // ── Dish row ──────────────────────────────────────────────
                <div style={s.itemRow}>
                  <span style={s.dishBadge}>🍳</span>
                  {dishNameMissing ? (
                    <span {...nameProps(item.name, { fontWeight: 500 })}>{item.name}</span>
                  ) : (
                    <span
                      style={{
                        ...s.itemText,
                        fontWeight: 500,
                        ...(subsMissing.length ? s.missingName({ dotted: true, obtained: subsResolved }) : {}),
                      }}
                      title={subsMissing.length ? (subsResolved ? DISH_OBTAINED_HINT : DISH_MISSING_HINT) : undefined}
                    >{item.name}</span>
                  )}
                  <div style={s.itemActions}>
                    <button
                      style={s.expandBtn(isOpen)}
                      onClick={() => toggleDish(idx)}
                      title={isOpen ? 'Close ingredients' : 'Edit ingredients'}
                    >
                      {isOpen ? '▲ Ingredients' : '▶ Ingredients'}
                    </button>
                    <button style={s.deleteBtn} onClick={() => handleDelete(idx)} title="Delete">🗑️</button>
                  </div>
                </div>
              ) : (
                // ── Simple item row ───────────────────────────────────────
                <div style={s.itemRow}>
                  <div style={s.qtyGroup}>
                    <button style={s.arrowBtn} onClick={() => handleQtyStep(idx, -1)}>▼</button>
                    <input
                      style={s.qtyInput}
                      type="text"
                      inputMode="decimal"
                      value={menuMode ? (item.amount ?? 1) : item.quantity}
                      onChange={(e) => handleQtyChange(idx, e.target.value)}
                      onBlur={() => handleQtyBlur(idx)}
                    />
                    <button style={s.arrowBtn} onClick={() => handleQtyStep(idx, 1)}>▲</button>
                  </div>
                  <UnitSelect unit={item.unit} units={units} language={language} onChange={(unit) => handleUnitChange(idx, unit)} />
                  <span {...nameProps(item.name)}>{item.name}</span>
                  <div style={s.itemActions}>
                    <button style={s.deleteBtn} onClick={() => handleDelete(idx)} title="Delete">🗑️</button>
                  </div>
                </div>
              )}

              {/* ── Sub-ingredient dropdown (dish only) ─────────────────── */}
              {isDish && isOpen && (
                <div style={s.subList}>
                  {(item.ingredients || []).map((sub, si) => (
                    <div key={si} style={s.subRow}>
                      <div style={s.qtyGroup}>
                        <button style={s.arrowBtn} onClick={() => handleSubQtyStep(idx, si, -1)}>▼</button>
                        <input
                          style={s.qtyInput}
                          type="text"
                          inputMode="decimal"
                          value={sub.amount ?? 1}
                          onChange={(e) => handleSubQtyChange(idx, si, e.target.value)}
                          onBlur={() => handleSubQtyBlur(idx, si)}
                        />
                        <button style={s.arrowBtn} onClick={() => handleSubQtyStep(idx, si, 1)}>▲</button>
                      </div>
                      <UnitSelect unit={sub.unit} units={units} language={language} onChange={(unit) => handleSubUnitChange(idx, si, unit)} />
                      <span {...nameProps(sub.name)}>{sub.name}</span>
                      <div style={s.itemActions}>
                        <button style={s.deleteBtn} onClick={() => handleSubDelete(idx, si)} title="Delete">🗑️</button>
                      </div>
                    </div>
                  ))}
                  {/* Always-visible add field at the bottom of the dropdown */}
                  <div style={s.subAddRow}>
                    <input
                      style={s.addInput}
                      value={newSubItem}
                      onChange={(e) => setNewSubItem(e.target.value)}
                      onKeyDown={(e) => e.key === 'Enter' && handleSubAdd(idx)}
                      placeholder="Add ingredient…"
                      autoFocus
                    />
                    <button style={s.addBtn} onClick={() => handleSubAdd(idx)}>＋ Item</button>
                  </div>
                </div>
              )}
            </div>
          )
        })}
      </div>

      <div style={s.addRow}>
        <input
          style={s.addInput}
          value={newItem}
          onChange={(e) => setNewItem(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleAdd(false)}
          placeholder={menuMode ? 'Item or dish name…' : 'Add item…'}
        />
        {menuMode ? (
          <>
            <button style={s.addBtn} onClick={() => handleAdd(false)} title="Add simple item (peynir, zeytin…)">＋ Item</button>
            <button style={s.addBtn} onClick={() => handleAdd(true)} title="Add complex dish (menemen, omlet…)">＋ Dish</button>
          </>
        ) : (
          <button style={s.addBtn} onClick={() => handleAdd(false)}>+</button>
        )}
      </div>

      <div style={s.actions}>
        <button style={s.closeBtn} onClick={onClose}>Close</button>
        {typeof extraActions === 'function' ? extraActions(buildCurrentMeal, { markAllObtained }) : extraActions}
        {onFavorite && (
          <button
            style={favAdded ? s.copyToFavBtnDone : s.copyToFavBtn}
            onClick={handleFavorite}
            disabled={favSaving || favAdded}
            title={favAdded ? 'Added to favorites' : 'Copy to favorites'}
          >
            {favSaving ? '...' : favAdded ? '✓ Saved' : '⭐ Save'}
          </button>
        )}
        {onSave && <button style={s.saveBtn} onClick={handleSave}>Save</button>}
      </div>
    </div>
  )
}

// ── Helpers ────────────────────────────────────────────────────────────────

// Unit dropdown in the AI language; a unit outside the list stays selectable as written
function UnitSelect({ unit, units, language, onChange }) {
  const value = localizeUnit(unit || countUnit(language), language)
  return (
    <select style={s.unitSelect} value={value} onChange={(e) => onChange(e.target.value)}>
      {units.map(u => <option key={u} value={u}>{u}</option>)}
      {!units.includes(value) && <option value={value}>{value}</option>}
    </select>
  )
}

function initItems(meal, menuMode) {
  if (menuMode) {
    return (meal?.menu || []).map(item => ({
      ...item,
      ingredients: (item.ingredients || []).map(s => ({ ...s })),
    }))
  }
  return (meal?.ingredients || []).map(normalizeItem)
}

/**
 * Simple menu items are served as-is (peynir, zeytin, meyve) — they have a top-level amount.
 * Dish items (menemen, omlet) have no top-level amount and carry sub-ingredients.
 */
function isSimpleItem(item) {
  return item.amount != null
}
