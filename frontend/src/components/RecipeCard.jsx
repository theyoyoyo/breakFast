import { rateMeal } from '../services/api'
import { useState } from 'react'

const s = {
  card: {
    background: 'var(--surface2)',
    borderRadius: 'var(--radius)',
    padding: 20,
    display: 'flex',
    flexDirection: 'column',
    gap: 14,
  },
  title: {
    fontSize: 18,
    fontWeight: 700,
    color: 'var(--accent)',
  },
  description: {
    color: 'var(--text-muted)',
    fontSize: 13,
  },
  section: {
    display: 'flex',
    flexDirection: 'column',
    gap: 6,
  },
  sectionLabel: {
    fontSize: 11,
    fontWeight: 700,
    textTransform: 'uppercase',
    letterSpacing: '0.08em',
    color: 'var(--text-muted)',
  },
  list: {
    listStyle: 'none',
    display: 'flex',
    flexDirection: 'column',
    gap: 4,
  },
  listItem: {
    fontSize: 13,
    color: 'var(--text)',
    paddingLeft: 12,
    position: 'relative',
  },
  bullet: {
    position: 'absolute',
    left: 0,
    color: 'var(--accent)',
  },
  prepTime: {
    fontSize: 13,
    color: 'var(--text-muted)',
  },
  nutritionNote: {
    fontSize: 13,
    color: '#7ec8a4',
    fontStyle: 'italic',
  },
  ratingRow: {
    display: 'flex',
    gap: 8,
    alignItems: 'center',
  },
  ratingBtn: (active) => ({
    background: active ? 'var(--accent)' : 'var(--surface)',
    border: '1px solid var(--border)',
    borderRadius: 8,
    padding: '6px 14px',
    color: 'var(--text)',
    fontSize: 16,
    transition: 'background 0.15s',
  }),
}

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
