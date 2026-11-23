/**
 * Tests for the main path through the chat: a typed message goes out on the socket and its reply
 * streams in, Stop keeps what came so far, an error frame shows as the reply, the chat's sessions
 * switch with Back / Next, start with New and go with Del; a Suggest press shows its progress and
 * then the meal card, selected, which a tap unselects and whose edits are saved with its message.
 * These tests check what the user sees and what reaches the server, not how it looks.
 * API calls and the chat socket are mocked — no real network calls are made.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent, act } from '@testing-library/react'
import ChatInterface from './ChatInterface'
import { OMELETTE_MENU, PLATE_MENU, suggestionReply } from './meals.fixtures'
import {
  createChatSocket, getActiveSession, listSessions, getSessionMessages, createSession, deleteSession,
  selectSessionMessage, updateSessionMessage, checkMissingIngredients, getTodaySupplements,
} from '../services/api'

vi.mock('../services/api', () => ({
  createChatSocket: vi.fn(),
  checkAuth: vi.fn(() => Promise.resolve({})),
  getActiveSession: vi.fn(),
  createSession: vi.fn(),
  deleteSession: vi.fn(),
  listSessions: vi.fn(),
  getSessionMessages: vi.fn(),
  saveSessionMessage: vi.fn(() => Promise.resolve({ status: 'ok', id: 99 })),
  updateSessionMessage: vi.fn(() => Promise.resolve({ status: 'ok' })),
  saveAteDraft: vi.fn(() => Promise.resolve({ status: 'ok' })),
  selectSessionMessage: vi.fn(() => Promise.resolve({ status: 'ok' })),
  getTodaySupplements: vi.fn(),
  toggleSupplement: vi.fn(),
  analyzeMeal: vi.fn(),
  getSchedule: vi.fn(),
  checkMissingIngredients: vi.fn(),
  getRatings: vi.fn(() => Promise.resolve([])),
  createRating: vi.fn(),
  logMeal: vi.fn(),
  addFavorite: vi.fn(),
  deleteFavorite: vi.fn(),
  getFavorites: vi.fn(() => Promise.resolve([])),
}))

const BOX = 'What are you craving?'

// The fake chat socket: it keeps the handlers it was created with and every frame sent on it
let socket
function fakeSocket(handlers) {
  const listeners = {}
  socket = {
    readyState: WebSocket.OPEN,
    handlers,
    listeners,
    frames: [],
    send: vi.fn((data) => socket.frames.push(JSON.parse(data))),
    close: vi.fn(),
    addEventListener: vi.fn((type, fn) => { listeners[type] = fn }),
  }
  return socket
}

// A frame from the server, through the handler named for it
function serverSends(handler, ...args) {
  act(() => socket.handlers[handler](...args))
}

// The user's chats, newest first, and each one's saved messages
let sessions
const MESSAGES = {
  s1: [{ id: 1, role: 'user', content: 'Older chat question' }, { id: 2, role: 'assistant', content: 'Older chat answer' }],
  s2: [{ id: 3, role: 'user', content: 'Hello' }],
}

async function renderChat(props = {}) {
  const view = render(<ChatInterface visible {...props} />)
  await screen.findByText('Hello')
  return view
}

function type(text) {
  fireEvent.change(screen.getByPlaceholderText(BOX), { target: { value: text } })
}

beforeEach(() => {
  vi.clearAllMocks()
  Element.prototype.scrollIntoView = vi.fn()
  createChatSocket.mockImplementation(fakeSocket)
  sessions = [{ id: 's2' }, { id: 's1' }]
  getActiveSession.mockResolvedValue({ id: 's2' })
  listSessions.mockImplementation(() => Promise.resolve([...sessions]))
  getSessionMessages.mockImplementation((id) => Promise.resolve(MESSAGES[id] ?? []))
  createSession.mockImplementation(() => {
    sessions = [{ id: 's3' }, ...sessions]
    return Promise.resolve({ session_id: 's3' })
  })
  deleteSession.mockImplementation((id) => {
    sessions = sessions.filter(s => s.id !== id)
    return Promise.resolve({ status: 'ok' })
  })
  getTodaySupplements.mockResolvedValue([])
  checkMissingIngredients.mockResolvedValue({ missing: [] })
})

describe('ChatInterface sending a message', () => {
  // Send puts the message on screen and on the socket for this chat, and the box empties
  it('sends a typed message for the open chat', async () => {
    await renderChat()
    type('Something with eggs?')
    fireEvent.click(screen.getByRole('button', { name: 'Send' }))
    expect(screen.getByText('Something with eggs?')).toBeInTheDocument()
    expect(socket.frames).toEqual([{ message: 'Something with eggs?', session_id: 's2' }])
    expect(screen.getByPlaceholderText(BOX)).toHaveValue('')
  })

  // Enter sends too, while Shift+Enter leaves the message in the box
  it('sends on Enter but not on Shift+Enter', async () => {
    await renderChat()
    type('Coffee first')
    fireEvent.keyDown(screen.getByPlaceholderText(BOX), { key: 'Enter', shiftKey: true })
    expect(socket.frames).toEqual([])
    fireEvent.keyDown(screen.getByPlaceholderText(BOX), { key: 'Enter' })
    expect(socket.frames).toEqual([{ message: 'Coffee first', session_id: 's2' }])
  })

  // A blank message isn't sent
  it('does not send a blank message', async () => {
    await renderChat()
    type('   ')
    fireEvent.keyDown(screen.getByPlaceholderText(BOX), { key: 'Enter' })
    expect(socket.send).not.toHaveBeenCalled()
  })

  // The reply shows "Thinking…", then grows with each token, and done leaves it in the chat with the box free again
  it('streams the reply in and keeps it once done', async () => {
    await renderChat()
    type('Something warm?')
    fireEvent.click(screen.getByRole('button', { name: 'Send' }))
    expect(screen.getByText('Thinking…')).toBeInTheDocument()
    expect(screen.getByPlaceholderText(BOX)).toBeDisabled()

    serverSends('onToken', 'How about ')
    expect(screen.getByText('How about')).toBeInTheDocument()
    expect(screen.queryByText('Thinking…')).toBeNull()
    serverSends('onToken', 'porridge?')
    expect(screen.getByText('How about porridge?')).toBeInTheDocument()

    serverSends('onDone', 'How about porridge?', 11)
    expect(screen.getAllByText('How about porridge?')).toHaveLength(1)
    expect(screen.getByPlaceholderText(BOX)).toBeEnabled()
    expect(screen.getByRole('button', { name: 'Suggest breakfast' })).toBeInTheDocument()
  })

  // A second message can't go out while a reply is still coming
  it('sends nothing else while a reply is streaming', async () => {
    await renderChat()
    type('First')
    fireEvent.keyDown(screen.getByPlaceholderText(BOX), { key: 'Enter' })
    type('Second')
    fireEvent.keyDown(screen.getByPlaceholderText(BOX), { key: 'Enter' })
    expect(socket.frames).toEqual([{ message: 'First', session_id: 's2' }])
  })

  // A message typed before the socket opened goes out once it opens
  it('sends once the socket opens when it was still connecting', async () => {
    createChatSocket.mockImplementation((handlers) => ({ ...fakeSocket(handlers), readyState: WebSocket.CONNECTING }))
    await renderChat()
    const connecting = socket
    type('Early bird')
    fireEvent.click(screen.getByRole('button', { name: 'Send' }))
    expect(connecting.send).not.toHaveBeenCalled()
    expect(screen.getByText('Thinking…')).toBeInTheDocument()
    act(() => connecting.listeners.open())
    expect(connecting.frames).toContainEqual({ message: 'Early bird', session_id: 's2' })
  })

  // A reply the server refused (its chat was deleted meanwhile) shows its text as the reply, and the chat stops waiting
  it('shows an error frame as the reply', async () => {
    await renderChat()
    type('Still there?')
    fireEvent.click(screen.getByRole('button', { name: 'Send' }))
    serverSends('onDone', 'This chat was deleted.')
    expect(screen.getByText('This chat was deleted.')).toBeInTheDocument()
    expect(screen.getByPlaceholderText(BOX)).toBeEnabled()
  })
})

describe('ChatInterface Stop', () => {
  // Stop keeps what came so far, marked as stopped, and the late done of that reply adds nothing
  it('keeps the partial reply and ignores its late done', async () => {
    await renderChat()
    type('Tell me a long story')
    fireEvent.click(screen.getByRole('button', { name: 'Send' }))
    serverSends('onToken', 'Once upon a time')
    fireEvent.click(screen.getByRole('button', { name: 'Stop' }))

    expect(screen.getByText('Once upon a time')).toBeInTheDocument()
    expect(screen.getByText('[stopped]')).toBeInTheDocument()
    expect(screen.getByPlaceholderText(BOX)).toBeEnabled()

    serverSends('onToken', ', there was')
    serverSends('onDone', 'Once upon a time, there was a toast.', 12)
    expect(screen.queryByText('Once upon a time, there was a toast.')).toBeNull()
    expect(screen.queryByText(/there was/)).toBeNull()
  })

  // Stop before any token shows only the stopped mark
  it('shows the stopped mark when no token came yet', async () => {
    await renderChat()
    type('Quick one')
    fireEvent.click(screen.getByRole('button', { name: 'Send' }))
    fireEvent.click(screen.getByRole('button', { name: 'Stop' }))
    expect(screen.getByText('[stopped]')).toBeInTheDocument()
    expect(screen.queryByText('Thinking…')).toBeNull()
  })

  // After a stopped reply's done, the next message streams its reply as usual
  it('takes the next message after a stopped reply', async () => {
    await renderChat()
    type('One')
    fireEvent.click(screen.getByRole('button', { name: 'Send' }))
    fireEvent.click(screen.getByRole('button', { name: 'Stop' }))
    serverSends('onDone', 'Ignored reply', 12)

    type('Two')
    fireEvent.click(screen.getByRole('button', { name: 'Send' }))
    serverSends('onDone', 'Second reply', 14)
    expect(screen.getByText('Second reply')).toBeInTheDocument()
    expect(screen.queryByText('Ignored reply')).toBeNull()
    expect(socket.frames).toEqual([{ message: 'One', session_id: 's2' }, { message: 'Two', session_id: 's2' }])
  })
})

describe('ChatInterface sessions', () => {
  // Back opens the older chat and tells the socket, then Next returns to the newer one
  it('moves between chats with Back and Next', async () => {
    await renderChat()
    expect(screen.queryByRole('button', { name: /Next/ })).toBeNull() // the newest chat has no Next

    fireEvent.click(screen.getByRole('button', { name: /Back/ }))
    expect(await screen.findByText('Older chat answer')).toBeInTheDocument()
    expect(screen.queryByText('Hello')).toBeNull()
    expect(socket.frames).toContainEqual({ session_id: 's1' })
    await waitFor(() => expect(screen.queryByRole('button', { name: /Back/ })).toBeNull()) // the oldest has no Back

    fireEvent.click(screen.getByRole('button', { name: /Next/ }))
    expect(await screen.findByText('Hello')).toBeInTheDocument()
    expect(screen.queryByText('Older chat answer')).toBeNull()
  })

  // New starts an empty chat with the welcome line and tells the socket, and messages then go to it
  it('starts a new chat with New', async () => {
    await renderChat()
    type('half-typed')
    fireEvent.click(screen.getByRole('button', { name: /New/ }))
    await waitFor(() => expect(screen.queryByText('Hello')).toBeNull())
    expect(screen.getByText(/Good morning!/)).toBeInTheDocument()
    expect(screen.getByPlaceholderText(BOX)).toHaveValue('')
    expect(socket.frames).toContainEqual({ session_id: 's3' })

    type('Fresh start')
    fireEvent.click(screen.getByRole('button', { name: 'Send' }))
    expect(socket.frames).toContainEqual({ message: 'Fresh start', session_id: 's3' })
  })

  // Del removes the open chat on the server and opens the next one in the list
  it('deletes the open chat and opens the one beside it', async () => {
    await renderChat()
    fireEvent.click(screen.getByRole('button', { name: /Del/ }))
    expect(await screen.findByText('Older chat answer')).toBeInTheDocument()
    expect(deleteSession).toHaveBeenCalledWith('s2')
    expect(screen.queryByText('Hello')).toBeNull()
    expect(createSession).not.toHaveBeenCalled()
  })

  // Deleting the only chat starts a new, empty one
  it('starts a new chat when the only one is deleted', async () => {
    sessions = [{ id: 's2' }]
    await renderChat()
    fireEvent.click(screen.getByRole('button', { name: /Del/ }))
    await waitFor(() => expect(screen.queryByText('Hello')).toBeNull())
    expect(deleteSession).toHaveBeenCalledWith('s2')
    expect(createSession).toHaveBeenCalledTimes(1)
    expect(screen.getByText(/Good morning!/)).toBeInTheDocument()
    expect(socket.frames).toContainEqual({ session_id: 's3' })
  })
})

describe('ChatInterface Suggest', () => {
  const REPLY = suggestionReply('A warm omelette with toast on the side.', OMELETTE_MENU)

  // Run a Suggest press through to its card: progress, the saved reply, then the meal
  async function suggestThrough() {
    fireEvent.click(screen.getByRole('button', { name: 'Suggest breakfast' }))
    serverSends('onProgress', 'drafting')
    serverSends('onDone', REPLY, 12)
    serverSends('onMealLogged', OMELETTE_MENU)
    return screen.findByText('Sunday Omelette')
  }

  // A press sends a suggest request for this chat and shows each pipeline step while it runs
  it('sends a suggest request and shows its progress', async () => {
    await renderChat()
    fireEvent.click(screen.getByRole('button', { name: 'Suggest breakfast' }))
    expect(socket.frames).toEqual([{ message: 'Suggest Breakfast', type: 'suggest', session_id: 's2' }])
    expect(screen.getByText('Suggest Breakfast')).toBeInTheDocument()
    expect(screen.getByText('Thinking…')).toBeInTheDocument()
    serverSends('onProgress', 'drafting')
    expect(screen.getByText('Drafting…')).toBeInTheDocument()
    serverSends('onProgress', 'analyzing')
    expect(screen.getByText('Analyzing nutrition…')).toBeInTheDocument()
    serverSends('onProgress', 'finalizing')
    expect(screen.getByText('Final touches…')).toBeInTheDocument()
  })

  // The reply's text shows without its JSON, and the meal arrives as a card with its items, selected for today
  it('shows the meal card selected under the reply', async () => {
    const onMealLogged = vi.fn()
    await renderChat({ onMealLogged })
    await suggestThrough()

    expect(screen.getByText('A warm omelette with toast on the side.')).toBeInTheDocument()
    expect(screen.queryByText(/menu_name/)).toBeNull()
    expect(screen.queryByText('Drafting…')).toBeNull()
    expect(screen.getByText('Veggie omelette, Toast, Olives')).toBeInTheDocument()
    expect(screen.getByTitle("Selected as today's meal — tap to unselect")).toBeInTheDocument()
    expect(onMealLogged).toHaveBeenCalledWith(expect.objectContaining({ menu_name: 'Sunday Omelette' }))
  })

  // A tap on the selected card's box unselects it on every device, and another tap selects it again
  it('unselects and reselects the new card', async () => {
    await renderChat()
    await suggestThrough()
    fireEvent.click(screen.getByTitle("Selected as today's meal — tap to unselect"))
    expect(screen.getByTitle("Select as today's meal")).toBeInTheDocument()
    expect(selectSessionMessage).toHaveBeenLastCalledWith('s2', null)
    fireEvent.click(screen.getByTitle("Select as today's meal"))
    expect(screen.getByTitle("Selected as today's meal — tap to unselect")).toBeInTheDocument()
    expect(selectSessionMessage).toHaveBeenLastCalledWith('s2', 12)
  })

  // A second suggestion's card takes the selection from the first
  it('selects the newest card', async () => {
    await renderChat()
    await suggestThrough()
    fireEvent.click(screen.getByRole('button', { name: 'Suggest breakfast' }))
    serverSends('onDone', suggestionReply('Something lighter.', PLATE_MENU), 13)
    serverSends('onMealLogged', PLATE_MENU)
    await screen.findByText('Quick Plate')
    expect(screen.getAllByTitle("Select as today's meal")).toHaveLength(1)
    expect(screen.getAllByTitle("Selected as today's meal — tap to unselect")).toHaveLength(1)
    expect(screen.getByText('Cheese, Tomato')).toBeInTheDocument()
  })

  // An amount edited in the card's editor is saved into the card's message, so other devices get it
  it('saves an edit made in the card into its message', async () => {
    await renderChat()
    fireEvent.click(await suggestThrough())
    fireEvent.change(screen.getByDisplayValue('6'), { target: { value: '8' } }) // Olives
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))
    await waitFor(() => expect(updateSessionMessage).toHaveBeenCalledWith(
      's2', 12, expect.stringContaining('"name":"Olives","amount":8'),
    ))
    expect(updateSessionMessage).toHaveBeenCalledWith(
      's2', 12, expect.stringMatching(/^A warm omelette with toast on the side\.\n\n```json\n/),
    )
    expect(screen.queryByRole('button', { name: 'Save' })).toBeNull() // the editor closed
  })
})
