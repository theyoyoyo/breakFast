import { useState, useEffect } from 'react'
import { ShoppingCart, X, Trash2 } from 'lucide-react'
import {
  getFavoriteIngredients, removeFavoriteIngredient,
  addShoppingItem, addShoppingItemsBulk, getShoppingList,
} from '../services/api'
import * as s from './FavoriteIngredientsPanel.styles'

export default function FavoriteIngredientsPanel({ open, onClose }) {
  const [items, setItems] = useState([])
  const [shoppingNames, setShoppingNames] = useState(new Set())
  const [addedNames, setAddedNames] = useState(new Set())
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const load = async () => {
    try {
      setLoading(true)
      setError(null)
      const [favs, shopList] = await Promise.all([
        getFavoriteIngredients(),
        getShoppingList(),
      ])
      setItems(favs)
      setShoppingNames(new Set(shopList.map(i => i.item_name.toLowerCase())))
      setAddedNames(new Set())
    } catch {
      setError('Could not reach server')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (open) {
      setError(null)
      setAddedNames(new Set())
      load()
    }
  }, [open]) // eslint-disable-line react-hooks/exhaustive-deps

  const handleAddToShopping = async (name) => {
    try {
      setError(null)
      await addShoppingItem(name)
      setAddedNames(prev => new Set(prev).add(name.toLowerCase()))
      setShoppingNames(prev => new Set(prev).add(name.toLowerCase()))
    } catch {
      setError('Could not add to shopping list')
    }
  }

  const handleRemove = async (name) => {
    setItems(prev => prev.filter(i => i.ingredient_name !== name))
    try {
      await removeFavoriteIngredient(name)
    } catch {
      setError('Failed to remove')
      load()
    }
  }

  // Items not yet in the shopping list
  const addableItems = items.filter(i => !shoppingNames.has(i.ingredient_name.toLowerCase()))

  const handleAddAll = async () => {
    if (addableItems.length === 0) return
    try {
      setError(null)
      await addShoppingItemsBulk(addableItems.map(i => i.ingredient_name))
      const allNames = new Set(items.map(i => i.ingredient_name.toLowerCase()))
      setShoppingNames(prev => new Set([...prev, ...allNames]))
      setAddedNames(allNames)
    } catch {
      setError('Could not add items to shopping list')
    }
  }

  if (!open) return null

  return (
    <div style={s.overlay} onClick={onClose}>
      <div style={s.panel} onClick={(e) => e.stopPropagation()}>
        <div style={s.header}>
          <span style={s.heartIcon}>❤️</span>
          <span style={s.title}>Favorite Ingredients</span>
          {addableItems.length > 0 && (
            <button style={s.addAllBtn} onClick={handleAddAll} title="Add all to shopping list">
              Add All
            </button>
          )}
          <button style={s.closeBtn} onClick={onClose}><X size={16} /></button>
        </div>

        <div style={s.list}>
          {error && <div style={s.error}>{error}</div>}
          {loading && <div style={s.empty}>Loading...</div>}
          {!loading && items.length === 0 && (
            <div style={s.empty}>No favorites yet. Tap the heart on any ingredient to add it here.</div>
          )}
          {items.map(item => {
            const nameLower = item.ingredient_name.toLowerCase()
            const inList = shoppingNames.has(nameLower)
            const justAdded = addedNames.has(nameLower)
            return (
              <div key={item.id} style={s.row}>
                <span style={s.itemName}>{item.ingredient_name}</span>
                {inList ? (
                  <span style={s.shopBtnDone}>
                    {justAdded ? 'Added' : 'In list'}
                  </span>
                ) : (
                  <button
                    style={s.shopBtn}
                    onClick={() => handleAddToShopping(item.ingredient_name)}
                    title="Add to shopping list"
                  >
                    <ShoppingCart size={13} />
                  </button>
                )}
                <button
                  style={s.removeBtn}
                  onClick={() => handleRemove(item.ingredient_name)}
                  title="Remove from favorites"
                >
                  <Trash2 size={12} />
                </button>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
