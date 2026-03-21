const BASE_URL = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8000'
const WS_URL = BASE_URL.replace(/^http/, 'ws')

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
  const r = await fetch(url, { ...options, headers })
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
  const r = await fetch(`${BASE_URL}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, pin }),
  })
  if (!r.ok) throw new Error('Login failed')
  return r.json()
}

export const logout = () => {
  localStorage.removeItem('bf_token')
  localStorage.removeItem('bf_user')
}

// ---------------------------------------------------------------------------
// Ingredients
// ---------------------------------------------------------------------------

export const getIngredients = () =>
  apiFetch(`${BASE_URL}/ingredients/`)

export const addIngredient = (name, quantity, unit) =>
  apiFetch(`${BASE_URL}/ingredients/`, json('POST', { name, quantity, unit }))

export const bulkAddIngredients = (ingredients) =>
  apiFetch(`${BASE_URL}/ingredients/bulk`, json('POST', ingredients))

export const updateIngredient = (id, quantity, unit) =>
  apiFetch(`${BASE_URL}/ingredients/${id}`, json('PATCH', { quantity, unit }))

export const deleteIngredient = (id) =>
  apiFetch(`${BASE_URL}/ingredients/${id}`, { method: 'DELETE' })

// ---------------------------------------------------------------------------
// Meals
// ---------------------------------------------------------------------------

export const getMeals = (limit = 50) =>
  apiFetch(`${BASE_URL}/meals/?limit=${limit}`)

export const logMeal = (meal) =>
  apiFetch(`${BASE_URL}/meals/`, json('POST', meal))

export const rateMeal = (id, rating) =>
  apiFetch(`${BASE_URL}/meals/${id}/rating`, json('PATCH', { rating }))

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
// WebSocket chat
// ---------------------------------------------------------------------------

/**
 * Open a WebSocket to /chat with auth token as query param.
 */
export function createChatSocket(onToken, onDone, onMealLogged, onError, onClose) {
  const token = getToken()
  const ws = new WebSocket(`${WS_URL}/chat?token=${token}`)

  ws.onmessage = (event) => {
    try {
      const msg = JSON.parse(event.data)
      if (msg.type === 'token') onToken(msg.content)
      else if (msg.type === 'done') onDone(msg.content)
      else if (msg.type === 'meal_logged') onMealLogged(msg.meal)
    } catch {
      // ignore unparseable frames
    }
  }

  ws.onerror = () => onError?.('WebSocket error')
  ws.onclose = () => onClose?.()

  return ws
}
