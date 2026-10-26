import { useState, useEffect, useCallback } from 'react'
import { getFavorites, deleteFavorite, updateFavorite } from '../services/api'
import { formatIngredient } from '../utils/ingredients'
import MealEditor from './MealEditor'
import * as s from './FavoritesPanel.styles'

export default function FavoritesPanel({ visible, onSendToChat }) {
  const [favorites, setFavorites] = useState([])
  const [expandedId, setExpandedId] = useState(null)
  const [editingId, setEditingId] = useState(null)

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
    // Map menu_items → menu so ChatInterface renders dishes correctly
    const meal = { ...fav, menu: fav.menu_items || fav.menu || undefined }
    onSendToChat?.(meal)
  }

  const handleEditorSave = async (updated) => {
    try {
      await updateFavorite(editingId, {
        ...updated,
        menu_items: updated.menu || updated.menu_items || null,
      })
      setFavorites(prev => prev.map(f => f.id === editingId ? { ...f, ...updated } : f))
    } catch { /* ignore */ }
    setEditingId(null)
  }

  if (favorites.length === 0) {
    return (
      <div style={s.container}>
        <div style={s.header}>Favorites</div>
        <div style={s.empty}>No favorites yet. Use ⭐ Save on a meal to save it here.</div>
      </div>
    )
  }

  return (
    <div style={s.container}>
      <div style={s.header}>Favorites</div>
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
                <span style={s.cardName}>{fav.meal_name}</span>
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
                            {item.amount != null ? `${item.amount} ${item.unit || ''} ` : '🍳 '}{item.name}
                          </span>
                        ))
                      : displayItems.map((ing, i) => (
                          <span key={i} style={s.ingredientChip}>{formatIngredient(ing)}</span>
                        ))
                    }
                  </div>
                  <div style={s.cardActions}>
                    <button style={s.sendBtn} onClick={() => handleSendToChat(fav)} title="Send to chat as suggestion">
                      🫕 Send to Chat
                    </button>
                    <button style={s.editBtn} onClick={() => setEditingId(fav.id)} title="Edit this favorite">
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
                    <MealEditor
                      meal={{ ...fav, menu: fav.menu_items || undefined }}
                      onSave={handleEditorSave}
                      onClose={() => setEditingId(null)}
                      showPrepTime={true}
                      editPrepTime={true}
                      menuMode={isMenuFormat}
                      checkFridge
                      canMarkObtained={false}
                    />
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
