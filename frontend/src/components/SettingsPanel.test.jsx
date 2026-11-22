/**
 * Tests for Settings: supplements start as Daily with no frequency picker, show
 * "Occasional" for occasional ones, and can be edited with ✏️; the theme picker offers all five themes;
 * the header shows the app name and the tab's name; the optional country saves with the profile, listed as
 * "Name (CODE)" and shown as its code; the profile boxes can shrink to a phone's width; removed shopping
 * suggestions can be brought back from AI settings after an "Are you sure?" prompt; meals older than one month
 * are deleted after one too, with a note saying how many went (or that it failed), and the history reloads.
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
    api.getMeals.mockResolvedValue([])
    api.deleteOldMeals.mockResolvedValue({})
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

  // The header shows the logo, like Chat, and the tab's name at the right
  it('titles the tab with the app name and the tab name', async () => {
    render(<SettingsPanel visible />)
    const title = await screen.findByRole('img', { name: 'break FAST' })
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

  // Appearance (#235): Light paints the page light at once and is saved as the user's preference
  it('switches the appearance and saves it', async () => {
    render(<SettingsPanel visible />)
    const light = await screen.findByRole('button', { name: 'Light' })
    expect(screen.getByRole('button', { name: 'Auto' })).toHaveAttribute('aria-pressed', 'true')
    fireEvent.click(light)
    expect(document.documentElement.dataset.mode).toBe('light')
    expect(light).toHaveAttribute('aria-pressed', 'true')
    await waitFor(() => expect(api.setPreference).toHaveBeenCalledWith('appearance', 'light'))
    fireEvent.click(screen.getByRole('button', { name: 'Dark' }))
    expect(document.documentElement.dataset.mode).toBe('dark')
    localStorage.clear()
  })

  // With nothing removed in the last 7 days the button shows 0 and can't be pressed
  it('disables Bring back at 0', async () => {
    render(<SettingsPanel visible />)
    expect(await screen.findByText('Removed shopping suggestions')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Bring back (0)' })).toBeDisabled()
  })

  // The first tap only asks; Allow brings them back and the count drops to 0
  it('brings back removed suggestions after the prompt', async () => {
    api.getRemovedSuggestionCount.mockResolvedValue({ count: 3 })
    render(<SettingsPanel visible />)
    fireEvent.click(await screen.findByRole('button', { name: 'Bring back (3)' }))
    expect(screen.getByText(/Are you sure you want to allow 3 removed items back/)).toBeInTheDocument()
    expect(api.bringBackRemovedSuggestions).not.toHaveBeenCalled()
    fireEvent.click(screen.getByRole('button', { name: 'Allow' }))
    expect(await screen.findByRole('button', { name: 'Bring back (0)' })).toBeDisabled()
    expect(api.bringBackRemovedSuggestions).toHaveBeenCalledTimes(1)
    expect(screen.queryByText(/Are you sure/)).toBeNull()
  })

  // Cancel closes the prompt without bringing anything back
  it('cancels the bring-back prompt', async () => {
    api.getRemovedSuggestionCount.mockResolvedValue({ count: 1 })
    render(<SettingsPanel visible />)
    fireEvent.click(await screen.findByRole('button', { name: 'Bring back (1)' }))
    expect(screen.getByText(/allow 1 removed item back/)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))
    expect(screen.queryByText(/Are you sure/)).toBeNull()
    expect(api.bringBackRemovedSuggestions).not.toHaveBeenCalled()
  })

  // A × on another device sends a notice, and the count reloads
  it('reloads the removed count on a suggestions notice', async () => {
    render(<SettingsPanel visible />)
    await screen.findByRole('button', { name: 'Bring back (0)' })
    api.getRemovedSuggestionCount.mockResolvedValue({ count: 1 })
    act(() => emitSyncNotice({ type: 'shopping_suggestions_updated' }))
    expect(await screen.findByRole('button', { name: 'Bring back (1)' })).toBeEnabled()
  })

  // The first tap only asks; Delete removes the old meals and the note says how many
  it('deletes meals older than one month after the prompt and shows the count', async () => {
    api.deleteOldMeals.mockResolvedValue({ deleted: 2 })
    render(<SettingsPanel visible />)
    fireEvent.click(await screen.findByRole('button', { name: /Delete meals older than one month/ }))
    expect(screen.getByText(/Are you sure you want to delete every meal older than one month/)).toBeInTheDocument()
    expect(api.deleteOldMeals).not.toHaveBeenCalled()
    fireEvent.click(screen.getByRole('button', { name: 'Delete' }))
    expect(await screen.findByText('2 meals older than one month deleted')).toBeInTheDocument()
    expect(api.deleteOldMeals).toHaveBeenCalledTimes(1)
    expect(screen.queryByText(/Are you sure/)).toBeNull()
  })

  // With nothing older than a month, the note says there were none
  it('says when there were no meals older than one month', async () => {
    api.deleteOldMeals.mockResolvedValue({ deleted: 0 })
    render(<SettingsPanel visible />)
    fireEvent.click(await screen.findByRole('button', { name: /Delete meals older than one month/ }))
    fireEvent.click(screen.getByRole('button', { name: 'Delete' }))
    expect(await screen.findByText('No meals older than one month')).toBeInTheDocument()
  })

  // Cancel closes the prompt without deleting anything
  it('cancels the old-meals prompt', async () => {
    render(<SettingsPanel visible />)
    fireEvent.click(await screen.findByRole('button', { name: /Delete meals older than one month/ }))
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))
    expect(screen.queryByText(/Are you sure/)).toBeNull()
    expect(api.deleteOldMeals).not.toHaveBeenCalled()
  })

  // A delete that went through reloads the history, so its count drops the deleted meals
  it('reloads the meal history after deleting old meals', async () => {
    let rows = [{ id: 1, meal_name: 'Old' }, { id: 2, meal_name: 'New' }]
    api.getMeals.mockImplementation(() => Promise.resolve(rows))
    api.deleteOldMeals.mockImplementation(() => { rows = [{ id: 2, meal_name: 'New' }]; return Promise.resolve({ deleted: 1 }) })
    render(<SettingsPanel visible />)
    expect(await screen.findByRole('button', { name: /Meal History \(2\)/ })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /Delete meals older than one month/ }))
    fireEvent.click(screen.getByRole('button', { name: 'Delete' }))
    expect(await screen.findByText('1 meal older than one month deleted')).toBeInTheDocument()
    expect(await screen.findByRole('button', { name: /Meal History \(1\)/ })).toBeInTheDocument()
  })

  // A delete that fails says so under the button and keeps the history as it was
  it('shows a note when deleting old meals fails', async () => {
    api.getMeals.mockResolvedValue([{ id: 1, meal_name: 'Old' }])
    api.deleteOldMeals.mockRejectedValue(new Error('500'))
    render(<SettingsPanel visible />)
    expect(await screen.findByRole('button', { name: /Meal History \(1\)/ })).toBeInTheDocument()
    const loads = api.getMeals.mock.calls.length
    fireEvent.click(screen.getByRole('button', { name: /Delete meals older than one month/ }))
    fireEvent.click(screen.getByRole('button', { name: 'Delete' }))
    expect(await screen.findByText('Failed to delete old meals')).toBeInTheDocument()
    expect(api.getMeals.mock.calls.length).toBe(loads)
  })
})
