import { useState, useEffect, useCallback, useRef, useImperativeHandle, forwardRef } from 'react'
import { Trash2, Pencil, Plus, X, AlertTriangle, ShoppingCart, Sparkles, Loader, ChevronRight, Heart } from 'lucide-react'
import {
  getIngredients, addIngredient, updateIngredient, deleteIngredient,
  getExpiredIngredients, getExpiredCount, handleExpiredAction,
  getShoppingSuggestions, getSuggestionList, saveSuggestionList, addShoppingItemsBulk, addShoppingItem,
  getFavoriteIngredients, addFavoriteIngredient, removeFavoriteIngredient,
} from '../services/api'
import { useSyncNotice } from '../hooks/useSyncNotice'
import ShoppingListPanel from './ShoppingListPanel'
import FavoriteIngredientsPanel from './FavoriteIngredientsPanel'
import * as s from './IngredientPanel.styles'

// ---------------------------------------------------------------------------
// Fixed ingredient groups (mirrors backend INGREDIENT_GROUPS)
// ---------------------------------------------------------------------------
const INGREDIENT_GROUPS = [
  '🐄 Animal Products', '🥬 Produce', '🍞 Breads', '🍯 Sweets',
  '🫒 Breakfast Staples', '🥜 Nuts & Seeds', '🌱 Plant-Based', '☕ Beverages',
  '🧂 Spices', '🫙 Pantry', '🍽️ Other',
]
const DEFAULT_GROUP = '🍽️ Other'

const COLLAPSE_KEY = 'bf_ingredient_groups_collapsed'

function loadCollapseState() {
  try { return JSON.parse(localStorage.getItem(COLLAPSE_KEY)) || {} }
  catch { return {} }
}

// The suggestions list lives on the server (the same on every device). This device's old
// list from before that moves to the server on its first load, then the key is cleared.
const LEGACY_SUGGESTIONS_KEY = 'bf_suggestions'
// Whether the suggestions list is collapsed (▼) — a per-device view setting
const SUGGESTIONS_COLLAPSED_KEY = 'bf_suggestions_collapsed'

function readLegacySuggestions() {
  try {
    const list = JSON.parse(localStorage.getItem(LEGACY_SUGGESTIONS_KEY))
    return Array.isArray(list) ? list.filter(i => typeof i?.name === 'string' && i.name.trim()) : []
  } catch { return [] }
}

/** The list with the new items added at the end, checked; names already listed are skipped. */
function appendNew(list, items) {
  const names = new Set(list.map(i => i.name.toLowerCase()))
  const added = []
  for (const item of items) {
    const key = item.name.toLowerCase()
    if (names.has(key)) continue
    names.add(key)
    added.push({ name: item.name, reason: item.reason || '', checked: true })
  }
  return [...list, ...added]
}

