/**
 * Tests for the Weekly Summary page (#206): a week without meals gets a pop-up instead of an analysis,
 * and the nudge to run one shows while the server asks for it and clears once the analysis runs.
 * API calls are mocked — no real network calls are made.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import WeeklySummary from './WeeklySummary'
import * as api from '../services/api'

vi.mock('../services/api', () => ({
  getWeeklyReview: vi.fn(),
  generateWeeklyReview: vi.fn(),
  getWeeklyReviewStatus: vi.fn(),
}))

function refused(status) {
  const err = new Error(`API error ${status}`)
  err.status = status
  return err
}

const REVIEW = {
  narrative: 'A steady week.',
  scores: [{ label: 'Variety', score: 70, note: 'Some repeats.' }],
  week_key: '2026-W48',
  cached: false,
}

describe('WeeklySummary', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    api.getWeeklyReview.mockRejectedValue(refused(404))
    api.getWeeklyReviewStatus.mockResolvedValue({ nudge: false })
  })

  // A week without meals is refused by the server, and the page says so in a pop-up instead of showing an analysis
  it('shows a pop-up when no meals were logged in the last 7 days', async () => {
    api.generateWeeklyReview.mockRejectedValue(refused(422))
    render(<WeeklySummary onBack={() => {}} />)
    fireEvent.click(await screen.findByRole('button', { name: 'Analyze this week' }))

    const dialog = await screen.findByRole('alertdialog')
    expect(dialog).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Cancel' })).toBeNull() // a notice: nothing to decide
    expect(screen.queryByText(REVIEW.narrative)).toBeNull()

    fireEvent.click(screen.getByRole('button', { name: 'OK' }))
    await waitFor(() => expect(screen.queryByRole('alertdialog')).toBeNull())
  })

  // The nudge shows while the server asks for an analysis and clears once one has run
  it('shows the nudge until the analysis runs', async () => {
    api.getWeeklyReviewStatus.mockResolvedValue({ nudge: true })
    api.generateWeeklyReview.mockResolvedValue(REVIEW)
    render(<WeeklySummary onBack={() => {}} />)

    expect(await screen.findByRole('status')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Analyze this week' }))

    expect(await screen.findByText(REVIEW.narrative)).toBeInTheDocument()
    expect(screen.queryByRole('status')).toBeNull()
    expect(screen.queryByRole('alertdialog')).toBeNull()
  })

  // Without the server asking for one, there is no nudge
  it('shows no nudge when the latest analysis is up to date', async () => {
    api.getWeeklyReview.mockResolvedValue({ ...REVIEW, cached: true })
    render(<WeeklySummary onBack={() => {}} />)
    expect(await screen.findByText(REVIEW.narrative)).toBeInTheDocument()
    await waitFor(() => expect(api.getWeeklyReviewStatus).toHaveBeenCalled())
    expect(screen.queryByRole('status')).toBeNull()
  })
})
