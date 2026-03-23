import { useState, useEffect, useCallback } from 'react'
import { getFavorites, deleteFavorite } from '../services/api'
import * as s from './FavoritesPanel.styles'

function formatIngredient(item) {
  if (typeof item === 'object' && item !== null && item.name) {
    const qty = item.quantity != null ? item.quantity : ''
    const unit = item.unit || ''
    return `${qty} ${unit} ${item.name}`.trim()
  }
  return String(item)
}

export default function FavoritesPanel({ visible, onSendToChat }) {
  const [favorites, setFavorites] = useState([])
  const [expandedId, setExpandedId] = useState(null)

  const load = useCallback(async () => {
    try {
      setFavorites(await getFavorites())
    } catch { /* Backend not available */ }
  }, [])

  // Reload when tab becomes visible
  useEffect(() => {
    if (visible) load()
  }, [visible, load])

  const handleRemove = async (id) => {
    try {
      await deleteFavorite(id)
      setFavorites(prev => prev.filter(f => f.id !== id))
    } catch { /* ignore */ }
  }

  const handleSendToChat = (meal) => {
    onSendToChat?.(meal)
  }

  if (favorites.length === 0) {
    return (
      <div style={s.container}>
        <div style={s.header}>Favorites</div>
        <div style={s.empty}>No favorites yet. Star a meal to save it here.</div>
      </div>
    )
  }

  return (
    <div style={s.container}>
      <div style={s.header}>Favorites</div>
      <div style={s.list}>
        {favorites.map(fav => {
          const expanded = expandedId === fav.id
          const ingredients = Array.isArray(fav.ingredients) ? fav.ingredients : []
          return (
            <div key={fav.id} style={s.card}>
              <div style={s.cardHeader} onClick={() => setExpandedId(expanded ? null : fav.id)}>
                <span style={s.cardName}>{fav.meal_name}</span>
                <span style={s.cardMeta}>
                  {fav.prep_time_min && `⏱ ${fav.prep_time_min}m`}
                  {' '}{expanded ? '▲' : '▼'}
                </span>
              </div>
              {expanded && (
                <div style={s.cardBody}>
                  {fav.description && <div style={s.description}>{fav.description}</div>}
                  <div style={s.ingredientList}>
                    {ingredients.map((ing, i) => (
                      <span key={i} style={s.ingredientChip}>{formatIngredient(ing)}</span>
                    ))}
                  </div>
                  <div style={s.cardActions}>
                    <button style={s.sendBtn} onClick={() => handleSendToChat(fav)} title="Send to chat as suggestion">
                      💬 Send to Chat
                    </button>
                    <button style={s.removeBtn} onClick={() => handleRemove(fav.id)} title="Remove from favorites">
                      ✕
                    </button>
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
