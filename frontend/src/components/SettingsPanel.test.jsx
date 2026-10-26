/**
 * Tests for Settings: supplements start as Daily with no frequency picker, and show
 * "Occasional" for occasional ones; the theme picker offers all five themes; the tab title is the app name.
 * API calls are mocked — no real network calls are made.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import SettingsPanel from './SettingsPanel'
import * as api from '../services/api'

vi.mock('../services/api', () => {
  const ok = (value) => vi.fn(() => Promise.resolve(value))
  return {
    getRatings: ok([]), createRating: ok({}), updateRating: ok({}), deleteRating: ok({}),
    getProfile: ok(null), upsertProfile: ok({}),
    getSupplements: ok([]), createSupplement: ok({}), updateSupplement: ok({}), deleteSupplement: ok({}),
    getMeals: ok([]), updateMeal: ok({}), deleteMeal: ok({}), deleteOldMeals: ok({}),
    getHealthRules: ok([]), createHealthRule: ok({}), updateHealthRule: ok({}), deleteHealthRule: ok({}),
    addFavorite: ok({}),
    getPreferences: ok([]), setPreference: ok({}),
    analyzeMeal: ok({}),
    getWeeklyReview: ok(null), generateWeeklyReview: ok({}),
    getKitchenAppliances: ok([]), toggleKitchenAppliance: ok({}),
  }
})

describe('SettingsPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    api.getSupplements.mockResolvedValue([])
  })

  it('adds a supplement as Daily without asking for a frequency', async () => {
    render(<SettingsPanel visible />)
    const name = await screen.findByPlaceholderText('Supplement name…')
    expect(screen.queryByRole('option', { name: /sometimes/i })).toBeNull()
    fireEvent.change(name, { target: { value: 'Vitamin D' } })
    fireEvent.click(screen.getAllByRole('button', { name: '+' }).at(-1))
    await waitFor(() => expect(api.createSupplement).toHaveBeenCalledWith('Vitamin D', '', 'daily'))
  })

  it('labels occasional supplements "Occasional"', async () => {
    api.getSupplements.mockResolvedValue([ // Settings loads on mount and when shown
      { id: 1, name: 'Magnesium', contents: '', frequency: 'sometimes' },
      { id: 2, name: 'Omega-3', contents: '', frequency: 'daily' },
    ])
    render(<SettingsPanel visible />)
    expect(await screen.findByRole('button', { name: 'Occasional' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Daily' })).toBeInTheDocument()
  })

  it('titles the tab with the app name, like Chat', async () => {
    render(<SettingsPanel visible />)
    expect(await screen.findByText('break FAST')).toBeInTheDocument()
    expect(screen.queryByText('Settings')).toBeNull()
  })

  it('offers all five themes', async () => {
    render(<SettingsPanel visible />)
    for (const label of ['Orange', 'Green', 'Teal', 'Blue', 'Purple']) {
      expect(await screen.findByRole('button', { name: label })).toBeInTheDocument()
    }
  })
})
