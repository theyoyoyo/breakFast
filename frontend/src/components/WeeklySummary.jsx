import { useState, useEffect } from 'react'
import { generateWeeklyReview } from '../services/api'
import * as s from './WeeklySummary.styles'

export default function WeeklySummary({ onBack }) {
  const [review, setReview] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const load = async (force = false) => {
    setLoading(true)
    setError(null)
    try {
      const data = await generateWeeklyReview(force)
      setReview(data)
    } catch (err) {
      if (err?.message?.includes('404')) {
        setError('No meals logged in the last 7 days.')
      } else if (err?.message?.includes('503')) {
        setError('AI is currently unavailable. Try again later.')
      } else {
        setError('Failed to load weekly review.')
      }
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, []) // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div style={s.container}>
      <div style={s.header}>
        <button style={s.backBtn} onClick={onBack}>←</button>
        <span>Weekly Summary</span>
      </div>

      <div style={s.body}>
        {loading && (
          <span style={s.empty}>
            {review ? 'Refreshing…' : 'Analyzing your week…'}
          </span>
        )}

        {!loading && error && (
          <div style={s.noDataCard}>{error}</div>
        )}

        {!loading && review && (
          <div style={s.reviewSection}>
            {/* Narrative */}
            {review.narrative && (
              <div style={s.narrative}>{review.narrative}</div>
            )}

            {/* Score cards */}
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

            {/* Actions row */}
            <div style={s.reviewActions}>
              {review.week_key && (
                <span style={s.weekLabel}>{review.week_key}</span>
              )}
              <button
                style={s.refreshBtn}
                onClick={() => load(true)}
                disabled={loading}
              >
                ↺ Refresh
              </button>
            </div>
          </div>
        )}

        {!loading && !review && !error && (
          <div style={s.noDataCard}>No meals found in the last 7 days.</div>
        )}
      </div>
    </div>
  )
}
