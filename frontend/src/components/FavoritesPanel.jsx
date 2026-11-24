import { useState, useEffect, useCallback, useMemo } from 'react'
import { getFavorites, deleteFavorite, updateFavorite } from '../services/api'
import { formatIngredient, localizeUnit } from '../utils/ingredients'
import { mealEmoji } from '../utils/emoji'
import { useMealReadiness } from '../hooks/useMealReadiness'
import { useLanguage } from '../hooks/useLanguage'
import MealEditor from './MealEditor'
import ReadinessIcon from './ReadinessIcon'
import EmojiPicker from './EmojiPicker'
import * as s from './FavoritesPanel.styles'

// A favorite's icon (its saved one, else one from its id) with the same fridge-readiness badge as chat cards
function FavoriteIcon({ fav, checkKey }) {
  const { readiness, stillMissing } = useMealReadiness(fav, checkKey)
  return <ReadinessIcon emoji={mealEmoji(fav, fav.id)} readiness={readiness} stillMissing={stillMissing} />
}

function Header() {
  return (
    <div style={s.header}>
      <span style={s.tabName}>Favorites</span>
    </div>
  )
}

export default function FavoritesPanel({ visible, onSendToChat }) {
  const [favorites, setFavorites] = useState([])
  const [expandedId, setExpandedId] = useState(null)
  const [editingId, setEditingId] = useState(null)
  // Set when Save tried another favorite's name; the editor stays open for a new one
  const [nameTaken, setNameTaken] = useState(false)
  // The icon picked in the open editor (set when it opens), saved with the editor's Save (#244)
  const [editEmoji, setEditEmoji] = useState(null)
  const language = useLanguage()

  // One meal object per edit, so a re-render (like the taken-name note) keeps the editor's edits
  const editingMeal = useMemo(() => {
    const fav = favorites.find(f => f.id === editingId)
    return fav ? { ...fav, menu: fav.menu_items || undefined } : null
  }, [favorites, editingId])
  useEffect(() => { setNameTaken(false) }, [editingId])

  const load = useCallback(async () => {
    try {
      setFavorites(await getFavorites())
    } catch { /* Backend not available */ }
  }, [])

  useEffect(() => {
    if (visible) load()
  }, [visible, load])

  const handleRemove = async (id) => {
    try {
      await deleteFavorite(id)
      setFavorites(prev => prev.filter(f => f.id !== id))
      if (editingId === id) setEditingId(null)
    } catch { /* ignore */ }
  }

  const handleSendToChat = (fav) => {
    // Map menu_items → menu so ChatInterface renders dishes correctly; the card shows the favorite's icon
    const meal = { ...fav, menu: fav.menu_items || fav.menu || undefined, emoji: mealEmoji(fav, fav.id) }
    onSendToChat?.(meal)
  }

  const handleEditorSave = async (updated) => {
    const saved = { ...updated, emoji: editEmoji || updated.emoji }
    try {
      await updateFavorite(editingId, {
        ...saved,
        menu_items: saved.menu || saved.menu_items || null,
      })
      setFavorites(prev => prev.map(f => f.id === editingId ? { ...f, ...saved } : f))
    } catch (err) {
      if (err?.status === 409) {
        setNameTaken(true)
        return
      }
    }
    setEditingId(null)
  }

  if (favorites.length === 0) {
    return (
      <div style={s.container}>
        <Header />
        <div style={s.empty}>No favorites yet. Use the ☆ beside a meal&apos;s name to save it here.</div>
      </div>
    )
  }

  return (
    <div style={s.container}>
      <Header />
      <div style={s.list}>
        {favorites.map(fav => {
          const expanded = expandedId === fav.id
          const editing = editingId === fav.id
          const menuItems = fav.menu_items
          const isMenuFormat = menuItems && menuItems.length > 0
          // Display: menu item names if menu format, else flat ingredients
          const displayItems = isMenuFormat
            ? menuItems
            : (Array.isArray(fav.ingredients) ? fav.ingredients : [])

          return (
            <div key={fav.id} style={s.card}>
              <div style={s.cardHeader} onClick={() => { setExpandedId(expanded ? null : fav.id); if (editing) setEditingId(null) }}>
                <span style={s.cardTitle}>
                  <FavoriteIcon fav={fav} checkKey={visible} />
                  <span style={s.cardName}>{fav.meal_name}</span>
                  <span style={s.cardId}>#{fav.id}</span>
                </span>
                <span style={s.cardMeta}>
                  {fav.prep_time_min && `⏱ ${fav.prep_time_min}m`}
                  {' '}{expanded ? '▲' : '▼'}
                </span>
              </div>

              {expanded && !editing && (
                <div style={s.cardBody}>
                  {fav.description && <div style={s.description}>{fav.description}</div>}
                  <div style={s.ingredientList}>
                    {isMenuFormat
                      ? menuItems.map((item, i) => (
                          <span key={i} style={s.ingredientChip}>
                            {item.amount != null ? `${item.amount} ${localizeUnit(item.unit || '', language)} ` : '🍳 '}{item.name}
                          </span>
                        ))
                      : displayItems.map((ing, i) => (
                          <span key={i} style={s.ingredientChip}>{formatIngredient(ing, language)}</span>
                        ))
                    }
                  </div>
                  <div style={s.cardActions}>
                    <button style={s.sendBtn} onClick={() => handleSendToChat(fav)} title="Send to chat as suggestion">
                      🫕 Send to Chat
                    </button>
                    <button style={s.editBtn} onClick={() => { setEditingId(fav.id); setEditEmoji(mealEmoji(fav, fav.id)) }} title="Edit this favorite">
                      ✏️ Edit
                    </button>
                    <button style={s.removeBtn} onClick={() => handleRemove(fav.id)} title="Remove from favorites">
                      🗑️
                    </button>
                  </div>
                </div>
              )}

              {editing && (
                <div style={s.overlay} onClick={(e) => { if (e.target === e.currentTarget) setEditingId(null) }}>
                  <div style={s.overlayPanel}>
                    <EmojiPicker value={editEmoji} onChange={setEditEmoji} />
                    <MealEditor
                      meal={editingMeal}
                      emoji={editEmoji}
                      onSave={handleEditorSave}
                      onClose={() => setEditingId(null)}
                      showPrepTime={true}
                      editPrepTime={true}
                      menuMode={isMenuFormat}
                      checkFridge
                      canMarkObtained={false}
                    />
                    {nameTaken && (
                      <div style={s.takenNote} role="status">
                        Another favorite already has this name. Pick a new one to save.
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
