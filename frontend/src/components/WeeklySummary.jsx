import { useState, useEffect } from 'react'
import { getWeeklyReview, generateWeeklyReview } from '../services/api'
import * as s from './WeeklySummary.styles'

export default function WeeklySummary({ onBack }) {
  const [review, setReview] = useState(null)
  const [loading, setLoading] = useState(true)
  const [generating, setGenerating] = useState(false)
  const [error, setError] = useState(null)

  // Load cached review on mount
  useEffect(() => {
    getWeeklyReview()
      .then(setReview)
      .catch((err) => {
        if (!err?.message?.includes('404')) {
          setError('Failed to load weekly review.')
        }
        // 404 = no review yet, that's fine
      })
      .finally(() => setLoading(false))
  }, [])

  const handleGenerate = async () => {
    setGenerating(true)
    setError(null)
    try {
      const data = await generateWeeklyReview()
      setReview(data)
    } catch (err) {
      if (err?.message?.includes('404')) {
        setError('No meals logged in the last 7 days.')
      } else if (err?.message?.includes('503')) {
        setError('AI is currently unavailable. Try again later.')
      } else {
        setError('Failed to generate weekly review.')
      }
    } finally {
      setGenerating(false)
    }
  }

  return (
    <div style={s.container}>
      <div style={s.header}>
        <button style={s.backBtn} onClick={onBack}>←</button>
        <span>Weekly Summary</span>
      </div>

      <div style={s.body}>
        {loading && <span style={s.empty}>Loading…</span>}

        {!loading && error && (
          <div style={s.noDataCard}>{error}</div>
        )}

        {!loading && review && (
          <div style={s.reviewSection}>
            {review.narrative && (
              <div style={s.narrative}>{review.narrative}</div>
            )}

            {review.scores?.length > 0 && (
              <div style={s.scoreGrid}>
                {review.scores.map((item, idx) => (
                  <div key={idx} style={s.scoreCard(item.score)}>
                    <span style={s.scoreLabel}>{item.label}</span>
                    <span style={s.scoreValue(item.score)}>{item.score}</span>
                    {item.note && <span style={s.scoreNote}>{item.note}</span>}
                  </div>
                ))}
              </div>
            )}

            <div style={s.reviewActions}>
              {review.week_key && (
                <span style={s.weekLabel}>{review.week_key}</span>
              )}
              <button
                style={s.refreshBtn}
                onClick={handleGenerate}
                disabled={generating}
              >
                {generating ? '…' : '↺ Analyze again'}
              </button>
            </div>
          </div>
        )}

        {!loading && !review && !error && (
          <div style={s.noDataCard}>
            No analysis yet for this week.
          </div>
        )}

        {/* Analyze button — shown when no review exists or after loading */}
        {!loading && !review && (
          <button
            style={{ ...s.refreshBtn, alignSelf: 'center', marginTop: 8 }}
            onClick={handleGenerate}
            disabled={generating}
          >
            {generating ? 'Analyzing…' : 'Analyze this week'}
          </button>
        )}

        {generating && (
          <span style={s.empty}>Analyzing your week…</span>
        )}
      </div>
    </div>
  )
}
