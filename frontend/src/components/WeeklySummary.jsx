import { useState, useEffect } from 'react'
import { getWeeklyMeals, analyzeMeal } from '../services/api'
import { formatIngredient } from '../utils/ingredients'
import * as s from './WeeklySummary.styles'

/**
 * Format a date string to Turkish locale short format.
 */
function formatDate(dateStr) {
  try {
    return new Date(dateStr).toLocaleDateString('tr-TR', {
      weekday: 'short', day: 'numeric', month: 'short',
    })
  } catch {
    return dateStr
  }
}

export default function WeeklySummary({ onBack }) {
  const [meals, setMeals] = useState([])
  const [loading, setLoading] = useState(true)
  const [analyzingId, setAnalyzingId] = useState(null)
  const [expandedId, setExpandedId] = useState(null)

  useEffect(() => {
    getWeeklyMeals()
      .then(setMeals)
      .catch(() => setMeals([]))
      .finally(() => setLoading(false))
  }, [])

  const handleAnalyze = async (meal) => {
    setAnalyzingId(meal.id)
    try {
      const result = await analyzeMeal(meal.meal_name, meal.ingredients, meal.id)
      setMeals(prev => prev.map(m =>
        m.id === meal.id
          ? { ...m, cached_nutrition: { analysis_text: result.analysis_text, analysis_data: result.analysis_data } }
          : m
      ))
    } catch { /* Analysis failed */ }
    setAnalyzingId(null)
  }

  return (
    <div style={s.container}>
      <div style={s.header}>
        <button style={s.backBtn} onClick={onBack}>←</button>
        <span>Weekly Summary ({meals.length})</span>
      </div>
      <div style={s.body}>
        {loading && <span style={s.empty}>Loading...</span>}
        {!loading && meals.length === 0 && <span style={s.empty}>No recent consecutive meals</span>}
        {meals.map((meal) => {
          const nutrition = meal.cached_nutrition
          const expanded = expandedId === meal.id
          return (
            <div key={meal.id} style={s.mealCard}>
              <div style={s.mealHeader} onClick={() => setExpandedId(expanded ? null : meal.id)}>
                <div style={s.mealInfo}>
                  <span style={s.mealDate}>{formatDate(meal.logged_at)}</span>
                  <span style={s.mealName}>{meal.meal_name}</span>
                  {meal.prep_time_min && <span style={s.prepBadge}>⏱ {meal.prep_time_min}m</span>}
                </div>
                <div style={s.mealBadges}>
                  {nutrition ? (
                    <span style={s.analyzedBadge}>Analyzed</span>
                  ) : (
                    <button
                      style={s.analyzeBtn}
                      onClick={(e) => { e.stopPropagation(); handleAnalyze(meal) }}
                      disabled={analyzingId === meal.id}
                    >
                      {analyzingId === meal.id ? '...' : 'Analyze'}
                    </button>
                  )}
                  <span style={s.expandIcon}>{expanded ? '▼' : '▶'}</span>
                </div>
              </div>

              {expanded && (
                <div style={s.mealExpanded}>
                  <div style={s.ingredientList}>
                    {(meal.ingredients || []).map((item, idx) => (
                      <span key={idx} style={s.ingredientTag}>{formatIngredient(item)}</span>
                    ))}
                  </div>

                  {nutrition ? (
                    <div style={s.nutritionSection}>
                      {nutrition.analysis_data && (
                        <div style={s.macroRow}>
                          {nutrition.analysis_data.macros?.calories_kcal != null && (
                            <span style={s.macroTag}>{nutrition.analysis_data.macros.calories_kcal} kcal</span>
                          )}
                          {nutrition.analysis_data.macros?.protein_g != null && (
                            <span style={s.macroTag}>{nutrition.analysis_data.macros.protein_g}g protein</span>
                          )}
                          {nutrition.analysis_data.macros?.carbs_g != null && (
                            <span style={s.macroTag}>{nutrition.analysis_data.macros.carbs_g}g carbs</span>
                          )}
                          {nutrition.analysis_data.macros?.fat_g != null && (
                            <span style={s.macroTag}>{nutrition.analysis_data.macros.fat_g}g fat</span>
                          )}
                        </div>
                      )}
                      {nutrition.analysis_text && (
                        <div style={s.analysisText}>{nutrition.analysis_text}</div>
                      )}
                    </div>
                  ) : (
                    <span style={s.notAnalyzed}>Not analyzed</span>
                  )}
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
