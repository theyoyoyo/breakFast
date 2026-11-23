/**
 * Tests for chat sync across devices: the open chat reloads when the page becomes visible,
 * when its socket reconnects and on a session_updated push for it, without losing the draft
 * or a streaming reply; analysis results and meal card edits are saved to the session;
 * the 💊 list reloads on a supplements push and when the page becomes visible, and other
 * notices reach the rest of the app; "Today I ate" saves its version with the card, opens
 * from it, and drops unsaved edits on Close; the selected meal card is the same on every
 * device, and a second tap unselects it. Prep plans in the new format are colored by dish,
 * while older plans and lyric fallbacks render as plain Markdown. A socket that closes before
 * it ever opened checks the session once before it reconnects, and a refused one stops reconnecting.
 * API calls and the chat socket are mocked — no real network calls are made.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, waitFor, fireEvent, act } from '@testing-library/react'
import ChatInterface from './ChatInterface'
import MarkdownText from './MarkdownText'
import { LYRIC_PLAN, OLD_PLAN, PLAN } from '../utils/prepPlan.fixtures'
import {
  createChatSocket, checkAuth, getActiveSession, createSession, deleteSession, listSessions, getSessionMessages,
  saveSessionMessage, updateSessionMessage, saveAteDraft, selectSessionMessage, analyzeMeal, getTodaySupplements, toggleSupplement,
  checkMissingIngredients, getRatings, logMeal,
} from '../services/api'
import { SYNC_NOTICE_EVENT } from '../hooks/useSyncNotice'

vi.mock('../services/api', () => ({
  createChatSocket: vi.fn(),
  checkAuth: vi.fn(),
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
  getFavorites: vi.fn(() => Promise.resolve([])),
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

// Fake chat sockets: each records the handlers it was created with and its event listeners
let sockets
function lastSocket() {
  return sockets[sockets.length - 1]
}
function pushSessionUpdated(sessionId) {
  act(() => lastSocket().handlers.onSessionUpdated(sessionId))
}
function pushNotice(notice) {
  act(() => lastSocket().handlers.onNotice(notice))
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
    createChatSocket.mockImplementation((handlers) => {
      const listeners = {}
      const ws = {
        readyState: WebSocket.OPEN,
        send: vi.fn(),
        close: vi.fn(),
        addEventListener: vi.fn((type, fn) => { listeners[type] = fn }),
        handlers,
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
    checkAuth.mockResolvedValue({})
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
    listSessions.mockClear()

    pushSessionUpdated('another-session')
    await waitFor(() => expect(listSessions).toHaveBeenCalledTimes(1))
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
    act(() => lastSocket().handlers.onToken('Half an ans'))
    await screen.findByText('Half an ans')
    expect(getSessionMessages).toHaveBeenCalledTimes(1)
    expect(screen.getByText('What now?')).toBeInTheDocument()

    getSessionMessages.mockResolvedValue([
      HELLO,
      { id: 4, role: 'user', content: 'What now?' },
      { id: 5, role: 'assistant', content: 'Half an answer' },
      PHONE_REPLY,
    ])
    act(() => lastSocket().handlers.onDone('Half an answer', 5))
    await screen.findByText('Fresh reply from the phone')
    expect(getSessionMessages).toHaveBeenCalledTimes(2)
    expect(screen.getByText('What now?')).toBeInTheDocument()
    expect(screen.getByText('Half an answer')).toBeInTheDocument()
  })

  // A socket the phone closed in the background reconnects as soon as the page is back, then reloads on open
  it('reconnects at once when the page returns after its socket closed', async () => {
    await renderChat()
    act(() => lastSocket().handlers.onClose())
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
    expect(updateSessionMessage).toHaveBeenCalledWith('s1', 3, expect.stringMatching(/^Try this\.\n\n```json\n/))
    expect(updateSessionMessage).toHaveBeenCalledWith('s1', 3, expect.stringContaining('"menu_name":"Edited Breakfast"'))
  })

  // A pill marked on another device shows up in the 💊 list open in "Today I ate" on a supplements push
  it('reloads the 💊 list on a supplements push', async () => {
    const MAGNESIUM = { id: 1, name: 'Magnesium', frequency: 'sometimes', taken_today: 0 }
    getTodaySupplements.mockResolvedValue([MAGNESIUM])
    await renderChat()
    fireEvent.click(screen.getByTitle('Today I ate...'))
    fireEvent.click(await screen.findByRole('button', { name: 'Supplements' }))
    expect(await screen.findByRole('button', { name: 'Magnesium' })).toBeInTheDocument()

    getTodaySupplements.mockResolvedValue([{ ...MAGNESIUM, taken_today: 1 }])
    pushNotice({ type: 'supplements_updated' })
    expect(await screen.findByRole('button', { name: '✓ Magnesium' })).toBeInTheDocument()
  })

  // A tap on a ticked daily supplement skips it for today, shown at once and saved
  it('skips a daily supplement from "Today I ate"', async () => {
    getTodaySupplements.mockResolvedValue([{ id: 4, name: 'Vitamin D', frequency: 'daily', taken_today: 1 }])
    toggleSupplement.mockResolvedValue({ status: 'ok', taken: false })
    await renderChat()
    fireEvent.click(screen.getByTitle('Today I ate...'))
    fireEvent.click(await screen.findByRole('button', { name: 'Supplements' }))
    fireEvent.click(await screen.findByRole('button', { name: '✓ Vitamin D' }))
    expect(await screen.findByRole('button', { name: 'Vitamin D' })).toHaveAttribute('aria-pressed', 'false')
    expect(toggleSupplement).toHaveBeenCalledWith(4, false)
  })

  // With an empty box the bar shows Suggest; typing turns it into Send, and an empty box brings Suggest back
  it('turns Suggest into Send while the box has text', async () => {
    await renderChat()
    const box = screen.getByPlaceholderText('What are you craving?')
    expect(screen.getByRole('button', { name: 'Suggest breakfast' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Send' })).toBeNull()

    fireEvent.change(box, { target: { value: 'eggs?' } })
    expect(screen.getByRole('button', { name: 'Send' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Suggest breakfast' })).toBeNull()

    fireEvent.change(box, { target: { value: '' } })
    expect(screen.getByRole('button', { name: 'Suggest breakfast' })).toBeInTheDocument()
  })

  // Coming back to the page reloads the 💊 list too, in case a push was missed in the background
  it('reloads the 💊 list when the page becomes visible again', async () => {
    await renderChat()
    getTodaySupplements.mockClear()
    setVisibility('visible')
    await waitFor(() => expect(getTodaySupplements).toHaveBeenCalledTimes(1))
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
    expect(saveAteDraft).toHaveBeenCalledWith('s1', 3, expect.objectContaining({ menu: [] }))

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

describe('ChatInterface ended session', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    Element.prototype.scrollIntoView = vi.fn()
    sockets = []
    createChatSocket.mockImplementation((handlers) => {
      const listeners = {}
      const ws = {
        readyState: WebSocket.CONNECTING,
        send: vi.fn(),
        close: vi.fn(),
        addEventListener: vi.fn((type, fn) => { listeners[type] = fn }),
        handlers,
        listeners,
      }
      sockets.push(ws)
      return ws
    })
    getActiveSession.mockResolvedValue({ id: 's1' })
    listSessions.mockResolvedValue([{ id: 's1' }])
    getSessionMessages.mockResolvedValue([HELLO])
    getTodaySupplements.mockResolvedValue([])
    checkAuth.mockResolvedValue({})
  })

  afterEach(() => vi.useRealTimers())

  // Close the last socket, let the session check answer, then run every pending reconnect timer
  async function closeAndWait() {
    vi.useFakeTimers()
    act(() => lastSocket().handlers.onClose())
    await act(async () => { await Promise.resolve() })
    act(() => { vi.advanceTimersByTime(60000) })
  }

  // A socket that closes before it opened checks the session once, then reconnects when it's fine
  it('checks the session once when a socket closes before it opened', async () => {
    await renderChat()
    await closeAndWait()
    expect(checkAuth).toHaveBeenCalledTimes(1)
    expect(sockets).toHaveLength(2)
  })

  // A socket that had opened reconnects as before, with no session check
  it('reconnects without a check when an opened socket closes', async () => {
    await renderChat()
    act(() => lastSocket().listeners.open())
    await closeAndWait()
    expect(checkAuth).not.toHaveBeenCalled()
    expect(sockets).toHaveLength(2)
  })

  // A refused session check stops the reconnects, since the app leaves for the login
  it('stops reconnecting when the session check is refused', async () => {
    checkAuth.mockRejectedValue(Object.assign(new Error('API error 401'), { status: 401 }))
    await renderChat()
    await closeAndWait()
    expect(checkAuth).toHaveBeenCalledTimes(1)
    expect(sockets).toHaveLength(1)
    expect(vi.getTimerCount()).toBe(0)
  })

  // A server that can't be reached during the check still gets the usual reconnect
  it('reconnects when the session check cannot reach the server', async () => {
    checkAuth.mockRejectedValue(new Error('Cannot reach server'))
    await renderChat()
    await closeAndWait()
    expect(sockets).toHaveLength(2)
  })

  // A session check that answers after unmount sets no reconnect timer
  it('sets no timer when the check answers after unmount', async () => {
    let answer
    checkAuth.mockReturnValue(new Promise(resolve => { answer = resolve }))
    const { unmount } = render(<ChatInterface visible />)
    await screen.findByText('Hello')
    vi.useFakeTimers()
    act(() => lastSocket().handlers.onClose())
    unmount()
    await act(async () => { answer({}) })
    expect(vi.getTimerCount()).toBe(0)
    expect(sockets).toHaveLength(1)
  })
})

describe('ChatInterface prep plans', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    Element.prototype.scrollIntoView = vi.fn()
    createChatSocket.mockReturnValue({ readyState: WebSocket.OPEN, send: vi.fn(), close: vi.fn(), addEventListener: vi.fn() })
    getActiveSession.mockResolvedValue({ id: 's1' })
    listSessions.mockResolvedValue([{ id: 's1' }])
    getTodaySupplements.mockResolvedValue([])
    getSessionMessages.mockResolvedValue([
      HELLO,
      { id: 4, role: 'assistant', content: PLAN },
      { id: 5, role: 'assistant', content: OLD_PLAN },
      { id: 6, role: 'assistant', content: LYRIC_PLAN },
    ])
  })

  // A plan in the new format shows its dishes in color, while older plans and lyrics render as before
  it('colors new plans by dish and leaves older plans and lyrics plain', async () => {
    await renderChat()
    expect(screen.getByText('Greek omelette').style.color).toBe('var(--dish-2)')

    const bubbles = [['0:00 — Hard-boil eggs (7 min) [Stove]', OLD_PLAN], ['🎵 Here comes the sun, doo-doo-doo-doo', LYRIC_PLAN]]
      .map(([line, plan]) => [screen.getByText(line).closest('div[style*="border-radius"]').innerHTML, plan])
    for (const [shown, plan] of bubbles) {
      expect(shown).toBe(render(<MarkdownText text={plan} />).container.innerHTML)
    }
  })
})

describe('ChatInterface session buttons after a delete', () => {
  // The user's chats on a fake server, newest first; each holds one message naming it
  let chats

  function fakeServer(ids, activeId) {
    chats = [...ids]
    getActiveSession.mockResolvedValue({ id: activeId })
    listSessions.mockImplementation(async () => chats.map(id => ({ id })))
    getSessionMessages.mockImplementation(async (id) => [{ id: 1, role: 'user', content: `Chat ${id}` }])
    deleteSession.mockImplementation(async (id) => { chats = chats.filter(c => c !== id) })
    createSession.mockImplementation(async () => { chats = ['new', ...chats]; return { session_id: 'new' } })
  }

  const back = () => screen.queryByRole('button', { name: /Back/ })
  const next = () => screen.queryByRole('button', { name: /Next/ })

  beforeEach(() => {
    vi.clearAllMocks()
    Element.prototype.scrollIntoView = vi.fn()
    createChatSocket.mockImplementation(() => ({
      readyState: WebSocket.OPEN, send: vi.fn(), close: vi.fn(), addEventListener: vi.fn(),
    }))
    getTodaySupplements.mockResolvedValue([])
    checkAuth.mockResolvedValue({})
  })

  // Deleting a chat with chats on both sides opens the newer one, shows only Back, and Back opens the older chat
  it('refreshes Back and Next after deleting a middle chat', async () => {
    fakeServer(['s3', 's2', 's1'], 's2')
    render(<ChatInterface visible />)
    await screen.findByText('Chat s2')
    await waitFor(() => expect(next()).not.toBeNull())

    fireEvent.click(screen.getByRole('button', { name: /Del/ }))
    await screen.findByText('Chat s3')
    await waitFor(() => expect(next()).toBeNull())
    expect(back()).not.toBeNull()

    fireEvent.click(back())
    await screen.findByText('Chat s1')
    await waitFor(() => expect(back()).toBeNull())
    expect(next()).not.toBeNull()
  })

  // Deleting the newest chat opens the next older one, with only Back shown
  it('refreshes Back and Next after deleting the newest chat', async () => {
    fakeServer(['s3', 's2', 's1'], 's3')
    render(<ChatInterface visible />)
    await screen.findByText('Chat s3')
    await waitFor(() => expect(back()).not.toBeNull())

    fireEvent.click(screen.getByRole('button', { name: /Del/ }))
    await screen.findByText('Chat s2')
    await waitFor(() => expect(back()).not.toBeNull())
    expect(next()).toBeNull()
  })

  // Deleting the only chat starts a new one and hides both buttons, also when the screen still showed Back
  it('hides Back and Next after deleting the only chat', async () => {
    fakeServer(['s1', 'old'], 's1')
    render(<ChatInterface visible />)
    await screen.findByText('Chat s1')
    await waitFor(() => expect(back()).not.toBeNull())
    // Another device deletes the older chat, so this one is now the only chat
    chats = ['s1']

    fireEvent.click(screen.getByRole('button', { name: /Del/ }))
    await waitFor(() => expect(createSession).toHaveBeenCalled())
    await waitFor(() => expect(screen.queryByText('Chat s1')).toBeNull())
    await waitFor(() => expect(back()).toBeNull())
    expect(next()).toBeNull()
  })
})
