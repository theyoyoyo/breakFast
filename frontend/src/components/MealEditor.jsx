import { useState, useEffect } from 'react'
import { Star } from 'lucide-react'
import { normalizeItem, unitsFor, countUnit, localizeUnit, unitWithSize, resolveUnit, rememberUnit, menuKey } from '../utils/ingredients'
import { checkMissingIngredients, getFavorites } from '../services/api'
import { useLanguage } from '../hooks/useLanguage'
import * as s from './MealEditor.styles'

const MISSING_HINT = 'Not in your fridge — tap once you have it'
const OBTAINED_HINT = 'Marked as obtained — tap to undo'
const TEMPLATE_MISSING_HINT = 'Not in your fridge'
const DISH_MISSING_HINT = 'Some ingredients are not in your fridge'
const DISH_MISSING_TAP_HINT = 'Some ingredients are not in your fridge — tap the name once you have them'
const DISH_OBTAINED_HINT = 'Missing ingredients are marked as obtained — tap to undo'

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
 *   menuMode     — boolean — edit meal.menu (multi-item) instead of meal.ingredients
 *   checkFridge  — boolean — underline ingredients that aren't in the fridge (checked by the backend);
 *                  tapping one marks it as obtained for this meal (green), saved as meal.obtained
 *   canMarkObtained — boolean — allow tapping missing items to mark them as obtained (default true);
 *                  off for templates like favorites, where items are only underlined
 *   onMissingChange — (names) => void — missing ingredients not marked as obtained, after each check
 *   onChange     — (currentMeal) => void — called with the live editor state after each change
 *   onFavorite   — async (currentMeal) => favoriteId — the ☆ left of the name adds the meal to favorites
 *   onUnfavorite — async (favoriteId) => void — the filled ⭐ removes that favorite
 *   (the star is filled when a favorite has the meal's name and food, so it's right for meals saved
 *   earlier too; a name another favorite has saves nothing and shows a note)
 *
 * extraActions may be a function: (buildCurrentMeal) => ReactNode
 */