const IngredientPanel = forwardRef(function IngredientPanel({ refreshTrigger, visible }, ref) {
  const [ingredients, setIngredients] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  // Add panel state
  const [addPanelOpen, setAddPanelOpen] = useState(false)
  const [newName, setNewName] = useState('')
  const [newExpiry, setNewExpiry] = useState('')
  const [newGroup, setNewGroup] = useState('')

  // Edit state
  const [editingId, setEditingId] = useState(null)
  const [editName, setEditName] = useState('')
  const [editExpiry, setEditExpiry] = useState('')
  const [editGroup, setEditGroup] = useState(DEFAULT_GROUP)

  // Group collapse state (persisted in localStorage)
  const [collapsed, setCollapsed] = useState(() => loadCollapseState())

  // Expiry state
  const [expiredCount, setExpiredCount] = useState(0)
  const [expiredItems, setExpiredItems] = useState([])
  const [expiryPanelOpen, setExpiryPanelOpen] = useState(false)
  const [expiryAction, setExpiryAction] = useState({}) // {id: 'delete'|'keep'|'shopping'}

  // Shopping state: the suggestions list is [{ name, reason, checked }], kept on the server
  const [suggestions, setSuggestions] = useState([])
  const [suggestionsCollapsed, setSuggestionsCollapsed] = useState(() => {
    try { return localStorage.getItem(SUGGESTIONS_COLLAPSED_KEY) === 'true' } catch { return false }
  })
  const [suggestionsLoading, setSuggestionsLoading] = useState(false)
  const [shoppingListOpen, setShoppingListOpen] = useState(false)
  const [lyricBanner, setLyricBanner] = useState(null)
  const [noNewSuggestions, setNoNewSuggestions] = useState(false) // the AI only had repeats

  // Delete-to-shopping popup
  const [deletePopup, setDeletePopup] = useState(null) // { id, name }

  // Favorite ingredients
  const [favoriteNames, setFavoriteNames] = useState(new Set())
  const [favPanelOpen, setFavPanelOpen] = useState(false)

  const loadFavorites = async () => {
    try {
      const favs = await getFavoriteIngredients()
      setFavoriteNames(new Set(favs.map(f => f.ingredient_name.toLowerCase())))
    } catch { /* ignore */ }
  }

  const toggleFavorite = async (name) => {
    const key = name.toLowerCase()
    const isFav = favoriteNames.has(key)
    // Optimistic update
    setFavoriteNames(prev => {
      const next = new Set(prev)
      if (isFav) next.delete(key)
      else next.add(key)
      return next
    })
    try {
      if (isFav) await removeFavoriteIngredient(name)
      else await addFavoriteIngredient(name)
    } catch {
      // Revert on failure
      loadFavorites()
    }
  }

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

  const refreshExpiredCount = useCallback(async () => {
    try {
      const { count } = await getExpiredCount()
      setExpiredCount(count)
    } catch { /* ignore */ }
  }, [])

  // Latest suggestions list, for handlers that finish after a request
  const suggestionsRef = useRef(suggestions)
  suggestionsRef.current = suggestions
  // Saves in flight; a reload asked for meanwhile waits for them, so it can't show an older list
  const savingRef = useRef(0)
  const reloadPendingRef = useRef(false)
  const loadSeqRef = useRef(0)

  // Load the suggestions list from the server (another device may have changed it)
  const loadSuggestions = useCallback(async () => {
    if (savingRef.current > 0) { reloadPendingRef.current = true; return }
    const seq = ++loadSeqRef.current
    try {
      const { items } = await getSuggestionList()
      if (seq !== loadSeqRef.current) return
      if (savingRef.current > 0) { reloadPendingRef.current = true; return }
      setSuggestions(items)
    } catch { /* offline — keep what's shown */ }
  }, [])

  // Show the new list at once and save it; `removed` names were removed with ×
  const saveSuggestions = useCallback(async (items, removed = []) => {
    setSuggestions(items)
    savingRef.current += 1
    try {
      await saveSuggestionList(items, removed)
    } catch {
      setError('Failed to save suggestions')
      reloadPendingRef.current = true // show what the server has
    } finally {
      savingRef.current -= 1
    }
    if (savingRef.current === 0 && reloadPendingRef.current) {
      reloadPendingRef.current = false
      loadSuggestions()
    }
  }, [loadSuggestions])

  useEffect(() => { load(); refreshExpiredCount(); loadFavorites() }, [refreshTrigger]) // eslint-disable-line react-hooks/exhaustive-deps

  // Refresh ingredients + expired count + favorites + suggestions every time the tab becomes visible
  useEffect(() => {
    if (visible) { load(); refreshExpiredCount(); loadFavorites(); loadSuggestions() }
  }, [visible]) // eslint-disable-line react-hooks/exhaustive-deps

  // First load: move this device's old local list to the server (after what's there), then load it
  useEffect(() => {
    ;(async () => {
      const legacy = readLegacySuggestions()
      if (legacy.length > 0) {
        try {
          const { items } = await getSuggestionList()
          const merged = appendNew(items, legacy)
          if (merged.length > items.length) await saveSuggestionList(merged)
          localStorage.removeItem(LEGACY_SUGGESTIONS_KEY)
        } catch { /* offline — move it on the next load */ }
      }
      loadSuggestions()
    })()
  }, [loadSuggestions])

  // Another device changed the list, or the chat socket (re)opened: reload it
  useSyncNotice(['shopping_suggestions_updated', 'sync_connected'], loadSuggestions)

  // Back from the background (phone app resumed): reload it too, in case a push was missed
  useEffect(() => {
    const handleVisible = () => { if (document.visibilityState === 'visible') loadSuggestions() }
    document.addEventListener('visibilitychange', handleVisible)
    return () => document.removeEventListener('visibilitychange', handleVisible)
  }, [loadSuggestions])

  // Dismiss delete confirm on any outside click (serves as cancel)
  useEffect(() => {
    if (!deletePopup) return
    const dismiss = () => setDeletePopup(null)
    // Use setTimeout(0) so the current click event doesn't immediately dismiss
    const id = setTimeout(() => {
      window.addEventListener('click', dismiss, { once: true })
    }, 0)
    return () => { clearTimeout(id); window.removeEventListener('click', dismiss) }
  }, [deletePopup])

  // Expose demo hooks
  useImperativeHandle(ref, () => ({
    injectDemoShopping: () => {
      const demoSuggestions = [
        { name: 'Walnuts', reason: 'Omega-3 source — supports brain function at breakfast' },
        { name: 'Strawberries', reason: 'In season, rich in antioxidants' },
        { name: 'Avocado', reason: 'Healthy fat source, perfect on toast' },
        { name: 'Chia seeds', reason: 'Fiber and omega-3 — great with yogurt' },
        { name: 'Whole-wheat bread', reason: 'Complex carbs, keeps you full longer' },
        { name: 'Cottage cheese', reason: 'High protein, low fat' },
        { name: 'Honey', reason: 'Natural sweetener, quick energy' },
        { name: 'Tomato', reason: 'Lycopene source, classic breakfast staple' },
        { name: 'Cucumber', reason: 'Hydrating and fresh' },
        { name: 'Olives', reason: 'Healthy fats, foundation of the Mediterranean diet' },
        { name: 'Tahini', reason: 'Calcium and iron source, classic with molasses' },
        { name: 'Rolled oats', reason: 'Beta-glucan helps lower cholesterol' },
      ]
      saveSuggestions(appendNew([], demoSuggestions))
    },
  }))

  const toggleCollapse = (groupName) => {
    setCollapsed(prev => {
      const next = { ...prev, [groupName]: !prev[groupName] }
      localStorage.setItem(COLLAPSE_KEY, JSON.stringify(next))
      return next
    })
  }

  const handleAdd = async () => {
    const name = newName.trim()
    if (!name) return
    try {
      setError(null)
      await addIngredient(name, newExpiry || null, newGroup || null)
      setNewName('')
      setNewExpiry('')
      setNewGroup('')
      setAddPanelOpen(false)
      load()
      refreshExpiredCount()
    } catch (e) {
      setError('Failed to add ingredient')
    }
  }

  const handleDelete = async (id) => {
    try {
      await deleteIngredient(id)
      setDeletePopup(null)
      load()
      refreshExpiredCount()
    } catch (err) {
      setError('Failed to delete ingredient')
    }
  }

  const handleDeleteToShopping = async (id) => {
    const ing = ingredients.find(i => i.id === id)
    try {
      await deleteIngredient(id)
      if (ing) await addShoppingItem(ing.name)
      setDeletePopup(null)
      load()
      refreshExpiredCount()
    } catch (err) {
      setError('Failed to delete ingredient')
    }
  }

  const startEdit = (ing) => {
    setEditingId(ing.id)
    setEditName(ing.name)
    setEditExpiry(ing.expiry_date || '')
    setEditGroup(ing.group_name || DEFAULT_GROUP)
  }

  const cancelEdit = () => {
    setEditingId(null)
    setEditName('')
    setEditExpiry('')
    setEditGroup(DEFAULT_GROUP)
  }

  const handleEdit = async () => {
    if (!editName.trim()) return
    try {
      setError(null)
      await updateIngredient(editingId, {
        name: editName.trim(),
        expiry_date: editExpiry || '',
        group_name: editGroup,
      })
      cancelEdit()
      load()
      refreshExpiredCount()
    } catch (e) {
      setError('Failed to update ingredient')
    }
  }

  // Open expiry panel — fetch full list
  const openExpiryPanel = async () => {
    try {
      const expired = await getExpiredIngredients()
      setExpiredItems(expired)
      const actions = {}
      expired.forEach(i => { actions[i.id] = 'delete' })
      setExpiryAction(actions)
      setExpiryPanelOpen(true)
    } catch {
      setError('Failed to load expired items')
    }
  }

  const setItemAction = (id, action) => {
    setExpiryAction(prev => ({ ...prev, [id]: action }))
  }

  const handleExpiryConfirm = async () => {
    const deleteIds = []
    const keepIds = []
    const shoppingIds = []
    for (const [id, action] of Object.entries(expiryAction)) {
      const numId = Number(id)
      if (numId < 0) continue // demo items
      if (action === 'delete') deleteIds.push(numId)
      else if (action === 'keep') keepIds.push(numId)
      else if (action === 'shopping') shoppingIds.push(numId)
    }
    try {
      setError(null)
      await handleExpiredAction(deleteIds, keepIds, shoppingIds)
      setExpiryPanelOpen(false)
      setExpiredItems([])
      load()
      refreshExpiredCount()
    } catch {
      setError('Failed to process expired items')
    }
  }

  // Shopping handlers: Suggest Shopping / Suggest More add new items at the end, checked;
  // items already listed keep their checks. The server leaves out what's listed (`exclude`)
  // and what was removed with × in the last 7 days.
  const handleSuggest = async () => {
    try {
      setError(null)
      setSuggestionsLoading(true)
      setLyricBanner(null)
      setNoNewSuggestions(false)
      const result = await getShoppingSuggestions(suggestionsRef.current.map(s => s.name))

      if (result.lyric) {
        // LLM is down
        setLyricBanner(result.lyric)
      } else if (result.error && (!result.suggestions || result.suggestions.length === 0)) {
        // Backend returned 200 with an error hint (e.g., parsing failed)
        setError(result.error)
      } else {
        // Added to the latest list: another device may have changed it meanwhile
        const latest = suggestionsRef.current
        const merged = appendNew(latest, result.suggestions || [])
        if (merged.length > latest.length) await saveSuggestions(merged)
        // The backend drops anything already known and retried once, so nothing new is left
        else setNoNewSuggestions(true)
      }
    } catch {
      setError('Failed to get suggestions')
    } finally {
      setSuggestionsLoading(false)
    }
  }

  const toggleSuggestion = (name) => {
    saveSuggestions(suggestions.map(s => (s.name === name ? { ...s, checked: !s.checked } : s)))
  }

  // × — remove one item; it stays out of new suggestions for 7 days
  const removeSuggestion = (name) => {
    saveSuggestions(suggestions.filter(s => s.name !== name), [name])
  }

  // Send to List moves the checked items to the shopping list and keeps the rest
  const handleSendToList = async () => {
    const sent = suggestions.filter(s => s.checked).map(s => s.name)
    if (sent.length === 0) return
    try {
      setError(null)
      await addShoppingItemsBulk(sent)
    } catch {
      setError('Failed to add items to shopping list')
      return
    }
    setLyricBanner(null)
    await saveSuggestions(suggestionsRef.current.filter(s => !sent.includes(s.name)))
  }

  // ▲/▼ hides or shows the list; it never clears it
  const toggleSuggestionsCollapsed = () => {
    setSuggestionsCollapsed(prev => {
      try { localStorage.setItem(SUGGESTIONS_COLLAPSED_KEY, String(!prev)) } catch { /* ignore */ }
      return !prev
    })
  }

  const selectedSuggestionCount = suggestions.filter(s => s.checked).length

  const suggestButtonLabel = suggestionsLoading
    ? <><Loader size={13} style={{ animation: 'spin 1s linear infinite' }} /> Thinking…</>
    : suggestions.length > 0
      ? <><Sparkles size={13} /> Suggest More</>
      : <><Sparkles size={13} /> Suggest Shopping</>

  const suggestNotes = (
    <>
      {lyricBanner && <div style={s.lyricBanner}>{lyricBanner}</div>}
      {noNewSuggestions && <div style={s.suggestNote}>No new items this time. Try again in a moment.</div>}
    </>
  )

  const formatExpiry = (dateStr) => {
    if (!dateStr) return null
    try {
      const d = new Date(dateStr + 'T00:00:00')
      return d.toLocaleDateString('tr-TR', { day: 'numeric', month: 'short' })
    } catch {
      return dateStr
    }
  }

  const isExpired = (dateStr) => {
    if (!dateStr) return false
    return dateStr <= new Date().toISOString().split('T')[0]
  }

  // Count of expired items the user previously acknowledged ("kept")
  const keptCount = ingredients.filter(i => i.expiry_acknowledged && isExpired(i.expiry_date)).length

  return (
    <div style={s.container}>
      {/* Header with expired + add buttons */}
      <div style={s.headerRow}>
        <span style={s.headerText}>break FAST</span>
        <div style={s.headerBtns}>
          <button
            style={expiredCount > 0 ? s.headerExpiredBtn : s.headerExpiredBtnSafe}
            onClick={() => expiredCount > 0 && openExpiryPanel()}
            title={expiredCount > 0 ? 'Expired items' : 'No expired items'}
          >
            <AlertTriangle size={13} />
            <span>{expiredCount}</span>
          </button>
          <button
            style={s.headerFavBtn}
            onClick={() => setFavPanelOpen(true)}
            title="Favorite ingredients"
          >
            <Heart size={13} fill="currentColor" />
          </button>
          <button
            style={s.headerShoppingBtn}
            onClick={() => setShoppingListOpen(true)}
            title="Shopping list"
          >
            <ShoppingCart size={13} />
          </button>
          <button
            style={s.headerAddBtn}
            onClick={() => { setAddPanelOpen(!addPanelOpen); setError(null) }}
            title="Add ingredient"
          >
            {addPanelOpen ? <X size={14} /> : <><Plus size={14} /> <span>Add Item</span></>}
          </button>
        </div>
      </div>

      {/* Add panel (slides open below header) */}
      {addPanelOpen && (
        <div style={s.addPanel}>
          <input
            style={s.addInput}
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleAdd()}
            placeholder="Ingredient name…"
            autoFocus
          />
          <div style={s.addPanelRow}>
            <select
              style={s.addGroupSelect}
              value={newGroup}
              onChange={(e) => setNewGroup(e.target.value)}
            >
              <option value="">Auto (group memory)</option>
              {INGREDIENT_GROUPS.map(g => (
                <option key={g} value={g}>{g}</option>
              ))}
            </select>
            <input
              type="date"
              style={s.addDateInput}
              value={newExpiry}
              onChange={(e) => setNewExpiry(e.target.value)}
            />
            <button style={s.addPanelBtn} onClick={handleAdd}>Add</button>
          </div>
        </div>
      )}

      {/* Ingredient list — grouped */}
      <div style={s.list}>
        {error && <div style={s.error}>{error}</div>}
        {loading && <div style={s.empty}>Loading…</div>}
        {!loading && ingredients.length === 0 && (
          <div style={s.empty}>No ingredients yet. Tell me what you have!</div>
        )}
        {!loading && ingredients.length > 0 && INGREDIENT_GROUPS.map(groupName => {
          const groupItems = ingredients.filter(i => (i.group_name || DEFAULT_GROUP) === groupName)
          if (groupItems.length === 0) return null
          const isCollapsed = !!collapsed[groupName]
          return (
            <div key={groupName} style={s.groupSection}>
              <div style={s.groupHeader} onClick={() => toggleCollapse(groupName)}>
                <ChevronRight
                  size={12}
                  style={{
                    ...s.groupChevron,
                    transform: isCollapsed ? 'rotate(0deg)' : 'rotate(90deg)',
                  }}
                />
                <span style={s.groupHeaderText}>{groupName}</span>
                <span style={s.groupCount}>{groupItems.length}</span>
              </div>
              {!isCollapsed && groupItems.map((ing) => (
                editingId === ing.id ? (
                  /* Edit mode row */
                  <div key={ing.id}>
                    <div style={s.editRow}>
                      <input
                        style={s.editInput}
                        value={editName}
                        onChange={(e) => setEditName(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter') handleEdit()
                          if (e.key === 'Escape') cancelEdit()
                        }}
                        autoFocus
                      />
                      <button style={s.editSaveBtn} onClick={handleEdit}>Save</button>
                      <button style={s.editCancelBtn} onClick={cancelEdit}>
                        <X size={14} />
                      </button>
                    </div>
                    <div style={{ ...s.editRow, paddingTop: 0 }}>
                      <select
                        style={s.editGroupSelect}
                        value={editGroup}
                        onChange={(e) => setEditGroup(e.target.value)}
                      >
                        {INGREDIENT_GROUPS.map(g => (
                          <option key={g} value={g}>{g}</option>
                        ))}
                      </select>
                      <input
                        type="date"
                        style={s.editDateInput}
                        value={editExpiry}
                        onChange={(e) => setEditExpiry(e.target.value)}
                      />
                    </div>
                  </div>
                ) : (
                  /* Normal row */
                  <div key={ing.id}>
                    <div style={{ ...s.row, padding: '7px 16px' }}>
                      <span style={{
                        ...s.name,
                        color: isExpired(ing.expiry_date) ? 'var(--error, #e74c3c)' : 'var(--text)',
                      }}>{ing.name}</span>
                      {ing.expiry_date && (
                        <span style={{
                          ...s.expiryBadge,
                          color: isExpired(ing.expiry_date) ? 'var(--error, #e74c3c)' : 'var(--text-muted)',
                          fontWeight: isExpired(ing.expiry_date) ? 600 : 400,
                        }}>
                          {formatExpiry(ing.expiry_date)}
                          {ing.expiry_acknowledged && isExpired(ing.expiry_date) && (
                            <span style={s.keptBadge}>(kept)</span>
                          )}
                        </span>
                      )}
                      <button
                        style={s.favBtn}
                        onClick={() => toggleFavorite(ing.name)}
                        title={favoriteNames.has(ing.name.toLowerCase()) ? 'Remove from favorites' : 'Add to favorites'}
                      >
                        <Heart
                          size={12}
                          fill={favoriteNames.has(ing.name.toLowerCase()) ? '#e74c3c' : 'none'}
                          color={favoriteNames.has(ing.name.toLowerCase()) ? '#e74c3c' : 'var(--text-muted)'}
                        />
                      </button>
                      <button
                        style={s.iconBtn}
                        onClick={() => startEdit(ing)}
                        title="Edit"
                      >
                        <Pencil size={12} />
                      </button>
                      <div style={{ position: 'relative' }}>
                        <button
                          style={s.rowDeleteBtn}
                          onClick={(e) => {
                            e.stopPropagation()
                            setDeletePopup(deletePopup?.id === ing.id ? null : { id: ing.id, name: ing.name })
                          }}
                          title="Delete"
                        >
                          <Trash2 size={12} />
                        </button>
                        {deletePopup?.id === ing.id && (
                          <div style={s.deleteConfirm} onClick={(e) => e.stopPropagation()}>
                            <button
                              style={s.deleteConfirmTrash}
                              onClick={() => handleDelete(ing.id)}
                              title="Delete"
                            >
                              <Trash2 size={12} />
                            </button>
                            <button
                              style={s.deleteConfirmShop}
                              onClick={() => handleDeleteToShopping(ing.id)}
                              title="Delete & add to shopping list"
                            >
                              <ShoppingCart size={12} />
                            </button>
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                )
              ))}
            </div>
          )
        })}
        {/* (delete confirm buttons now appear inline next to the delete icon) */}
      </div>

      {/* Expiry detail panel — 3-way radio buttons */}
      {expiryPanelOpen && (
        <div style={s.expiryPanel}>
          <div style={s.expiryPanelHeader}>
            <button style={s.closeBtn} onClick={() => setExpiryPanelOpen(false)}>
              <X size={16} />
            </button>
            <span style={s.expiryPanelTitle}>
              Expired Items
              {keptCount > 0 && (
                <span style={s.keptCountLabel}> · {keptCount} kept</span>
              )}
            </span>
            <div style={{ width: 24 }} />
          </div>
          <div style={s.expiryPanelList}>
            {expiredItems.map(item => (
              <div key={item.id} style={s.expiryRow}>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <span style={{ fontSize: 13, color: 'var(--text)' }}>{item.name}</span>
                  {item.expiry_date && (
                    <span style={{ ...s.expiryBadge, marginLeft: 6 }}>{formatExpiry(item.expiry_date)}</span>
                  )}
                </div>
                <div style={s.expiryActionGroup}>
                  <button
                    style={expiryAction[item.id] === 'delete' ? s.expiryActionDeleteActive : s.expiryActionBtn}
                    onClick={() => setItemAction(item.id, 'delete')}
                    title="Delete"
                  >
                    <Trash2 size={11} />
                  </button>
                  <button
                    style={expiryAction[item.id] === 'keep' ? s.expiryActionKeepActive : s.expiryActionBtn}
                    onClick={() => setItemAction(item.id, 'keep')}
                    title="Keep"
                  >
                    ✓
                  </button>
                  <button
                    style={expiryAction[item.id] === 'shopping' ? s.expiryActionShoppingActive : s.expiryActionBtn}
                    onClick={() => setItemAction(item.id, 'shopping')}
                    title="Add to shopping list"
                  >
                    <ShoppingCart size={11} />
                  </button>
                </div>
              </div>
            ))}
          </div>
          {expiredItems.length > 0 && (
            <button style={s.expiryConfirmBtn} onClick={handleExpiryConfirm}>
              Confirm
            </button>
          )}
        </div>
      )}

      {/* Shopping suggestions: Suggest Shopping at the top while there's no list */}
      {suggestions.length === 0 && (
        <div style={s.suggestSection}>
          <button
            style={{
              ...s.suggestBtn,
              opacity: suggestionsLoading ? 0.6 : 1,
              cursor: suggestionsLoading ? 'default' : 'pointer',
            }}
            onClick={handleSuggest}
            disabled={suggestionsLoading}
          >
            {suggestButtonLabel}
          </button>
          {suggestNotes}
        </div>
      )}

      {/* Suggestions list (kept on the server): ▲/▼ hides it, × removes one item,
          Send to List and Suggest More sit together under it */}
      {suggestions.length > 0 && (
        <div style={s.suggestionsPanel}>
          <button
            style={s.suggestionsPanelHeader}
            onClick={toggleSuggestionsCollapsed}
            aria-expanded={!suggestionsCollapsed}
            title={suggestionsCollapsed ? 'Show suggestions' : 'Hide suggestions'}
          >
            <span style={s.suggestionsPanelTitle}>
              Suggestions{suggestionsCollapsed ? ` (${suggestions.length})` : ''}
            </span>
            <span style={s.collapseIcon} aria-hidden="true">{suggestionsCollapsed ? '▼' : '▲'}</span>
          </button>
          {!suggestionsCollapsed && (
            <>
              <div style={s.suggestionsList}>
                {suggestions.map((item) => (
                  <div key={item.name} style={s.suggestionRow}>
                    <label style={s.suggestionLabel}>
                      <input
                        type="checkbox"
                        checked={item.checked}
                        onChange={() => toggleSuggestion(item.name)}
                        style={s.checkbox}
                      />
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={s.suggestionName}>{item.name}</div>
                        {item.reason && <div style={s.suggestionReason}>{item.reason}</div>}
                      </div>
                    </label>
                    <button
                      style={s.suggestionRemoveBtn}
                      onClick={() => removeSuggestion(item.name)}
                      title="Remove (not suggested again for 7 days)"
                      aria-label={`Remove ${item.name}`}
                    >×</button>
                  </div>
                ))}
              </div>
              <div style={s.suggestionsActions}>
                <button
                  style={{
                    ...s.sendToListBtn,
                    opacity: selectedSuggestionCount === 0 ? 0.4 : 1,
                    cursor: selectedSuggestionCount === 0 ? 'default' : 'pointer',
                  }}
                  onClick={handleSendToList}
                  disabled={selectedSuggestionCount === 0}
                >
                  <ShoppingCart size={13} />
                  Send to List{selectedSuggestionCount > 0 ? ` (${selectedSuggestionCount})` : ''}
                </button>
                <button
                  style={{
                    ...s.suggestMoreBtn,
                    opacity: suggestionsLoading ? 0.6 : 1,
                    cursor: suggestionsLoading ? 'default' : 'pointer',
                  }}
                  onClick={handleSuggest}
                  disabled={suggestionsLoading}
                >
                  {suggestButtonLabel}
                </button>
              </div>
              {(lyricBanner || noNewSuggestions) && <div style={s.suggestionsNotes}>{suggestNotes}</div>}
            </>
          )}
        </div>
      )}

      {/* Shopping list overlay */}
      <ShoppingListPanel
        open={shoppingListOpen}
        onClose={() => setShoppingListOpen(false)}
        onBought={() => { load(); refreshExpiredCount() }}
      />
      <FavoriteIngredientsPanel
        open={favPanelOpen}
        onClose={() => setFavPanelOpen(false)}
      />
    </div>
  )
})

export default IngredientPanel
