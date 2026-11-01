/**
 * Tests for Settings: supplements start as Daily with no frequency picker, show
 * "Occasional" for occasional ones, and can be edited with ✏️; the theme picker offers all five themes;
 * the tab title is the app name; the optional country saves with the profile.
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
    api.getProfile.mockResolvedValue(null)
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

  // ✏️ opens an editor for the name and contents and saves both, keeping the frequency
  it("edits a supplement's name and contents", async () => {
    api.getSupplements.mockResolvedValue([{ id: 4, name: 'Vitamn D', contents: '', frequency: 'sometimes' }])
    render(<SettingsPanel visible />)
    fireEvent.click(await screen.findByTitle('Edit supplement'))
    fireEvent.change(screen.getByLabelText('Name'), { target: { value: 'Vitamin D' } })
    fireEvent.change(screen.getByLabelText('Contents'), { target: { value: 'D3 1000 IU' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))
    await waitFor(() => expect(api.updateSupplement).toHaveBeenCalledWith(
      4, { name: 'Vitamin D', contents: 'D3 1000 IU', frequency: 'sometimes' },
    ))
    await waitFor(() => expect(screen.queryByLabelText('Contents')).toBeNull())
  })

  it('titles the tab with the app name, like Chat', async () => {
    render(<SettingsPanel visible />)
    expect(await screen.findByText('break FAST')).toBeInTheDocument()
    expect(screen.queryByText('Settings')).toBeNull()
  })

  it('names the weekly review toggle after what it does', async () => {
    render(<SettingsPanel visible />)
    expect(await screen.findByText('Weekly review in suggestions')).toBeInTheDocument()
  })

  it('saves the optional country with the profile', async () => {
    render(<SettingsPanel visible />)
    const country = await screen.findByLabelText('Country')
    fireEvent.change(country, { target: { value: 'Türkiye' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save Profile' }))
    await waitFor(() => expect(api.upsertProfile).toHaveBeenCalledWith(
      expect.objectContaining({ country: 'Türkiye' }),
    ))
  })

  it('does not mark a profile without a country as incomplete', async () => {
    api.getProfile.mockResolvedValue({
      age: 30, gender: 'male', height_cm: 180, weight_kg: 80, activity_level: 'moderate', country: null,
    })
    render(<SettingsPanel visible />)
    expect(await screen.findByLabelText('Country')).toHaveValue('')
    await waitFor(() => expect(screen.getByDisplayValue('30')).toBeInTheDocument())
    expect(screen.queryByText('●')).toBeNull()
  })

  it('offers all five themes', async () => {
    render(<SettingsPanel visible />)
    for (const label of ['Orange', 'Green', 'Teal', 'Blue', 'Purple']) {
      expect(await screen.findByRole('button', { name: label })).toBeInTheDocument()
    }
  })
})
