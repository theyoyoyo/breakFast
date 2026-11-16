// Auto-detect backend from current hostname so the app works from any IP
// (home WiFi, Tailscale, localhost) without config changes.
// VITE_BACKEND_URL in .env still overrides if explicitly set.
const BASE_URL = import.meta.env.VITE_BACKEND_URL ||
  `${window.location.protocol}//${window.location.hostname}:8000`
const WS_URL = BASE_URL.replace(/^https?/, (p) => (p === 'https' ? 'wss' : 'ws'))

// ---------------------------------------------------------------------------
// Error types
// ---------------------------------------------------------------------------

export class NetworkError extends Error {
  constructor() { super('Cannot reach server') }
}

/** Too many failed logins: `retryAfter` is the server's wait in seconds (0 when unknown). */
export class LoginLimitError extends Error {
  constructor(retryAfter) {
    super('Too many failed logins')
    this.retryAfter = retryAfter
  }
}

// ---------------------------------------------------------------------------
// Auth helpers
// ---------------------------------------------------------------------------

function getToken() {
  return localStorage.getItem('bf_token') || ''
}

function authHeaders(token = getToken()) {
  return { Authorization: `Bearer ${token}` }
}

// The server refused this device's session (it restarted, or the session was ended):
// apiFetch clears it and tells the app through one window event, so it can show the login
const SESSION_ENDED_EVENT = 'bf:session-ended'

function endSession() {
  localStorage.removeItem('bf_token')
  localStorage.removeItem('bf_user')
  window.dispatchEvent(new Event(SESSION_ENDED_EVENT))
}

/** Call `handler()` when a request is refused for an ended session; returns the unsubscribe. */
export function onSessionEnded(handler) {
  window.addEventListener(SESSION_ENDED_EVENT, handler)
  return () => window.removeEventListener(SESSION_ENDED_EVENT, handler)
}

// ---------------------------------------------------------------------------
// Shared fetch helper — avoids repeating ok-check + json() everywhere
// ---------------------------------------------------------------------------

/** Fetch a URL, throw on non-2xx, and return parsed JSON (or undefined for 204). */
async function apiFetch(url, options = {}) {
  const token = getToken()
  const headers = {
    ...authHeaders(token),
    ...(options.body ? { 'Content-Type': 'application/json' } : {}),
  }
  let r
  try {
    r = await fetch(url, { ...options, headers })
  } catch {
    throw new NetworkError()
  }
  if (!r.ok) {
    // A refused session ends here, unless a login made while the request ran stored a new one
    if (r.status === 401 && token === getToken()) endSession()
    // The status lets a caller tell a refusal (like 409, a name already taken) from other errors
    const err = new Error(`API error ${r.status}: ${url}`)
    err.status = r.status
    throw err
  }
  if (r.status === 204) return undefined
  return r.json()
}

/** POST / PUT with a JSON body. */
function json(method, body) {
  return { method, body: JSON.stringify(body) }
}

// ---------------------------------------------------------------------------
// Auth
// ---------------------------------------------------------------------------

export const login = async (name, pin) => {
  let r
  try {
    r = await fetch(`${BASE_URL}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, pin }),
    })
  } catch {
    throw new NetworkError()
  }
  if (r.status === 429) throw new LoginLimitError(Number(r.headers.get('Retry-After')) || 0)
  if (!r.ok) throw new Error('Login failed')
  return r.json()
}

/**
 * Log this device out: forget its stored session, then end it on the server too.
 * The device is logged out even when the server can't be reached or the call fails.
 * Storage is cleared before the call, so a login made while it runs keeps its new session.
 */
export const logout = async () => {
  const token = getToken()
  localStorage.removeItem('bf_token')
  localStorage.removeItem('bf_user')
  if (!token) return
  try {
    await fetch(`${BASE_URL}/auth/logout`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}` },
    })
  } catch {
    // Offline: the session ends on the server at its next restart
  }
}

export const checkAuth = () =>
  apiFetch(`${BASE_URL}/health/auth`)

// ---------------------------------------------------------------------------
// Ingredients
// ---------------------------------------------------------------------------

export const getIngredients = () =>
  apiFetch(`${BASE_URL}/ingredients/`)

export const addIngredient = (name, expiry_date = null, group_name = null) =>
  apiFetch(`${BASE_URL}/ingredients/`, json('POST', { name, expiry_date, group_name }))

