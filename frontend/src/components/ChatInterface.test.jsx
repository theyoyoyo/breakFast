/**
 * Tests for chat sync across devices: the open chat reloads when the page becomes visible,
 * when its socket reconnects and on a session_updated push for it, without losing the draft
 * or a streaming reply; analysis results and meal card edits are saved to the session;
 * the 💊 list reloads on a supplements push and when the page becomes visible, and other
 * notices reach the rest of the app; "Today I ate" saves its version with the card, opens
 * from it, and drops unsaved edits on Close; the selected meal card is the same on every
 * device, and a second tap unselects it.
 * API calls and the chat socket are mocked — no real network calls are made.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent, act } from '@testing-library/react'
import ChatInterface from './ChatInterface'
import {
  createChatSocket, getActiveSession, listSessions, getSessionMessages,
  saveSessionMessage, updateSessionMessage, saveAteDraft, selectSessionMessage, analyzeMeal, getTodaySupplements,
  checkMissingIngredients, getRatings, logMeal,
} from '../services/api'
import { SYNC_NOTICE_EVENT } from '../hooks/useSyncNotice'

vi.mock('../services/api', () => ({
  createChatSocket: vi.fn(),
  getActiveSession: vi.fn(),
  createSession: vi.fn(),
  deleteSession: vi.fn(),
  listSessions: vi.fn(),
  getSessionMessages: vi.fn(),
  saveSessionMessage: vi.fn(),
  updateSessionMessage: vi.fn(),
  saveAteDraft: vi.fn(),
  selectSessionMessage: vi.fn(),
  getTodaySupplements: vi.fn(),
  toggleSupplement: vi.fn(),
  analyzeMeal: vi.fn(),
  getSchedule: vi.fn(),
  // "Today I ate" (DecidePanel and its MealEditor)
  checkMissingIngredients: vi.fn(),
  getRatings: vi.fn(),
  createRating: vi.fn(),
  logMeal: vi.fn(),
  addFavorite: vi.fn(),
  deleteFavorite: vi.fn(),
}))

// The card itself is MealBlock's and MealEditor's business; here it only exposes its callbacks
vi.mock('./MealBlock', () => ({
  default: ({ meal, checked, onSave, onAnalyze, onCheck }) => (
    <div>
      <span>Card: {meal.menu_name}</span>
      {checked && <span>Selected</span>}
      <button onClick={() => onSave({ ...meal, menu_name: 'Edited Breakfast' })}>Save card</button>
      <button onClick={onAnalyze}>Analyze card</button>
      <button onClick={onCheck}>Select card</button>
    </div>
  ),
}))

const HELLO = { id: 1, role: 'user', content: 'Hello' }
const PHONE_REPLY = { id: 2, role: 'assistant', content: 'Fresh reply from the phone' }
const MEAL = { id: 7, menu_name: 'Test Breakfast', menu: [{ name: 'Olives', amount: 5, unit: 'pcs', ingredients: [] }] }
const MEAL_MSG = { id: 3, role: 'assistant', content: 'Try this.\n\n```json\n' + JSON.stringify(MEAL) + '\n```' }

// Fake chat sockets: each records the callbacks it was created with and its event listeners
let sockets
function lastSocket() {
  return sockets[sockets.length - 1]
}
function pushSessionUpdated(sessionId) {
  act(() => lastSocket().callbacks[7](sessionId))
}
function pushNotice(notice) {
  act(() => lastSocket().callbacks[8](notice))
}

function setVisibility(state) {
  Object.defineProperty(document, 'visibilityState', { configurable: true, get: () => state })
  act(() => { document.dispatchEvent(new Event('visibilitychange')) })
}

async function renderChat() {
  render(<ChatInterface visible />)
  await screen.findByText('Hello')
}

describe('ChatInterface sync', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    Element.prototype.scrollIntoView = vi.fn()
    sockets = []
    createChatSocket.mockImplementation((...callbacks) => {
      const listeners = {}
      const ws = {
        readyState: WebSocket.OPEN,
        send: vi.fn(),
        close: vi.fn(),
        addEventListener: vi.fn((type, fn) => { listeners[type] = fn }),
        callbacks,
        listeners,
      }
      sockets.push(ws)
      return ws
    })
    getActiveSession.mockResolvedValue({ id: 's1' })
    listSessions.mockResolvedValue([{ id: 's1' }])
    getSessionMessages.mockResolvedValueOnce([HELLO]).mockResolvedValue([HELLO, PHONE_REPLY])
    saveSessionMessage.mockResolvedValue({ status: 'ok', id: 9 })
    updateSessionMessage.mockResolvedValue({ status: 'ok' })
    getTodaySupplements.mockResolvedValue([])
    saveAteDraft.mockResolvedValue({ status: 'ok' })
    selectSessionMessage.mockResolvedValue({ status: 'ok' })
    checkMissingIngredients.mockResolvedValue({ missing: [] })
    getRatings.mockResolvedValue([])
  })

  // Coming back to the page (phone app resumed) reloads the open chat from the server
  it('reloads the open chat when the page becomes visible again', async () => {
    await renderChat()
    setVisibility('visible')
    await screen.findByText('Fresh reply from the phone')
    expect(getSessionMessages).toHaveBeenCalledTimes(2)
    expect(getSessionMessages).toHaveBeenLastCalledWith('s1')
  })

  // A push for the chat on screen reloads it; a push for another chat only refreshes Back / Next
  it('reloads on session_updated for the open chat only', async () => {
    await renderChat()
    const listCalls = listSessions.mock.calls.length

    pushSessionUpdated('another-session')
    await waitFor(() => expect(listSessions.mock.calls.length).toBe(listCalls + 1))
    expect(getSessionMessages).toHaveBeenCalledTimes(1)

    pushSessionUpdated('s1')
    await screen.findByText('Fresh reply from the phone')
    expect(getSessionMessages).toHaveBeenCalledTimes(2)
  })

  // An unsent draft stays in the input when the chat reloads
  it('keeps an unsent draft through a reload', async () => {
    await renderChat()
    const input = screen.getByPlaceholderText('What are you craving?')
    fireEvent.change(input, { target: { value: 'half a thought' } })
    pushSessionUpdated('s1')
    await screen.findByText('Fresh reply from the phone')
    expect(input).toHaveValue('half a thought')
  })

  // A push during a streaming reply waits for the reply's done, then reloads
  it('waits for a streaming reply before reloading', async () => {
    await renderChat()
    fireEvent.change(screen.getByPlaceholderText('What are you craving?'), { target: { value: 'What now?' } })
    fireEvent.click(screen.getByRole('button', { name: 'Send' }))
    expect(lastSocket().send).toHaveBeenCalled()

    pushSessionUpdated('s1')
    act(() => lastSocket().callbacks[0]('Half an ans'))
    await screen.findByText('Half an ans')
    expect(getSessionMessages).toHaveBeenCalledTimes(1)
    expect(screen.getByText('What now?')).toBeInTheDocument()

    getSessionMessages.mockResolvedValue([
      HELLO,
      { id: 4, role: 'user', content: 'What now?' },
      { id: 5, role: 'assistant', content: 'Half an answer' },
      PHONE_REPLY,
    ])
    act(() => lastSocket().callbacks[1]('Half an answer', 5))
    await screen.findByText('Fresh reply from the phone')
    expect(getSessionMessages).toHaveBeenCalledTimes(2)
    expect(screen.getByText('What now?')).toBeInTheDocument()
    expect(screen.getByText('Half an answer')).toBeInTheDocument()
  })

  // A socket the phone closed in the background reconnects as soon as the page is back, then reloads on open
  it('reconnects at once when the page returns after its socket closed', async () => {
    await renderChat()
    act(() => lastSocket().callbacks[4]()) // onClose
    expect(sockets).toHaveLength(1)

    setVisibility('visible')
    expect(sockets).toHaveLength(2)
    expect(getSessionMessages).toHaveBeenCalledTimes(1) // waits for the new socket to open

    act(() => lastSocket().listeners.open())
    await screen.findByText('Fresh reply from the phone')
  })

  // A meal card edit rewrites the card's meal block in its saved message, keeping the text
  it('saves a meal card edit into its message', async () => {
    getSessionMessages.mockReset().mockResolvedValue([HELLO, MEAL_MSG])
    await renderChat()
    fireEvent.click(await screen.findByRole('button', { name: 'Save card' }))

    await screen.findByText('Card: Edited Breakfast')
    expect(updateSessionMessage).toHaveBeenCalledTimes(1)
    const [sessionId, messageId, content] = updateSessionMessage.mock.calls[0]
    expect([sessionId, messageId]).toEqual(['s1', 3])
    expect(content.startsWith('Try this.\n\n```json\n')).toBe(true)
    expect(JSON.parse(content.match(/```json\s*([\s\S]*?)\s*```/)[1]).menu_name).toBe('Edited Breakfast')
  })

  // A pill marked on another device shows up in the open 💊 list on a supplements push
  it('reloads the 💊 list on a supplements push', async () => {
    const MAGNESIUM = { id: 1, name: 'Magnesium', frequency: 'sometimes', taken_today: 0 }
    getTodaySupplements.mockResolvedValue([MAGNESIUM])
    await renderChat()
    fireEvent.click(screen.getByTitle('Supplements'))
    expect(await screen.findByText('○ Magnesium')).toBeInTheDocument()

    getTodaySupplements.mockResolvedValue([{ ...MAGNESIUM, taken_today: 1 }])
    pushNotice({ type: 'supplements_updated' })
    expect(await screen.findByText('✓ Magnesium')).toBeInTheDocument()
  })

  // Coming back to the page reloads the 💊 list too, in case a push was missed in the background
  it('reloads the 💊 list when the page becomes visible again', async () => {
    await renderChat()
    const calls = getTodaySupplements.mock.calls.length
    setVisibility('visible')
    await waitFor(() => expect(getTodaySupplements.mock.calls.length).toBe(calls + 1))
  })

  // A notice that isn't about the chat is passed to the rest of the app as one window event
  it('passes other notices to the app as a window event', async () => {
    const seen = []
    const listener = (e) => seen.push(e.detail)
    window.addEventListener(SYNC_NOTICE_EVENT, listener)
    try {
      await renderChat()
      pushNotice({ type: 'shopping_suggestions_updated' })
      expect(seen).toEqual([{ type: 'shopping_suggestions_updated' }])
    } finally {
      window.removeEventListener(SYNC_NOTICE_EVENT, listener)
    }
  })

  // Open "Today I ate" from the meal card
  async function openTodayIAte() {
    fireEvent.click(await screen.findByRole('button', { name: 'Select card' }))
    fireEvent.click(screen.getByTitle('Today I ate...'))
    return screen.findByText('Today I ate')
  }

  // Save stores the edited meal with the card's message and closes; the panel opens from it next time
  it('saves "Today I ate" with its card, closes and opens from it', async () => {
    getSessionMessages.mockReset().mockResolvedValue([HELLO, MEAL_MSG])
    await renderChat()
    await openTodayIAte()
    fireEvent.click(screen.getAllByTitle('Delete')[0]) // remove Olives
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))
    await waitFor(() => expect(screen.queryByText('Today I ate')).toBeNull())
    expect(saveAteDraft).toHaveBeenCalledTimes(1)
    const [sessionId, messageId, meal] = saveAteDraft.mock.calls[0]
    expect([sessionId, messageId, meal.menu]).toEqual(['s1', 3, []])

    fireEvent.click(screen.getByTitle('Today I ate...'))
    await screen.findByText('Today I ate')
    expect(screen.queryByText('Olives')).toBeNull()
  })

  // Close drops edits that weren't saved
  it('drops unsaved "Today I ate" edits on Close', async () => {
    getSessionMessages.mockReset().mockResolvedValue([HELLO, MEAL_MSG])
    await renderChat()
    await openTodayIAte()
    fireEvent.click(screen.getAllByTitle('Delete')[0]) // remove Olives
    expect(screen.queryByText('Olives')).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Close' }))
    fireEvent.click(screen.getByTitle('Today I ate...'))
    expect(await screen.findByText('Olives')).toBeInTheDocument()
    expect(saveAteDraft).not.toHaveBeenCalled()
  })

  // A version saved on another device arrives with the messages; the panel opens from it
  it('opens "Today I ate" from a version saved on another device', async () => {
    const savedOnPhone = { ...MEAL, menu: [{ name: 'Honey', amount: 1, unit: 'tbsp', ingredients: [] }] }
    getSessionMessages.mockReset()
      .mockResolvedValueOnce([HELLO, MEAL_MSG])
      .mockResolvedValue([HELLO, { ...MEAL_MSG, ate_draft: savedOnPhone }])
    await renderChat()
    pushSessionUpdated('s1')
    await waitFor(() => expect(getSessionMessages).toHaveBeenCalledTimes(2))
    await openTodayIAte()
    expect(screen.getByText('Honey')).toBeInTheDocument()
    expect(screen.queryByText('Olives')).toBeNull()
  })

  // Logging the meal unselects its card and clears its saved version, on every device
  it('clears the saved version and the selection once the meal is logged', async () => {
    getSessionMessages.mockReset().mockResolvedValue([HELLO, { ...MEAL_MSG, selected: true, ate_draft: MEAL }])
    getRatings.mockResolvedValue([{ product_name: 'Olives' }]) // nothing to rate: Confirm logs at once
    logMeal.mockResolvedValue({})
    await renderChat()
    expect(await screen.findByText('Selected')).toBeInTheDocument()
    fireEvent.click(screen.getByTitle('Today I ate...'))
    const confirm = await screen.findByRole('button', { name: 'Confirm' })
    await waitFor(() => expect(confirm).toBeEnabled())
    fireEvent.click(confirm)
    await waitFor(() => expect(saveAteDraft).toHaveBeenCalledWith('s1', 3, null))
    expect(logMeal).toHaveBeenCalledTimes(1)
    expect(selectSessionMessage).toHaveBeenLastCalledWith('s1', null)
    expect(screen.queryByText('Selected')).toBeNull()
  })

  // Selecting a card tells the server (so other devices follow), and a second tap unselects it
  it('selects a card on every device and unselects it with a second tap', async () => {
    getSessionMessages.mockReset().mockResolvedValue([HELLO, MEAL_MSG])
    await renderChat()
    const select = await screen.findByRole('button', { name: 'Select card' })
    fireEvent.click(select)
    expect(screen.getByText('Selected')).toBeInTheDocument()
    expect(selectSessionMessage).toHaveBeenLastCalledWith('s1', 3)
    fireEvent.click(select)
    expect(screen.queryByText('Selected')).toBeNull()
    expect(selectSessionMessage).toHaveBeenLastCalledWith('s1', null)
  })

  // A card selected on another device arrives with the messages and is selected here too
  it('follows the card selected on another device', async () => {
    getSessionMessages.mockReset()
      .mockResolvedValueOnce([HELLO, MEAL_MSG])
      .mockResolvedValue([HELLO, { ...MEAL_MSG, selected: true }])
    await renderChat()
    await screen.findByText('Card: Test Breakfast')
    expect(screen.queryByText('Selected')).toBeNull()
    pushSessionUpdated('s1')
    expect(await screen.findByText('Selected')).toBeInTheDocument()
  })

  // An analysis result is saved to the session, so reloads and the other device show it
  it('saves analysis results to the session', async () => {
    getSessionMessages.mockReset().mockResolvedValue([HELLO, MEAL_MSG])
    analyzeMeal.mockResolvedValue({ analysis_text: 'Lots of protein.' })
    await renderChat()
    fireEvent.click(await screen.findByRole('button', { name: 'Analyze card' }))

    await screen.findByText('Lots of protein.', { exact: false })
    expect(saveSessionMessage).toHaveBeenCalledWith('s1', 'assistant', '📊 Test Breakfast — Nutrition Analysis\n\nLots of protein.')
  })
})
