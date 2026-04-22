const BASE_URL = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8000'
const WS_URL = BASE_URL.replace(/^http/, 'ws')

// ---------------------------------------------------------------------------
// Error types
// ---------------------------------------------------------------------------

export class NetworkError extends Error {
  constructor() { super('Cannot reach server') }
}

// ---------------------------------------------------------------------------
// Auth helpers
// ---------------------------------------------------------------------------

function getToken() {
  return localStorage.getItem('bf_token') || ''
}

function authHeaders() {
  return { Authorization: `Bearer ${getToken()}` }
}

// ---------------------------------------------------------------------------
// Shared fetch helper — avoids repeating ok-check + json() everywhere
// ---------------------------------------------------------------------------

/** Fetch a URL, throw on non-2xx, and return parsed JSON (or undefined for 204). */
async function apiFetch(url, options = {}) {
  const headers = {
    ...authHeaders(),
    ...(options.body ? { 'Content-Type': 'application/json' } : {}),
  }
  let r
  try {
    r = await fetch(url, { ...options, headers })
  } catch {
    throw new NetworkError()
  }
  if (!r.ok) throw new Error(`API error ${r.status}: ${url}`)
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
  if (!r.ok) throw new Error('Login failed')
  return r.json()
}

export const logout = () => {
  localStorage.removeItem('bf_token')
  localStorage.removeItem('bf_user')
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

export const getExpiredIngredients = () =>
  apiFetch(`${BASE_URL}/ingredients/expired`)

export const getExpiredCount = () =>
  apiFetch(`${BASE_URL}/ingredients/expired-count`)

export const confirmExpiredThrown = (ids) =>
  apiFetch(`${BASE_URL}/ingredients/expired/thrown`, json('POST', { ids }))

export const handleExpiredAction = (delete_ids, keep_ids, shopping_ids) =>
  apiFetch(`${BASE_URL}/ingredients/expired/action`, json('POST', { delete_ids, keep_ids, shopping_ids }))

export const getShoppingSuggestions = (exclude = []) =>
  apiFetch(`${BASE_URL}/ingredients/shopping-suggestions`, json('POST', { exclude }))

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

export const rateMeal = (id, rating) =>
  apiFetch(`${BASE_URL}/meals/${id}/rating`, json('PATCH', { rating }))

export const updateMeal = (id, meal) =>
  apiFetch(`${BASE_URL}/meals/${id}`, json('PUT', meal))

export const deleteMeal = (id) =>
  apiFetch(`${BASE_URL}/meals/${id}`, { method: 'DELETE' })

export const deleteOldMeals = () =>
  apiFetch(`${BASE_URL}/meals/old`, { method: 'DELETE' })

export const getWeeklyMeals = () =>
  apiFetch(`${BASE_URL}/meals/weekly`)

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

export const saveSessionMessage = (sessionId, role, content) =>
  apiFetch(`${BASE_URL}/sessions/${sessionId}/messages`, json('POST', { role, content }))

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

export const getSchedule = (meal_name, steps, ingredients, meal_id = null) =>
  apiFetch(`${BASE_URL}/scheduler/plan`, json('POST', { meal_name, steps, ingredients, meal_id }))

// ---------------------------------------------------------------------------
// WebSocket chat
// ---------------------------------------------------------------------------

/**
 * Open a WebSocket to /chat with auth token as query param.
 */
export function createChatSocket(onToken, onDone, onMealLogged, onError, onClose, onProgress, onMealUpdated) {
  const token = getToken()
  const ws = new WebSocket(`${WS_URL}/chat?token=${token}`)

  ws.onmessage = (event) => {
    try {
      const msg = JSON.parse(event.data)
      if (msg.type === 'token') onToken(msg.content)
      else if (msg.type === 'done') onDone(msg.content)
      else if (msg.type === 'meal_logged') onMealLogged(msg.meal)
      else if (msg.type === 'meal_updated') onMealUpdated?.(msg.meal)
      else if (msg.type === 'progress') onProgress?.(msg.step)
    } catch {
      // ignore unparseable frames
    }
  }

  ws.onerror = () => onError?.('WebSocket error')
  ws.onclose = () => onClose?.()

  return ws
}