export const updateIngredient = (id, data) =>
  apiFetch(`${BASE_URL}/ingredients/${id}`, json('PATCH', data))

export const deleteIngredient = (id) =>
  apiFetch(`${BASE_URL}/ingredients/${id}`, { method: 'DELETE' })

// Which of a meal's ingredients aren't in the fridge → { missing: [names] }
export const checkMissingIngredients = (meal) =>
  apiFetch(`${BASE_URL}/ingredients/check`, json('POST', { meal }))

export const getExpiredIngredients = () =>
  apiFetch(`${BASE_URL}/ingredients/expired`)

export const getExpiredCount = () =>
  apiFetch(`${BASE_URL}/ingredients/expired-count`)

export const handleExpiredAction = (delete_ids, keep_ids, shopping_ids) =>
  apiFetch(`${BASE_URL}/ingredients/expired/action`, json('POST', { delete_ids, keep_ids, shopping_ids }))

export const getShoppingSuggestions = (exclude = []) =>
  apiFetch(`${BASE_URL}/ingredients/shopping-suggestions`, json('POST', { exclude }))

// The Fridge tab's suggestions list, kept on the server → { items: [{ name, reason, checked }] }
export const getSuggestionList = () =>
  apiFetch(`${BASE_URL}/shopping/suggestions`)

// Replace the list; `removed` names were removed with × and stay out of suggestions for 7 days
export const saveSuggestionList = (items, removed = []) =>
  apiFetch(`${BASE_URL}/shopping/suggestions`, json('PUT', { items, removed }))

// How many items removed with × new suggestions leave out right now → { count }
export const getRemovedSuggestionCount = () =>
  apiFetch(`${BASE_URL}/shopping/suggestions/removed`)

// Forget the items removed with ×, so the next Suggest Shopping may bring them back
export const bringBackRemovedSuggestions = () =>
  apiFetch(`${BASE_URL}/shopping/suggestions/removed`, { method: 'DELETE' })

// ---------------------------------------------------------------------------
// Shopping List
// ---------------------------------------------------------------------------

export const getShoppingList = () =>
  apiFetch(`${BASE_URL}/shopping/`)

export const addShoppingItem = (item_name) =>
  apiFetch(`${BASE_URL}/shopping/`, json('POST', { item_name }))

export const addShoppingItemsBulk = (items) =>
  apiFetch(`${BASE_URL}/shopping/bulk`, json('POST', items.map(item_name => ({ item_name }))))

export const deleteShoppingItem = (id) =>
  apiFetch(`${BASE_URL}/shopping/${id}`, { method: 'DELETE' })

// Empty the whole shopping list (its Delete all)
export const clearShoppingList = () =>
  apiFetch(`${BASE_URL}/shopping/`, { method: 'DELETE' })

export const buyShoppingItems = (ids, expiry_dates = null) =>
  apiFetch(`${BASE_URL}/shopping/bought`, json('POST', { ids, expiry_dates }))

// ---------------------------------------------------------------------------
// Favorite Ingredients
// ---------------------------------------------------------------------------

export const getFavoriteIngredients = () =>
  apiFetch(`${BASE_URL}/favorite-ingredients/`)

export const addFavoriteIngredient = (ingredient_name) =>
  apiFetch(`${BASE_URL}/favorite-ingredients/`, json('POST', { ingredient_name }))

export const removeFavoriteIngredient = (ingredient_name) =>
  apiFetch(`${BASE_URL}/favorite-ingredients/${encodeURIComponent(ingredient_name)}`, { method: 'DELETE' })

// ---------------------------------------------------------------------------
// Kitchen Appliances
// ---------------------------------------------------------------------------

export const getKitchenAppliances = () =>
  apiFetch(`${BASE_URL}/kitchen/`)

export const toggleKitchenAppliance = (key, enabled) =>
  apiFetch(`${BASE_URL}/kitchen/${key}`, json('PUT', { enabled }))

// ---------------------------------------------------------------------------
// Meals
// ---------------------------------------------------------------------------

export const getMeals = (limit = 50) =>
  apiFetch(`${BASE_URL}/meals/?limit=${limit}`)

export const logMeal = (meal) =>
  apiFetch(`${BASE_URL}/meals/`, json('POST', meal))

