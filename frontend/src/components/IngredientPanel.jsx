import { useState, useEffect, useCallback, useImperativeHandle, forwardRef } from 'react'
import { Trash2, Pencil, Plus, X, AlertTriangle, ShoppingCart, Sparkles, Loader, ChevronRight } from 'lucide-react'
import {
  getIngredients, addIngredient, updateIngredient, deleteIngredient,
  getExpiredIngredients, getExpiredCount, handleExpiredAction,
  getShoppingSuggestions, addShoppingItemsBulk, addShoppingItem,
} from '../services/api'
import ShoppingListPanel from './ShoppingListPanel'
import * as s from './IngredientPanel.styles'

// ---------------------------------------------------------------------------
// Fixed ingredient groups (mirrors backend INGREDIENT_GROUPS)
// ---------------------------------------------------------------------------
const INGREDIENT_GROUPS = ['Şarküteri', 'Sebze/Meyve', 'Baharatlar', 'Diğer']
const DEFAULT_GROUP = 'Diğer'

const COLLAPSE_KEY = 'bf_ingredient_groups_collapsed'

function loadCollapseState() {
  try { return JSON.parse(localStorage.getItem(COLLAPSE_KEY)) || {} }
  catch { return {} }
}

/** Deterministic subtle background color from group name hash */
function groupColor(name) {
  let hash = 0
  for (let i = 0; i < name.length; i++) hash = name.charCodeAt(i) + ((hash << 5) - hash)
  const h = Math.abs(hash) % 360
  return `hsla(${h}, 30%, 50%, 0.06)`
}

const STORAGE_KEY = 'bf_suggestions'

function loadSavedSuggestions() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? JSON.parse(raw) : []
  } catch { return [] }
}

function saveSuggestions(data) {
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify(data)) } catch { /* ignore */ }
}

