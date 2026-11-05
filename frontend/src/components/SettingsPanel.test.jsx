/**
 * Tests for Settings: supplements start as Daily with no frequency picker, show
 * "Occasional" for occasional ones, and can be edited with ✏️; the theme picker offers all five themes;
 * the header shows the app name and the tab's name; the optional country saves with the profile, listed as
 * "Name (CODE)" and shown as its code; the profile boxes can shrink to a phone's width; removed shopping
 * suggestions can be brought back after a confirm.
 * API calls are mocked — no real network calls are made.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react'
import SettingsPanel from './SettingsPanel'
import * as api from '../services/api'
import { emitSyncNotice } from '../hooks/useSyncNotice'

vi.mock('../services/api', () => {
  const ok = (value) => vi.fn(() => Promise.resolve(value))
  return {
    getRatings: ok([]), createRating: ok({}), updateRating: ok({}), deleteRating: ok({}),
    getProfile: ok(null), upsertProfile: ok({}),
    getSupplements: ok([]), createSupplement: ok({}), updateSupplement: ok({}), deleteSupplement: ok({}),
    getMeals: ok([]), updateMeal: ok({}), deleteMeal: ok({}), deleteOldMeals: ok({}),
    getHealthRules: ok([]), createHealthRule: ok({}), updateHealthRule: ok({}), deleteHealthRule: ok({}),
    addFavorite: ok({}), deleteFavorite: ok({}), getFavorites: ok([]),
    getPreferences: ok([]), setPreference: ok({}),
    analyzeMeal: ok({}),
    getWeeklyReview: ok(null), generateWeeklyReview: ok({}),
    getKitchenAppliances: ok([]), toggleKitchenAppliance: ok({}),
    getRemovedSuggestionCount: ok({ count: 0 }), bringBackRemovedSuggestions: ok(undefined),
  }
})

describe('SettingsPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    api.getSupplements.mockResolvedValue([])
    api.getProfile.mockResolvedValue(null)
    api.getRemovedSuggestionCount.mockResolvedValue({ count: 0 })
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

  // The header shows the app name, like Chat, and the tab's name at the right
  it('titles the tab with the app name and the tab name', async () => {
    render(<SettingsPanel visible />)
    const title = await screen.findByText('break FAST')
    expect(title.nextSibling).toHaveTextContent('Settings')
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

  // The list shows "Germany (DE)", the closed box shows "DE", and the name is what's saved
  it('lists countries with their code, shows the code once chosen and saves the name', async () => {
    render(<SettingsPanel visible />)
    const country = await screen.findByLabelText('Country')
    expect(screen.getByRole('option', { name: 'Germany (DE)' })).toHaveValue('Germany')
    fireEvent.change(country, { target: { value: 'Germany' } })
    expect(country.parentElement).toHaveTextContent(/^DE▾/)
    fireEvent.click(screen.getByRole('button', { name: 'Save Profile' }))
    await waitFor(() => expect(api.upsertProfile).toHaveBeenCalledWith(
      expect.objectContaining({ country: 'Germany' }),
    ))
  })

  // A saved country that isn't in the list (an older name) stays selectable and shows as written
  it('keeps a saved country that is not in the list', async () => {
    api.getProfile.mockResolvedValue({ country: 'Atlantis' })
    render(<SettingsPanel visible />)
    const country = await screen.findByLabelText('Country')
    await waitFor(() => expect(country).toHaveValue('Atlantis'))
    expect(country.parentElement).toHaveTextContent(/^Atlantis▾/)
  })

  // At 320 px nothing may keep its native width: the columns shrink and the boxes are content-sized
  it('lets every profile box shrink to fit a 320 px screen', async () => {
    render(<SettingsPanel visible />)
    for (const label of ['Age', 'Gender', 'Height (cm)', 'Weight (kg)', 'Activity Level', 'Country']) {
      const box = await screen.findByLabelText(label)
      expect(['0', '0px'].includes(box.style.minWidth) || box.style.width === '100%', label).toBe(true)
    }
    for (const label of ['Age', 'Height (cm)', 'Weight (kg)']) {
      expect(screen.getByLabelText(label).style.width).toMatch(/^calc\(\d+ch \+ 22px\)$/)
    }
    const pair = screen.getByLabelText('Age').closest('div').parentElement.parentElement
    expect(pair.style.gridTemplateColumns).toBe('repeat(2, minmax(0, 1fr))')
  })

  // Number boxes take digits only, and weight one decimal (a comma counts as the point)
  it('keeps profile numbers to digits', async () => {
    render(<SettingsPanel visible />)
    const age = await screen.findByLabelText('Age')
    fireEvent.change(age, { target: { value: '3a5' } })
    expect(age).toHaveValue('35')
    const weight = screen.getByLabelText('Weight (kg)')
    fireEvent.change(weight, { target: { value: '72,55' } })
    expect(weight).toHaveValue('72.5')
    fireEvent.click(screen.getByRole('button', { name: 'Save Profile' }))
    await waitFor(() => expect(api.upsertProfile).toHaveBeenCalledWith(
      expect.objectContaining({ age: 35, weight_kg: 72.5 }),
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

  // With nothing removed in the last 7 days the button shows 0 and can't be pressed
  it('disables Bring back removed suggestions at 0', async () => {
    render(<SettingsPanel visible />)
    const button = await screen.findByRole('button', { name: 'Bring back removed suggestions (0)' })
    expect(button).toBeDisabled()
  })

  // The first tap only opens the confirm; Confirm brings them back and the count drops to 0
  it('brings back removed suggestions after the confirm', async () => {
    api.getRemovedSuggestionCount.mockResolvedValue({ count: 3 })
    render(<SettingsPanel visible />)
    fireEvent.click(await screen.findByRole('button', { name: 'Bring back removed suggestions (3)' }))
    expect(api.bringBackRemovedSuggestions).not.toHaveBeenCalled()
    api.getRemovedSuggestionCount.mockResolvedValue({ count: 0 })
    fireEvent.click(screen.getByRole('button', { name: 'Confirm' }))
    expect(await screen.findByRole('button', { name: 'Bring back removed suggestions (0)' })).toBeDisabled()
    expect(api.bringBackRemovedSuggestions).toHaveBeenCalledTimes(1)
    expect(screen.queryByRole('button', { name: 'Confirm' })).toBeNull()
  })

  // A tap anywhere else closes the confirm without bringing anything back, like the Fridge's delete confirm
  it('cancels the bring-back confirm on a tap elsewhere', async () => {
    api.getRemovedSuggestionCount.mockResolvedValue({ count: 2 })
    render(<SettingsPanel visible />)
    fireEvent.click(await screen.findByRole('button', { name: 'Bring back removed suggestions (2)' }))
    expect(screen.getByRole('button', { name: 'Confirm' })).toBeInTheDocument()
    await act(() => new Promise(resolve => setTimeout(resolve, 0)))  // the outside-click listener starts next tick
    fireEvent.click(document.body)
    await waitFor(() => expect(screen.queryByRole('button', { name: 'Confirm' })).toBeNull())
    expect(api.bringBackRemovedSuggestions).not.toHaveBeenCalled()
  })

  // A × on another device sends a notice, and the count reloads
  it('reloads the removed count on a suggestions notice', async () => {
    render(<SettingsPanel visible />)
    await screen.findByRole('button', { name: 'Bring back removed suggestions (0)' })
    api.getRemovedSuggestionCount.mockResolvedValue({ count: 1 })
    act(() => emitSyncNotice({ type: 'shopping_suggestions_updated' }))
    expect(await screen.findByRole('button', { name: 'Bring back removed suggestions (1)' })).toBeEnabled()
  })
})