export default function MealEditor({
  meal,
  onSave,
  onClose,
  showPrepTime = true,
  editPrepTime = true,
  extraActions,
  menuMode = false,
  onFavorite,
  onUnfavorite,
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
  // The user's favorites ({ id, meal_name, key }), loaded when the star is shown; null until loaded
  const [favorites, setFavorites] = useState(null)
  // The name the "already in Favorites" note was shown for; it hides once the name changes
  const [takenNoteFor, setTakenNoteFor] = useState(null)
  const [detailsOpen, setDetailsOpen] = useState(false)
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
    setDetailsOpen(false)
    setObtained(new Set(meal?.obtained || []))
  }, [meal, menuMode])

  // Load the favorites once, so the star shows whether this meal is already one of them
  const showStar = !!onFavorite
  useEffect(() => {
    if (!showStar) return
    let cancelled = false
    getFavorites()
      .then(list => { if (!cancelled) setFavorites(list.map(f => ({ id: f.id, meal_name: f.meal_name, key: menuKey(f) }))) })
      .catch(() => { /* offline — the star stays off until the editor opens again */ })
    return () => { cancelled = true }
  }, [showStar])

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
  // A dish's name marks all of its missing items at once (or unmarks them all)
  const setObtainedAll = (names, on) => setObtained(prev => {
    const next = new Set(prev)
    names.forEach(name => (on ? next.add(key(name)) : next.delete(key(name))))
    return next
  })

  // Missing names are tappable: yellow until marked as obtained, then green
  // (templates only show the yellow underline)
  const markProps = (name) => {
    if (!isMissing(name)) return {}
    if (!canMarkObtained) return { style: s.missingName(), title: TEMPLATE_MISSING_HINT }
    const got = isObtained(name)
    return {
      style: { ...s.missingName({ obtained: got }), cursor: 'pointer' },
      title: got ? OBTAINED_HINT : MISSING_HINT,
      role: 'button',
      onClick: (e) => { e.stopPropagation(); toggleObtained(name) },
    }
  }

  // The name's cell fills the row, while the mark and its tap stay on the text itself
  const nameCell = (name) => (
    <span style={s.itemText}><span {...markProps(name)}>{name}</span></span>
  )

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

  // How the suggestion meant each dish to be made: its method and its ingredients' prep words ("Oats: rolled"), behind the ℹ️ button
  const prepDetails = menuMode
    ? items
        .filter(item => !isSimpleItem(item))
        .map(item => ({
          dish: item.name,
          method: typeof item.method === 'string' ? item.method.trim() : '',
          notes: (item.ingredients || []).filter(sub => typeof sub.prep === 'string' && sub.prep.trim()),
        }))
        .filter(({ method, notes }) => method || notes.length > 0)
    : []

  // This meal is a favorite when one has its name (as typed now: exact, any case, like the server's
  // check) and the same food (menuKey: any order). Favorite names are unique, so another favorite
  // with this name means the name is taken.
  const favName = (mealName.trim() || meal?.meal_name || meal?.menu_name || 'Meal').toLowerCase()
  const sameName = (f) => (f.meal_name || '').trim().toLowerCase() === favName
  const currentKey = favorites ? menuKey(buildCurrentMeal()) : ''
  const favMatch = favorites?.find(f => sameName(f) && f.key === currentKey)
  const nameTaken = !!favorites?.some(sameName)
  const isFav = !!favMatch
  const showTakenNote = !isFav && takenNoteFor === favName

  // ☆ adds the meal as it is now to favorites; the filled ⭐ removes that favorite. A taken name
  // saves nothing: the note asks for a new name, or an edit of that favorite in Favorites.
  const handleFavorite = async () => {
    if (!favMatch && nameTaken) {
      setTakenNoteFor(favName)
      return
    }
    setFavSaving(true)
    try {
      if (favMatch) {
        await onUnfavorite?.(favMatch.id)
        setFavorites(prev => prev.filter(f => f.id !== favMatch.id))
      } else {
        const current = buildCurrentMeal()
        const id = await onFavorite?.(current)
        setFavorites(prev => [...(prev || []), { id, meal_name: current.meal_name, key: menuKey(current) }])
      }
    } catch (err) {
      // Another device saved a favorite with this name meanwhile
      if (err?.status === 409) setTakenNoteFor(favName)
    }
    setFavSaving(false)
  }

  // ── Render ───────────────────────────────────────────────────────────────

  return (
    <div style={s.editorContainer}>
      <div style={s.editorHeader}>
        {onFavorite && (
          <button
            style={s.favStar}
            onClick={handleFavorite}
            disabled={favSaving || favorites === null || (isFav && (!onUnfavorite || favMatch.id == null))}
            title={isFav ? 'Remove from favorites' : 'Add to favorites'}
            aria-label={isFav ? 'Remove from favorites' : 'Add to favorites'}
            aria-pressed={isFav}
          >
            <Star size={22} {...(isFav ? s.favStarOn : s.favStarOff)} />
          </button>
        )}
        <input
          style={s.nameInput}
          value={mealName}
          onChange={(e) => { if (e.target.value.length <= 100) setMealName(e.target.value) }}
          onBlur={() => { if (!mealName.trim()) setMealName(meal?.meal_name || meal?.menu_name || 'Meal') }}
          placeholder="Meal name"
        />
        {showPrepTime && (
          <div style={s.prepTimeGroup}>
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
            <span style={s.prepTimeUnit}>min</span>
          </div>
        )}
        {prepDetails.length > 0 && (
          <button
            style={s.detailsBtn(detailsOpen)}
            onClick={() => setDetailsOpen(open => !open)}
            title="Preparation details"
            aria-expanded={detailsOpen}
          >ℹ️</button>
        )}
      </div>

      {showTakenNote && (
        <div style={s.favNote} role="status">
          "{mealName.trim()}" is already in Favorites. Rename this meal to save it, or edit that favorite in Favorites.
        </div>
      )}

      {detailsOpen && prepDetails.length > 0 && (
        <div style={s.detailsBox}>
          {prepDetails.map(({ dish, method, notes }, di) => (
            <div key={di}>
              <div style={s.detailsDish}>{dish}</div>
              {method && <div style={s.detailsMethod}>{method}</div>}
              {notes.map((sub, ni) => (
                <div key={ni} style={s.detailsLine}>{sub.name}: {sub.prep.trim()}</div>
              ))}
            </div>
          ))}
        </div>
      )}

      <div style={s.itemList}>
        {items.map((item, idx) => {
          const isDish = menuMode && !isSimpleItem(item)
          const isOpen = openDishIdx === idx
          // A dish's mark sums up its hidden sub-ingredients: dotted yellow if any still missing,
          // dotted green if all missing ones are marked as obtained (solid when the name itself is
          // missing). A tap on the name marks all of them, or unmarks them all, without opening the dish.
          const subsMissing = isDish ? (item.ingredients || []).filter(sub => isMissing(sub.name)) : []
          const dishNameMissing = isDish && isMissing(item.name)
          const dishMarks = [...(dishNameMissing ? [item.name] : []), ...subsMissing.map(sub => sub.name)]
          const dishMarked = dishMarks.length > 0 && dishMarks.every(isObtained)

          return (
            <div key={idx}>
              {isDish ? (
                // ── Dish row ──────────────────────────────────────────────
                // A tap opens or closes the ingredients, the space beside the name included; its buttons
                // and the marked name itself keep the tap to themselves
                <div style={s.dishRow} onClick={() => toggleDish(idx)}>
                  <span style={s.dishBadge}>🍳</span>
                  <span style={{ ...s.itemText, fontWeight: 500 }}>
                    {dishMarks.length === 0 ? (
                      <span>{item.name}</span>
                    ) : !canMarkObtained ? (
                      <span
                        style={s.missingName({ dotted: !dishNameMissing })}
                        title={dishNameMissing ? TEMPLATE_MISSING_HINT : DISH_MISSING_HINT}
                      >{item.name}</span>
                    ) : (
                      <span
                        style={{ ...s.missingName({ dotted: !dishNameMissing, obtained: dishMarked }), cursor: 'pointer' }}
                        title={dishNameMissing
                          ? (dishMarked ? OBTAINED_HINT : MISSING_HINT)
                          : (dishMarked ? DISH_OBTAINED_HINT : DISH_MISSING_TAP_HINT)}
                        role="button"
                        // Stops here so marking doesn't also open the dish
                        onClick={(e) => { e.stopPropagation(); setObtainedAll(dishMarks, !dishMarked) }}
                      >{item.name}</span>
                    )}
                  </span>
                  <div style={s.itemActions}>
                    <button
                      style={s.expandBtn(isOpen)}
                      onClick={(e) => { e.stopPropagation(); toggleDish(idx) }}
                      title={isOpen ? 'Close ingredients' : 'Edit ingredients'}
                    >
                      {isOpen ? '▲ Ingredients' : '▶ Ingredients'}
                    </button>
                    <button style={s.deleteBtn} onClick={(e) => { e.stopPropagation(); handleDelete(idx) }} title="Delete">🗑️</button>
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
                  {nameCell(item.name)}
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
                      {nameCell(sub.name)}
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
          <div style={s.addBtns}>
            <button style={s.addBtn} onClick={() => handleAdd(false)} title="Add simple item (peynir, zeytin…)">＋ Item</button>
            <button style={s.addBtn} onClick={() => handleAdd(true)} title="Add complex dish (menemen, omlet…)">＋ Dish</button>
          </div>
        ) : (
          <button style={s.addBtn} onClick={() => handleAdd(false)}>+</button>
        )}
      </div>

      <div style={s.actions}>
        <button style={s.closeBtn} onClick={onClose}>Close</button>
        {typeof extraActions === 'function' ? extraActions(buildCurrentMeal) : extraActions}
        {onSave && <button style={s.saveBtn} onClick={handleSave}>Save</button>}
      </div>
    </div>
  )
}

// ── Helpers ────────────────────────────────────────────────────────────────

// Unit dropdown in the AI language; a unit outside the list stays selectable as written.
// The box shows the plain unit and only the open list shows spoon and glass sizes, so the
// select lies invisibly over a label as wide as the longest word of any unit: two-word units
// take two lines, so the column stays narrow on phones and keeps its width when a unit is picked.
function UnitSelect({ unit, units, language, onChange }) {
  const value = localizeUnit(unit || countUnit(language), language)
  const options = units.includes(value) ? units : [...units, value]
  const width = `${Math.max(...options.flatMap(u => u.split(' ')).map(word => word.length)) + 2}ch`
  return (
    <span style={{ ...s.unitPicker, width }}>
      <span style={s.unitText} aria-hidden="true">{value}</span>
      <span aria-hidden="true">▾</span>
      <select style={s.unitSelect} value={value} onChange={(e) => onChange(e.target.value)}>
        {options.map(u => <option key={u} value={u}>{unitWithSize(u)}</option>)}
      </select>
    </span>
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