const IngredientPanel = forwardRef(function IngredientPanel({ refreshTrigger }, ref) {
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

  // Shopping state
  const [suggestions, setSuggestions] = useState(() => loadSavedSuggestions())
  const [suggestionsLoading, setSuggestionsLoading] = useState(false)
  const [selectedSuggestions, setSelectedSuggestions] = useState({})
  const [shoppingListOpen, setShoppingListOpen] = useState(false)
  const [lyricBanner, setLyricBanner] = useState(null)

  // Delete-to-shopping popup
  const [deletePopup, setDeletePopup] = useState(null) // { id, name, top }

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

  useEffect(() => { load(); refreshExpiredCount() }, [refreshTrigger]) // eslint-disable-line react-hooks/exhaustive-deps

  // Init selected suggestions from saved data
  useEffect(() => {
    if (suggestions.length > 0) {
      const sel = {}
      suggestions.forEach((_, i) => { sel[i] = true })
      setSelectedSuggestions(sel)
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // Dismiss delete popup on any outside click
  useEffect(() => {
    if (!deletePopup) return
    const dismiss = () => setDeletePopup(null)
    const timer = setTimeout(dismiss, 5000)
    window.addEventListener('click', dismiss, { once: true, capture: true })
    return () => { clearTimeout(timer); window.removeEventListener('click', dismiss, { capture: true }) }
  }, [deletePopup])

  // Expose demo hooks
  useImperativeHandle(ref, () => ({
    injectDemoExpiry: () => {
      const fakeExpired = [
        { id: -1, name: 'Yogurt (demo)', expiry_date: new Date().toISOString().split('T')[0], added_at: '', updated_at: '' },
        { id: -2, name: 'Milk (demo)', expiry_date: new Date().toISOString().split('T')[0], added_at: '', updated_at: '' },
      ]
      setExpiredItems(fakeExpired)
      setExpiredCount(fakeExpired.length)
      const actions = {}
      fakeExpired.forEach(i => { actions[i.id] = 'delete' })
      setExpiryAction(actions)
      setExpiryPanelOpen(true)
    },
    injectDemoShopping: () => {
      const demoSuggestions = [
        { name: 'Ceviz', reason: 'Omega-3 kaynağı, kahvaltıda beyin fonksiyonlarını destekler' },
        { name: 'Çilek', reason: 'Mevsiminde, antioksidan açısından zengin' },
        { name: 'Avokado', reason: 'Sağlıklı yağ kaynağı, tostu mükemmel' },
        { name: 'Chia tohumu', reason: 'Lif ve omega-3 deposu, yoğurtla harika' },
        { name: 'Tam buğday ekmeği', reason: 'Kompleks karbonhidrat, uzun süre tok tutar' },
        { name: 'Lor peyniri', reason: 'Yüksek protein, düşük yağ' },
        { name: 'Bal', reason: 'Doğal tatlandırıcı, enerji kaynağı' },
        { name: 'Domates', reason: 'Likopen kaynağı, klasik kahvaltı malzemesi' },
        { name: 'Salatalık', reason: 'Hidrasyon ve tazelik sağlar' },
        { name: 'Zeytin', reason: 'Sağlıklı yağ, Akdeniz diyetinin temeli' },
        { name: 'Tahin', reason: 'Kalsiyum ve demir kaynağı, pekmezle klasik' },
        { name: 'Yulaf ezmesi', reason: 'Beta-glukan ile kolesterol düşürücü etki' },
      ]
      setSuggestions(demoSuggestions)
      saveSuggestions(demoSuggestions)
      const sel = {}
      demoSuggestions.forEach((_, i) => { sel[i] = true })
      setSelectedSuggestions(sel)
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

  const handleDelete = async (id, e) => {
    const ing = ingredients.find(i => i.id === id)
    setIngredients((prev) => prev.filter((i) => i.id !== id))
    try {
      await deleteIngredient(id)
      refreshExpiredCount()
      // Show "add to shopping list?" popup
      if (ing) {
        const rect = e?.currentTarget?.getBoundingClientRect()
        setDeletePopup({ id, name: ing.name, top: rect ? rect.bottom : 0 })
      }
    } catch (err) {
      setError('Failed to delete ingredient')
      load()
    }
  }

  const handleAddToShoppingFromDelete = async () => {
    if (!deletePopup) return
    try {
      await addShoppingItem(deletePopup.name)
    } catch { /* ignore */ }
    setDeletePopup(null)
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

  // Shopping handlers
  const handleSuggest = async () => {
    try {
      setError(null)
      setSuggestionsLoading(true)
      setLyricBanner(null)
      const exclude = suggestions.map(s => s.name) // exclude current when "suggest more"
      const result = await getShoppingSuggestions(suggestions.length > 0 ? exclude : [])

      if (result.lyric) {
        // LLM is down
        setLyricBanner(result.lyric)
        // Show saved suggestions if we have none
        if (suggestions.length === 0) {
          const saved = loadSavedSuggestions()
          if (saved.length > 0) {
            setSuggestions(saved)
            const sel = {}
            saved.forEach((_, i) => { sel[i] = true })
            setSelectedSuggestions(sel)
          }
        }
      } else if (result.suggestions && result.suggestions.length > 0) {
        if (suggestions.length > 0) {
          // "Suggest more" mode — append new, deduplicate by name
          const existingNames = new Set(suggestions.map(s => s.name.toLowerCase()))
          const newItems = result.suggestions.filter(s => !existingNames.has(s.name.toLowerCase()))
          const merged = [...suggestions, ...newItems]
          setSuggestions(merged)
          saveSuggestions(merged)
          // Select only new items
          const sel = { ...selectedSuggestions }
          newItems.forEach((_, i) => { sel[suggestions.length + i] = true })
          setSelectedSuggestions(sel)
        } else {
          setSuggestions(result.suggestions)
          saveSuggestions(result.suggestions)
          const sel = {}
          result.suggestions.forEach((_, i) => { sel[i] = true })
          setSelectedSuggestions(sel)
        }
      }
    } catch {
      setError('Failed to get suggestions')
    } finally {
      setSuggestionsLoading(false)
    }
  }

  const toggleSuggestion = (idx) => {
    setSelectedSuggestions(prev => ({ ...prev, [idx]: !prev[idx] }))
  }

  const handleSendToList = async () => {
    const selected = suggestions.filter((_, i) => selectedSuggestions[i])
    if (selected.length === 0) return
    try {
      setError(null)
      await addShoppingItemsBulk(selected.map(s => s.name))
      // Close suggestions panel entirely after sending
      setSuggestions([])
      saveSuggestions([])
      setSelectedSuggestions({})
      setLyricBanner(null)
    } catch {
      setError('Failed to add items to shopping list')
    }
  }

  const closeSuggestions = () => {
    setSuggestions([])
    saveSuggestions([])
    setSelectedSuggestions({})
    setLyricBanner(null)
  }

  const selectedSuggestionCount = Object.values(selectedSuggestions).filter(Boolean).length

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

  return (
    <div style={s.container}>
      {/* Header with expired + add buttons */}
      <div style={s.headerRow}>
        <span style={s.headerText}>Ingredients</span>
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
            <div key={groupName} style={{ ...s.groupSection, background: groupColor(groupName) }}>
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
                        }}>
                          {formatExpiry(ing.expiry_date)}
                        </span>
                      )}
                      <button
                        style={s.iconBtn}
                        onClick={() => startEdit(ing)}
                        title="Edit"
                      >
                        <Pencil size={12} />
                      </button>
                      <button
                        style={s.iconBtn}
                        onClick={(e) => handleDelete(ing.id, e)}
                        title="Delete"
                      >
                        <Trash2 size={12} />
                      </button>
                    </div>
                    {/* Delete-to-shopping popup */}
                    {deletePopup?.id === ing.id && (
                      <div style={s.deletePopup} onClick={(e) => e.stopPropagation()}>
                        <span style={s.deletePopupText}>Add to shopping list?</span>
                        <button style={s.deletePopupYes} onClick={handleAddToShoppingFromDelete}>Yes</button>
                        <button style={s.deletePopupNo} onClick={() => setDeletePopup(null)}>No</button>
                      </div>
                    )}
                  </div>
                )
              ))}
            </div>
          )
        })}
        {/* Show delete popup for items already removed from list */}
        {deletePopup && !ingredients.find(i => i.id === deletePopup.id) && (
          <div style={s.deletePopup} onClick={(e) => e.stopPropagation()}>
            <span style={s.deletePopupText}>Add "{deletePopup.name}" to shopping list?</span>
            <button style={s.deletePopupYes} onClick={handleAddToShoppingFromDelete}>Yes</button>
            <button style={s.deletePopupNo} onClick={() => setDeletePopup(null)}>No</button>
          </div>
        )}
      </div>

      {/* Expiry detail panel — 3-way radio buttons */}
      {expiryPanelOpen && (
        <div style={s.expiryPanel}>
          <div style={s.expiryPanelHeader}>
            <button style={s.closeBtn} onClick={() => setExpiryPanelOpen(false)}>
              <X size={16} />
            </button>
            <span style={s.expiryPanelTitle}>Expired Items</span>
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

      {/* Shopping suggestions section */}
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
          {suggestionsLoading
            ? <><Loader size={13} style={{ animation: 'spin 1s linear infinite' }} /> Thinking…</>
            : suggestions.length > 0
              ? <><Sparkles size={13} /> Suggest More</>
              : <><Sparkles size={13} /> Suggest Shopping</>}
        </button>
        {lyricBanner && (
          <div style={s.lyricBanner}>{lyricBanner}</div>
        )}
      </div>

      {/* Suggestions list (persisted in localStorage) */}
      {suggestions.length > 0 && (
        <div style={s.suggestionsPanel}>
          <div style={s.suggestionsPanelHeader}>
            <span style={s.suggestionsPanelTitle}>Suggestions</span>
            <button style={s.closeBtn} onClick={closeSuggestions}>
              <X size={14} />
            </button>
          </div>
          <div style={s.suggestionsList}>
            {suggestions.map((item, idx) => (
              <label key={idx} style={s.suggestionRow}>
                <input
                  type="checkbox"
                  checked={!!selectedSuggestions[idx]}
                  onChange={() => toggleSuggestion(idx)}
                  style={s.checkbox}
                />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={s.suggestionName}>{item.name}</div>
                  {item.reason && <div style={s.suggestionReason}>{item.reason}</div>}
                </div>
              </label>
            ))}
          </div>
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
        </div>
      )}

      {/* Shopping list overlay */}
      <ShoppingListPanel
        open={shoppingListOpen}
        onClose={() => setShoppingListOpen(false)}
        onBought={() => { load(); refreshExpiredCount() }}
      />
    </div>
  )
})

export default IngredientPanel
