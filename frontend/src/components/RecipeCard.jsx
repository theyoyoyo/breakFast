import { rateMeal } from '../services/api'
import { useState } from 'react'
import * as s from './RecipeCard.styles'

export default function RecipeCard({ meal, mealId }) {
  const [rated, setRated] = useState(null)

  if (!meal) return null

  const handleRate = async (rating) => {
    setRated(rating)
    if (mealId) {
      try {
        await rateMeal(mealId, rating)
      } catch {
        // non-critical
      }
    }
  }

  return (
    <div style={s.card}>
      <div>
        <div style={s.title}>{meal.meal_name}</div>
        {meal.description && <div style={s.description}>{meal.description}</div>}
      </div>

      {meal.ingredients?.length > 0 && (
        <div style={s.section}>
          <div style={s.sectionLabel}>Ingredients</div>
          <ul style={s.list}>
            {meal.ingredients.map((ing) => (
              <li key={ing} style={s.listItem}>
                <span style={s.bullet}>·</span>
                {ing}
              </li>
            ))}
          </ul>
        </div>
      )}

      {meal.steps?.length > 0 && (
        <div style={s.section}>
          <div style={s.sectionLabel}>Steps</div>
          <ol style={{ ...s.list, listStyle: 'decimal', paddingLeft: 18 }}>
            {meal.steps.map((step) => (
              <li key={step} style={{ ...s.listItem, paddingLeft: 4 }}>
                {step}
              </li>
            ))}
          </ol>
        </div>
      )}

      {meal.prep_time_min && (
        <div style={s.prepTime}>⏱ {meal.prep_time_min} minutes total</div>
      )}

      {meal.nutrition_note && (
        <div style={s.nutritionNote}>✦ {meal.nutrition_note}</div>
      )}

      <div style={s.ratingRow}>
        <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>Rate this meal:</span>
        <button
          style={s.ratingBtn(rated === 5)}
          onClick={() => handleRate(5)}
          title="Thumbs up"
        >
          👍
        </button>
        <button
          style={s.ratingBtn(rated === 1)}
          onClick={() => handleRate(1)}
          title="Thumbs down"
        >
          👎
        </button>
      </div>
    </div>
  )
}