export const updateMeal = (id, meal) =>
  apiFetch(`${BASE_URL}/meals/${id}`, json('PUT', meal))

export const deleteMeal = (id) =>
  apiFetch(`${BASE_URL}/meals/${id}`, { method: 'DELETE' })

export const deleteOldMeals = () =>
  apiFetch(`${BASE_URL}/meals/old`, { method: 'DELETE' })

export const getWeeklyReview = () =>
  apiFetch(`${BASE_URL}/meals/weekly-review`)

export const generateWeeklyReview = () =>
  apiFetch(`${BASE_URL}/meals/weekly-review`, { method: 'POST' })

// ---------------------------------------------------------------------------
// Preferences
// ---------------------------------------------------------------------------

export const getPreferences = () =>
  apiFetch(`${BASE_URL}/preferences/`)

// Only sends `value` — the key lives in the URL path
export const setPreference = (key, value) =>
  apiFetch(`${BASE_URL}/preferences/${encodeURIComponent(key)}`, json('PUT', { value }))

export const deletePreference = (key) =>
  apiFetch(`${BASE_URL}/preferences/${encodeURIComponent(key)}`, { method: 'DELETE' })

export const getHabits = () =>
  apiFetch(`${BASE_URL}/preferences/habits`)

export const addHabit = (description) =>
  apiFetch(`${BASE_URL}/preferences/habits`, json('POST', { description, source: 'stated' }))

export const deleteHabit = (id) =>
  apiFetch(`${BASE_URL}/preferences/habits/${id}`, { method: 'DELETE' })

// ---------------------------------------------------------------------------
// Profile
// ---------------------------------------------------------------------------

export const getProfile = () =>
  apiFetch(`${BASE_URL}/profile/`)

export const upsertProfile = (profile) =>
  apiFetch(`${BASE_URL}/profile/`, json('PUT', profile))

// ---------------------------------------------------------------------------
// Supplements
// ---------------------------------------------------------------------------

export const getSupplements = () =>
  apiFetch(`${BASE_URL}/profile/supplements`)

export const createSupplement = (name, contents = '', frequency = 'daily') =>
  apiFetch(`${BASE_URL}/profile/supplements`, json('POST', { name, contents, frequency }))

export const updateSupplement = (id, data) =>
  apiFetch(`${BASE_URL}/profile/supplements/${id}`, json('PUT', data))

export const deleteSupplement = (id) =>
  apiFetch(`${BASE_URL}/profile/supplements/${id}`, { method: 'DELETE' })

export const getTodaySupplements = () =>
  apiFetch(`${BASE_URL}/profile/supplements/today`)

export const toggleSupplement = (id, taken) =>
  apiFetch(`${BASE_URL}/profile/supplements/${id}/toggle`, json('POST', { taken }))

// ---------------------------------------------------------------------------
// Ratings
// ---------------------------------------------------------------------------

export const getRatings = () =>
  apiFetch(`${BASE_URL}/ratings/`)

export const createRating = (product_name, rating = 10) =>
  apiFetch(`${BASE_URL}/ratings/`, json('POST', { product_name, rating }))

export const updateRating = (id, rating) =>
  apiFetch(`${BASE_URL}/ratings/${id}`, json('PUT', { rating }))

export const deleteRating = (id) =>
  apiFetch(`${BASE_URL}/ratings/${id}`, { method: 'DELETE' })

// ---------------------------------------------------------------------------
// Sessions
// ---------------------------------------------------------------------------

export const getActiveSession = () =>
  apiFetch(`${BASE_URL}/sessions/active`)

export const createSession = () =>
  apiFetch(`${BASE_URL}/sessions/`, { method: 'POST' })

export const deleteSession = (sessionId) =>
  apiFetch(`${BASE_URL}/sessions/${sessionId}`, { method: 'DELETE' })

export const listSessions = () =>
  apiFetch(`${BASE_URL}/sessions/`)

export const getSessionMessages = (sessionId) =>
  apiFetch(`${BASE_URL}/sessions/${sessionId}/messages`)

// → { status, id }; the user's open chats are told the session changed.
// select: true also makes it the selected meal card (a meal sent to chat)
export const saveSessionMessage = (sessionId, role, content, select = false) =>
  apiFetch(`${BASE_URL}/sessions/${sessionId}/messages`, json('POST', select ? { role, content, select } : { role, content }))

// Select a meal card for today (its message id), or none (null); the user's other devices follow
export const selectSessionMessage = (sessionId, messageId) =>
  apiFetch(`${BASE_URL}/sessions/${sessionId}/selected`, json('PUT', { message_id: messageId }))

// Replace a saved message's content (a meal card edit rewrites its meal block)
export const updateSessionMessage = (sessionId, messageId, content) =>
  apiFetch(`${BASE_URL}/sessions/${sessionId}/messages/${messageId}`, json('PUT', { content }))

// Save a meal card's "Today I ate" version with its message; the user's other devices get it
export const saveAteDraft = (sessionId, messageId, meal) =>
  apiFetch(`${BASE_URL}/sessions/${sessionId}/messages/${messageId}`, json('PUT', { ate_draft: meal }))

// ---------------------------------------------------------------------------
// Health Rules
// ---------------------------------------------------------------------------

export const getHealthRules = () =>
  apiFetch(`${BASE_URL}/health-rules/`)

export const createHealthRule = (rule_text, priority = 'high') =>
  apiFetch(`${BASE_URL}/health-rules/`, json('POST', { rule_text, priority }))

export const updateHealthRule = (id, data) =>
  apiFetch(`${BASE_URL}/health-rules/${id}`, json('PUT', data))

export const deleteHealthRule = (id) =>
  apiFetch(`${BASE_URL}/health-rules/${id}`, { method: 'DELETE' })

// ---------------------------------------------------------------------------
// Favorites
// ---------------------------------------------------------------------------

export const getFavorites = () =>
  apiFetch(`${BASE_URL}/favorites/`)

export const addFavorite = (meal) =>
  apiFetch(`${BASE_URL}/favorites/`, json('POST', meal))

export const updateFavorite = (id, meal) =>
  apiFetch(`${BASE_URL}/favorites/${id}`, json('PUT', meal))

export const deleteFavorite = (id) =>
  apiFetch(`${BASE_URL}/favorites/${id}`, { method: 'DELETE' })

// ---------------------------------------------------------------------------
// Analyst
// ---------------------------------------------------------------------------

export const analyzeMeal = (meal_name, ingredients, meal_id = null) =>
  apiFetch(`${BASE_URL}/analyst/analyze`, json('POST', { meal_name, ingredients, meal_id }))

// ---------------------------------------------------------------------------
// Scheduler
// ---------------------------------------------------------------------------

export const getSchedule = (meal_name, steps, ingredients, meal_id = null, menu = []) =>
  apiFetch(`${BASE_URL}/scheduler/plan`, json('POST', { meal_name, steps, menu, ingredients, meal_id }))

// ---------------------------------------------------------------------------
// WebSocket chat
// ---------------------------------------------------------------------------

/**
 * Open a WebSocket to /chat. The session token goes in the Sec-WebSocket-Protocol header
 * ("bearer", then the token), the one header a page can set on a WebSocket, so it stays
 * out of the URL. Without a stored token the socket sends "bearer" alone, which the
 * server refuses (an empty subprotocol would throw).
 * onDone gets the reply and its saved message id; onSessionUpdated gets the id of a
 * session another device (or a REST save) changed; onNotice gets any other notice
 * ({ type: 'supplements_updated' }, …) for the rest of the app.
 */
export function createChatSocket(onToken, onDone, onMealLogged, onError, onClose, onProgress, onSessionUpdated, onNotice) {
  const token = getToken()
  const ws = new WebSocket(`${WS_URL}/chat`, token ? ['bearer', token] : ['bearer'])

  ws.onmessage = (event) => {
    try {
      const msg = JSON.parse(event.data)
      if (msg.type === 'token') onToken(msg.content)
      else if (msg.type === 'done') onDone(msg.content, msg.message_id)
      else if (msg.type === 'meal_logged') onMealLogged(msg.meal)
      else if (msg.type === 'progress') onProgress?.(msg.step)
      else if (msg.type === 'session_updated') onSessionUpdated?.(msg.session_id)
      else if (msg.type) onNotice?.(msg)
    } catch {
      // ignore unparseable frames
    }
  }

  ws.onerror = () => onError?.('WebSocket error')
  ws.onclose = () => onClose?.()

  return ws
}
