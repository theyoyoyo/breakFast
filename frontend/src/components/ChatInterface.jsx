import { useState, useRef, useEffect, useCallback, useImperativeHandle, forwardRef } from 'react'
import { createChatSocket, getActiveSession, createSession, deleteSession, listSessions, getSessionMessages, saveSessionMessage, updateSessionMessage, saveAteDraft, selectSessionMessage, getTodaySupplements, toggleSupplement, analyzeMeal, getSchedule } from '../services/api'
import { useVoice } from '../hooks/useVoice'
import { emitSyncNotice, useSyncNotice } from '../hooks/useSyncNotice'
import SuggestButton from './SuggestButton'
import DecidePanel from './DecidePanel'
import MealBlock from './MealBlock'
import MarkdownText from './MarkdownText'
import { normalizeMeal } from '../utils/ingredients'
import * as s from './ChatInterface.styles'

const WELCOME_MSG = { role: 'assistant', content: "Good morning! Tell me what's in your fridge and I'll plan your breakfast." }

// Client-side lyric fallback — mirrors backend's FALLBACK_LYRICS exactly.
// When the server returns a lyric (LLM down), we detect which one it is
// and advance our index so client-side fallback continues the sequence
// if the server becomes unreachable next.
const OFFLINE_LYRICS = [
  "Benim aklım ocakta kaldı~",
  "🎶 Dünkü menüyü kafana takma ne olursun...",
  "🎵 Onlar çaya simide gelir şeyler değil!",
  "💔 Menemen yapmam dedim; yalandı~",
  "🎶 Çay istemiyorum artık; palavra!",
  "🥯 Ellerimde simitler~",
  "☕ Kapında demlik elimde...",
  "👀 Ocakta görürsen şaşırma~",
  "🎵 Beni böyle aç susuz...",
  "🎶 Beni böyle kahvaltısız...",
  "🍳 Beni böyle sofrada yalnız bırakma!",
  "🙈 Son zamanlarda yediklerime bakma ne olursun~",
]
let _lyricIdx = 0
function nextLyric() {
  const line = OFFLINE_LYRICS[_lyricIdx]
  _lyricIdx = (_lyricIdx + 1) % OFFLINE_LYRICS.length
  return line
}
/** Call when we receive a lyric from the server — syncs client index. */
function syncLyric(serverLyric) {
  const idx = OFFLINE_LYRICS.indexOf(serverLyric)
  if (idx !== -1) _lyricIdx = (idx + 1) % OFFLINE_LYRICS.length
}

// Pipeline progress step labels
const PIPELINE_STEPS = {
  drafting: 'Drafting…',
  analyzing: 'Analyzing nutrition…',
  finalizing: 'Final touches…',
}

// Strip ```json ... ``` blocks from message text
const JSON_BLOCK_RE = /```json[\s\S]*?```/g
function stripJsonBlock(text) {
  return text.replace(JSON_BLOCK_RE, '').trim()
}

// During streaming the closing ``` may not have arrived yet — strip from the
// opening fence onwards so the raw JSON is never visible while buffering.
function stripStreamingJsonBlock(text) {
  const idx = text.indexOf('```json')
  return idx === -1 ? text : text.slice(0, idx).trim()
}

// Try to parse a ```json block from text — captures everything between
// the fences so nested objects/arrays are included
function parseJsonBlock(text) {
  const match = text.match(/```json\s*([\s\S]*?)\s*```/)
  if (!match) return null
  try { return JSON.parse(match[1].trim()) } catch { return null }
}

// The message with its ```json block replaced by an edited meal, so the edit is saved with it
const FIRST_JSON_BLOCK_RE = /```json[\s\S]*?```/
function withJsonBlock(text, meal) {
  const block = '```json\n' + JSON.stringify(meal) + '\n```'
  return FIRST_JSON_BLOCK_RE.test(text) ? text.replace(FIRST_JSON_BLOCK_RE, () => block) : `${text}\n\n${block}`
}

// Saved session messages as chat messages after the welcome line; the id lets a card edit save,
// ateDraft is the card's saved "Today I ate" version, and selected marks the card selected for today
function toChatMessages(msgs) {
  return [WELCOME_MSG, ...msgs.map(m => ({
    id: m.id, role: m.role, content: m.content, ateDraft: m.ate_draft ?? null, selected: !!m.selected,
  }))]
}

// Index of the meal card the server has selected for today, or null
function selectedIndex(msgs, blocks) {
  const idx = msgs.findIndex((m, i) => m.selected && blocks[i])
  return idx === -1 ? null : idx
}

const sameDraft = (a, b) => JSON.stringify(a ?? null) === JSON.stringify(b ?? null)

function sameMessages(a, b) {
  return a.length === b.length && a.every((m, i) => (
    m.role === b[i].role && m.content === b[i].content && m.id === b[i].id && sameDraft(m.ateDraft, b[i].ateDraft)
  ))
}

// Unchanged meal cards stay the same objects on a reload, so an open editor keeps its edits
function keepUnchangedBlocks(prev, next) {
  const kept = {}
  for (const [i, meal] of Object.entries(next)) {
    kept[i] = prev[i] && JSON.stringify(prev[i]) === JSON.stringify(meal) ? prev[i] : meal
  }
  return kept
}

// Template meal for demo/preview without LLM
const DEMO_MEAL = {
  menu_name: 'Classic Spread Breakfast',
  meal_name: 'Classic Spread Breakfast',
  description: 'A rich, balanced Turkish breakfast — menemen, fresh cheese, and olives.',
  menu: [
    {
      name: 'Menemen',
      ingredients: [
        { name: 'Egg', amount: 2, unit: 'pcs' },
        { name: 'Tomato', amount: 1, unit: 'pcs' },
        { name: 'Green pepper', amount: 1, unit: 'pcs' },
        { name: 'Olive oil', amount: 1, unit: 'tbsp' },
      ],
    },
    { name: 'White cheese', amount: 50, unit: 'g', ingredients: [] },
    { name: 'Olives', amount: 6, unit: 'pcs', ingredients: [] },
    { name: 'Cucumber', amount: 1, unit: 'pcs', ingredients: [] },
    { name: 'Bread', amount: 3, unit: 'slice', ingredients: [] },
    { name: 'Honey', amount: 1, unit: 'tbsp', ingredients: [] },
  ],
  prep_time_min: 12,
  nutrition_note: 'Rich in protein, calcium, and healthy fats.',
}

// Demo schedule output — shows what the scheduler produces
const DEMO_SCHEDULE = `📋 Classic Spread Breakfast — Prep Plan

🔪 Prep
  • Slice tomato and cucumber — thin rounds
  • Cube the white cheese
  • Drain olives and plate
  • Put honey and butter in small bowls
  • Cut 3 slices of bread

⏱ Timing (7 min)
  0:00  — Drop eggs into boiling water (7 min)  [stove]
         ↳ Drain, cool in cold water, peel
  5:00  — Put bread slices in the toaster (2 min)  [toaster]
         ↳ Remove and plate
  7:00  — Ready! ✓`

export default forwardRef(function ChatInterface({ onMealLogged, visible }, ref) {
  const [messages, setMessages] = useState([WELCOME_MSG])
  const [input, setInput] = useState('')
  // null = idle, '' = thinking (no tokens yet), string = streaming content
  const [streamBuffer, setStreamBuffer] = useState(null)
  const [connected, setConnected] = useState(false)
  const [sessionId, setSessionId] = useState(null)
  const [hasOlder, setHasOlder] = useState(false)
  const [hasNewer, setHasNewer] = useState(false)
  const [todaySupps, setTodaySupps] = useState([])
  const [aborted, setAborted] = useState(false)
  // mealBlocks: { [messageIndex]: mealData } — tracks which messages have meal blocks
  const [mealBlocks, setMealBlocks] = useState({})
  // checkedMealIdx: the message index of the currently checked meal block (only one at a time)
  const [checkedMealIdx, setCheckedMealIdx] = useState(null)
  // analyzingIdx: the message index of a meal block currently being analyzed (null = idle)
  const [analyzingIdx, setAnalyzingIdx] = useState(null)
  // schedulingIdx: the message index of a meal block getting a prep timeline (null = idle)
  const [schedulingIdx, setSchedulingIdx] = useState(null)
  // pipelineStep: current pipeline progress step (null = not in pipeline)
  const [pipelineStep, setPipelineStep] = useState(null)
  // syncPending: the open chat should reload from the server once nothing is in flight
  const [syncPending, setSyncPending] = useState(false)
  const wsRef = useRef(null)
  const hasConnectedRef = useRef(false)
  const busyRef = useRef(false)
  const reloadSeq = useRef(0)
  const messagesEndRef = useRef(null)
  const reconnectTimer = useRef(null)
  const reconnectDelay = useRef(1000)
  const onMealLoggedRef = useRef(onMealLogged)
  const sessionIdRef = useRef(null)
  const abortedRef = useRef(false)
  const analyzeAbortRef = useRef(null)
  const { isListening, startListening, stopListening, supported: voiceSupported } = useVoice()

  // Inject a meal into chat (used by demo and favorites send-to-chat)
  const injectMealToChat = useCallback((meal, introText) => {
    // Normalize: map menu_items → menu so MealBlock renders correctly
    const normalized = normalizeMeal({
      ...meal,
      menu: meal.menu || meal.menu_items || undefined,
    })
    const jsonBlock = '\n\n```json\n' + JSON.stringify(normalized) + '\n```'
    const fullContent = introText + jsonBlock
    const msg = { role: 'assistant', content: fullContent }
    setMessages(prev => {
      const newIdx = prev.length
      const newMsgs = [...prev, msg]
      setMealBlocks(blocks => ({ ...blocks, [newIdx]: normalized }))
      setCheckedMealIdx(newIdx)
      return newMsgs
    })
    if (sessionIdRef.current) {
      // Saved as the selected card, so the user's other devices select it too
      saveSessionMessage(sessionIdRef.current, 'assistant', fullContent, true)
        .then(({ id }) => setMessages(prev => prev.map(m => (m === msg ? { ...m, id } : m))))
        .catch(() => {})
    }
  }, [])

  // Show an assistant message and save it to the session, so reloads and other devices show it too
  const appendSavedMessage = useCallback((content) => {
    setMessages(prev => [...prev, { role: 'assistant', content }])
    if (sessionIdRef.current) {
      saveSessionMessage(sessionIdRef.current, 'assistant', content).catch(() => {})
    }
  }, [])

  // Expose methods to parent via ref
  useImperativeHandle(ref, () => ({
    injectDemoMeal: () => {
      const introText = "Here's a nice classic spread breakfast for you! 🫕\n\nA balanced Turkish breakfast with fresh, wholesome ingredients."
      injectMealToChat(DEMO_MEAL, introText)
    },
    injectDemoSchedule: () => {
      appendSavedMessage(DEMO_SCHEDULE)
    },
    injectFavoriteMeal: (meal) => {
      const introText = `⭐ From favorites: ${meal.meal_name}\n\n${meal.description || 'Enjoy!'}`
      injectMealToChat(meal, introText)
    },
  }))

  // Keep refs in sync so socket callbacks always see the latest props/functions
  useEffect(() => { onMealLoggedRef.current = onMealLogged }, [onMealLogged])
  useEffect(() => { sessionIdRef.current = sessionId }, [sessionId])

  const refreshNavState = useCallback(async (currentId) => {
    try {
      const sessions = await listSessions()
      const idx = sessions.findIndex(s => s.id === currentId)
      setHasOlder(idx < sessions.length - 1)
      setHasNewer(idx > 0)
    } catch {
      setHasOlder(false)
      setHasNewer(false)
    }
  }, [])

  const loadTodaySupplements = useCallback(async () => {
    try {
      const supps = await getTodaySupplements()
      setTodaySupps(supps)
    } catch { /* Backend not available */ }
  }, [])

  const handleToggleSupplement = useCallback(async (id, currentTaken) => {
    const newTaken = !currentTaken
    setTodaySupps(prev => prev.map(s => s.id === id ? { ...s, taken_today: newTaken ? 1 : 0 } : s))
    try {
      await toggleSupplement(id, newTaken)
    } catch {
      loadTodaySupplements()
    }
  }, [loadTodaySupplements])

  // Parse meal blocks from loaded session messages
  const parseMealBlocksFromMessages = useCallback((msgs) => {
    const blocks = {}
    msgs.forEach((m, i) => {
      if (m.role === 'assistant') {
        const meal = parseJsonBlock(m.content)
        if (meal) blocks[i] = normalizeMeal(meal)
      }
    })
    return blocks
  }, [])

  // Load active session on mount
  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        const session = await getActiveSession()
        if (cancelled) return
        setSessionId(session.id)
        const msgs = await getSessionMessages(session.id)
        if (cancelled) return
        const allMsgs = toChatMessages(msgs)
        const blocks = parseMealBlocksFromMessages(allMsgs)
        setMessages(allMsgs)
        setMealBlocks(blocks)
        setCheckedMealIdx(selectedIndex(allMsgs, blocks))
        await refreshNavState(session.id)
      } catch {
        // Backend not available yet — will work once connected
      }
      loadTodaySupplements()
    })()
    return () => { cancelled = true }
  }, [refreshNavState, loadTodaySupplements, parseMealBlocksFromMessages])

  // Reload the open chat from the server: another device changed it, or this one was away.
  // Keeps the draft, the selected card and every unchanged card.
  const reloadSession = useCallback(async () => {
    const id = sessionIdRef.current
    if (!id) return
    const seq = ++reloadSeq.current
    let msgs
    try {
      msgs = await getSessionMessages(id)
    } catch {
      return // Backend not available
    }
    // Only the latest reload applies, and only to the chat it loaded
    if (seq !== reloadSeq.current || id !== sessionIdRef.current) return
    // A reply or an analysis started while loading: reload again once it's done
    if (busyRef.current) {
      setSyncPending(true)
      return
    }
    const allMsgs = toChatMessages(msgs)
    const blocks = parseMealBlocksFromMessages(allMsgs)
    setMessages(prev => (sameMessages(prev, allMsgs) ? prev : allMsgs))
    setMealBlocks(prev => keepUnchangedBlocks(prev, blocks))
    setCheckedMealIdx(selectedIndex(allMsgs, blocks))
    refreshNavState(id)
  }, [parseMealBlocksFromMessages, refreshNavState])

  // Refresh supplements when Chat tab becomes visible (picks up Settings changes)
  useEffect(() => {
    if (visible) loadTodaySupplements()
  }, [visible]) // eslint-disable-line react-hooks/exhaustive-deps

  // Another device marked a pill or changed a supplement, or the socket (re)opened: reload the 💊 list
  useSyncNotice(['supplements_updated', 'sync_connected'], loadTodaySupplements)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, streamBuffer, analyzingIdx, pipelineStep])

  const ensureSocket = useCallback(() => {
    const state = wsRef.current?.readyState
    if (state === WebSocket.OPEN || state === WebSocket.CONNECTING) return wsRef.current

    const ws = createChatSocket(
      // onToken — skip if aborted; clear pipeline step when tokens start flowing
      (chunk) => {
        if (!abortedRef.current) {
          setPipelineStep(null)
          setStreamBuffer((prev) => (prev ?? '') + chunk)
        }
      },
      // onDone — messageId is the saved reply's id (lets a card edit save into it)
      (full, messageId) => {
        setPipelineStep(null)
        syncLyric(full) // keep client lyric index in sync if this was a fallback lyric
        if (abortedRef.current) {
          // Already handled by handleStop
          abortedRef.current = false
          setAborted(false)
        } else {
          setMessages((prev) => [...prev, { id: messageId, role: 'assistant', content: full }])
        }
        setStreamBuffer(null)
      },
      // onMealLogged — attach meal block to the last assistant message
      (meal) => {
        const normalized = normalizeMeal(meal)
        setMessages((prev) => {
          const lastIdx = prev.length - 1
          setMealBlocks((blocks) => ({ ...blocks, [lastIdx]: normalized }))
          setCheckedMealIdx(lastIdx)
          return prev
        })
        onMealLoggedRef.current?.(normalized)
      },
      // onError — don't spam chat with error messages, header already shows "reconnecting…"
      () => {
        if (wsRef.current !== ws) return // an old socket, already replaced
        setStreamBuffer(null)
        setPipelineStep(null)
        setConnected(false)
      },
      // onClose — auto-reconnect with exponential backoff (max 30s).
      // Skipped for a socket already replaced or closed on unmount (wsRef no longer points to it).
      () => {
        if (wsRef.current !== ws) return
        setStreamBuffer(null)
        setPipelineStep(null)
        setConnected(false)
        // A stopped reply's done can't arrive on this socket any more
        abortedRef.current = false
        setAborted(false)
        wsRef.current = null
        reconnectTimer.current = setTimeout(() => {
          reconnectDelay.current = Math.min(reconnectDelay.current * 2, 30000)
          ensureSocket()
        }, reconnectDelay.current)
      },
      // onProgress — pipeline step updates
      (step) => {
        setPipelineStep(step)
      },
      // onMealUpdated — chat modified the current meal; update the selected block in place
      (meal) => {
        const normalized = normalizeMeal(meal)
        setCheckedMealIdx((idx) => {
          if (idx !== null) {
            setMealBlocks((blocks) => ({ ...blocks, [idx]: normalized }))
          }
          return idx
        })
      },
      // onSessionUpdated — a session changed elsewhere: reload it if it's on screen,
      // else only Back / Next may have changed
      (changedId) => {
        if (changedId === sessionIdRef.current) setSyncPending(true)
        else if (sessionIdRef.current) refreshNavState(sessionIdRef.current)
      },
      // onNotice — any other change (supplements, shopping suggestions) goes to every panel
      emitSyncNotice
    )
    ws.addEventListener('open', () => {
      hasConnectedRef.current = true
      setConnected(true)
      reconnectDelay.current = 1000 // reset backoff on successful connect
      setSyncPending(true) // catch up on anything missed while disconnected
      emitSyncNotice({ type: 'sync_connected' }) // and so do the other panels
    })
    wsRef.current = ws
    return ws
  }, [refreshNavState])

  // Open the socket on mount so other devices' changes arrive; close it on unmount
  useEffect(() => {
    ensureSocket()
    return () => {
      clearTimeout(reconnectTimer.current)
      const ws = wsRef.current
      wsRef.current = null // tells onClose not to reconnect
      ws?.close()
    }
  }, [ensureSocket])

  // Back from the background (phone app resumed, tab shown again): reload the chat and the 💊 list
  // now, or reconnect at once if the socket closed meanwhile (the chat reload follows on open)
  useEffect(() => {
    const handleVisible = () => {
      if (document.visibilityState !== 'visible') return
      loadTodaySupplements()
      const state = wsRef.current?.readyState
      if (state === WebSocket.OPEN) {
        setSyncPending(true)
      } else if (state !== WebSocket.CONNECTING) {
        clearTimeout(reconnectTimer.current)
        reconnectDelay.current = 1000
        ensureSocket()
      }
    }
    document.addEventListener('visibilitychange', handleVisible)
    return () => document.removeEventListener('visibilitychange', handleVisible)
  }, [ensureSocket, loadTodaySupplements])

  const sendMessage = useCallback((text, type = 'chat', mode = null, chatContext = null) => {
    const msg = text.trim()
    if (!msg || streamBuffer !== null || analyzingIdx !== null) return

    setMessages((prev) => [...prev, { role: 'user', content: msg }])
    setInput('')
    abortedRef.current = false
    setAborted(false)

    const payload = { message: msg }
    if (type !== 'chat') payload.type = type
    if (mode) payload.mode = mode
    if (sessionIdRef.current) payload.session_id = sessionIdRef.current
    if (chatContext && chatContext.length > 0) payload.chat_context = chatContext

    const ws = ensureSocket()
    if (ws.readyState === WebSocket.OPEN) {
      setStreamBuffer('')  // '' = thinking
      ws.send(JSON.stringify(payload))
    } else {
      // Backend not connected yet — wait for connection, then send
      setStreamBuffer('')
      ws.addEventListener('open', () => ws.send(JSON.stringify(payload)), { once: true })
    }
  }, [streamBuffer, analyzingIdx, ensureSocket])

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage(input)
    }
  }

  const handleNewSession = useCallback(async () => {
    try {
      const { session_id } = await createSession()
      setSessionId(session_id)
      setMessages([WELCOME_MSG])
      setMealBlocks({})
      setCheckedMealIdx(null)
      setStreamBuffer(null)
      setInput('')
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ session_id }))
      }
      await refreshNavState(session_id)
    } catch {
      // Backend not available
    }
  }, [refreshNavState])

  const switchToSession = useCallback(async (targetId) => {
    setSessionId(targetId)
    const msgs = await getSessionMessages(targetId)
    const allMsgs = toChatMessages(msgs)
    const blocks = parseMealBlocksFromMessages(allMsgs)
    setMessages(allMsgs)
    setMealBlocks(blocks)
    setCheckedMealIdx(selectedIndex(allMsgs, blocks))
    setStreamBuffer(null)
    setInput('')
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ session_id: targetId }))
    }
    await refreshNavState(targetId)
  }, [refreshNavState, parseMealBlocksFromMessages])

  const handleBack = useCallback(async () => {
    if (!sessionIdRef.current) return
    try {
      const sessions = await listSessions()
      const idx = sessions.findIndex(s => s.id === sessionIdRef.current)
      if (idx < sessions.length - 1) {
        await switchToSession(sessions[idx + 1].id)
      }
    } catch { /* Backend not available */ }
  }, [switchToSession])

  const handleNext = useCallback(async () => {
    if (!sessionIdRef.current) return
    try {
      const sessions = await listSessions()
      const idx = sessions.findIndex(s => s.id === sessionIdRef.current)
      if (idx > 0) {
        await switchToSession(sessions[idx - 1].id)
      }
    } catch { /* Backend not available */ }
  }, [switchToSession])

  const handleDeleteSession = useCallback(async () => {
    if (!sessionIdRef.current) return
    try {
      const currentId = sessionIdRef.current
      const sessions = await listSessions()
      const idx = sessions.findIndex(s => s.id === currentId)
      await deleteSession(currentId)

      // Navigate to adjacent session or create new
      if (sessions.length > 1) {
        const nextIdx = idx > 0 ? idx - 1 : idx + 1
        await switchToSession(sessions[nextIdx].id)
      } else {
        const { session_id } = await createSession()
        setSessionId(session_id)
        setMessages([WELCOME_MSG])
        setMealBlocks({})
        setCheckedMealIdx(null)
        setStreamBuffer(null)
        setInput('')
        if (wsRef.current?.readyState === WebSocket.OPEN) {
          wsRef.current.send(JSON.stringify({ session_id }))
        }
      }
    } catch { /* Backend not available */ }
  }, [switchToSession, refreshNavState])

  const handleMic = () => {
    if (isListening) {
      stopListening()
    } else {
      startListening((transcript) => {
        setInput(transcript)
        sendMessage(transcript)
      })
    }
  }

  const handleStop = useCallback(() => {
    // Stop streaming chat/suggestion
    if (streamBuffer !== null) {
      abortedRef.current = true
      setAborted(true)
      setPipelineStep(null)
      setStreamBuffer((prev) => {
        const partial = prev || ''
        const stopped = partial ? partial + '\n\n[stopped]' : '[stopped]'
        setMessages((msgs) => [...msgs, { role: 'assistant', content: stopped }])
        return null
      })
    }
    // Cancel ongoing analysis
    if (analyzeAbortRef.current) {
      analyzeAbortRef.current.abort()
      analyzeAbortRef.current = null
      setAnalyzingIdx(null)
      setMessages(prev => [...prev, { role: 'assistant', content: '📊 [Analysis stopped]' }])
    }
  }, [streamBuffer])

  const handleSuggest = useCallback((mode) => {
    const modeLabels = {
      favorites: 'Suggest breakfast from my favorite meals',
      explore: 'Suggest a different breakfast from world cuisines',
    }
    const msg = modeLabels[mode] || 'Suggest Breakfast'

    // Collect last 5 user messages (chronological) as breakfast feedback context
    const recentUserMsgs = messages
      .filter(m => m.role === 'user')
      .slice(-5)
      .map(m => m.content)

    sendMessage(msg, 'suggest', mode || null, recentUserMsgs.length > 0 ? recentUserMsgs : null)
  }, [sendMessage, messages])

  const handleAnalyze = useCallback(async (msgIdx) => {
    const meal = mealBlocks[msgIdx]
    if (!meal || streamBuffer !== null || analyzingIdx !== null) return
    setAnalyzingIdx(msgIdx)
    const abortCtrl = { cancelled: false }
    analyzeAbortRef.current = { abort: () => { abortCtrl.cancelled = true } }
    try {
      const mealName = meal.meal_name || meal.menu_name || 'Meal'
      const result = await analyzeMeal(mealName, meal.ingredients || [], meal.id || null)
      if (abortCtrl.cancelled) return
      // Strip JSON block from analysis text for display, show as assistant message
      const displayText = result.analysis_text
        ? result.analysis_text.replace(/```json[\s\S]*?```/g, '').trim()
        : "Couldn't get the analysis."
      syncLyric(displayText) // keep client lyric index in sync if this was a fallback lyric
      appendSavedMessage(`📊 ${mealName} — Nutrition Analysis\n\n${displayText}`)
    } catch {
      if (abortCtrl.cancelled) return
      appendSavedMessage(`📊 ${meal.meal_name || meal.menu_name || 'Meal'} — Nutrition Analysis\n\n${nextLyric()}`)
    } finally {
      analyzeAbortRef.current = null
      if (!abortCtrl.cancelled) setAnalyzingIdx(null)
    }
  }, [mealBlocks, analyzingIdx, streamBuffer, appendSavedMessage])

  const handleSchedule = useCallback(async (msgIdx) => {
    const meal = mealBlocks[msgIdx]
    if (!meal || streamBuffer !== null || schedulingIdx !== null) return
    setSchedulingIdx(msgIdx)
    const mealName = meal.meal_name || meal.menu_name || 'Meal'
    try {
      const result = await getSchedule(
        mealName,
        meal.steps || [],
        meal.ingredients || [],
        meal.id || null,
        meal.menu || [],
      )
      const text = result.formatted || "Couldn't build a prep plan."
      syncLyric(text) // keep client lyric index in sync if this was a fallback lyric
      const idTag = meal.id ? ` (#${meal.id})` : ''
      appendSavedMessage(`📋 ${mealName}${idTag} — Prep Plan\n\n${text}`)
    } catch {
      const idTag = meal.id ? ` (#${meal.id})` : ''
      appendSavedMessage(`📋 ${mealName}${idTag} — Prep Plan\n\n${nextLyric()}`)
    } finally {
      setSchedulingIdx(null)
    }
  }, [mealBlocks, schedulingIdx, streamBuffer, appendSavedMessage])

  // Select a meal card for today, or none (null), on every device. A card whose message has
  // no id yet (not saved) is selected on this device only.
  const selectCard = (idx) => {
    setCheckedMealIdx(idx)
    const msg = idx !== null ? messages[idx] : null
    if (sessionIdRef.current && (idx === null || msg?.id)) {
      selectSessionMessage(sessionIdRef.current, msg?.id ?? null).catch(() => {})
    }
  }

  // Save a card's "Today I ate" version with its message, so the panel opens from it on every device.
  // A card whose message has no id yet (not saved) keeps it on this device only.
  const handleSaveAteDraft = async (idx, meal) => {
    const msg = messages[idx]
    setMessages(prev => prev.map((m, i) => (i === idx ? { ...m, ateDraft: meal } : m)))
    if (msg?.id && sessionIdRef.current) await saveAteDraft(sessionIdRef.current, msg.id, meal)
  }

  // Save a meal card edit into its message, so reloads and other devices show the edited card.
  // A card whose message has no id yet (not saved) stays edited on this device only.
  const handleMealSave = useCallback((idx, msg, updated) => {
    setMealBlocks(prev => ({ ...prev, [idx]: updated }))
    const content = withJsonBlock(msg.content, updated)
    setMessages(prev => prev.map(m => (m === msg ? { ...m, content } : m)))
    if (msg.id && sessionIdRef.current) {
      updateSessionMessage(sessionIdRef.current, msg.id, content).catch(() => {})
    }
  }, [])

  // True when anything is busy (streaming, analyzing, or scheduling)
  const isBusy = streamBuffer !== null || analyzingIdx !== null || schedulingIdx !== null
  // A stopped reply still runs on the server until its done arrives, so a reload waits for that too
  const syncBusy = isBusy || aborted
  busyRef.current = syncBusy

  // Reload once nothing is in flight, so a streaming reply or an analysis on its way isn't lost
  useEffect(() => {
    if (syncPending && !syncBusy) {
      setSyncPending(false)
      reloadSession()
    }
  }, [syncPending, syncBusy, reloadSession])

  // Get the checked meal for DecidePanel (priority: checked block > null)
  const checkedMeal = checkedMealIdx !== null ? mealBlocks[checkedMealIdx] : null

  const [suppMenuOpen, setSuppMenuOpen] = useState(false)
  const [decideOpen, setDecideOpen] = useState(false)
  // The card "Today I ate" opened from (its message index), kept while the panel is open
  const [decideIdx, setDecideIdx] = useState(null)
  const decideMeal = decideIdx !== null ? mealBlocks[decideIdx] ?? null : null

  return (
    <div style={s.container}>
      <div style={{ ...s.header, display: 'flex', alignItems: 'center' }}>
        <span>break FAST</span>
        {!connected && hasConnectedRef.current && (
          <span style={s.connStatus}> — reconnecting…</span>
        )}
        <button style={{ ...s.newSessionBtn, visibility: hasOlder ? 'visible' : 'hidden' }} onClick={handleBack} title="Previous session">
          ◀ Back
        </button>
        <button style={{ ...s.newSessionBtn, visibility: hasNewer ? 'visible' : 'hidden' }} onClick={handleNext} title="Next session">
          Next ▶
        </button>
        <button style={s.newSessionBtn} onClick={handleNewSession} title="Start a new conversation">
          ✚ New
        </button>
        <button style={s.deleteSessionBtn} onClick={handleDeleteSession} title="Delete this session">
          🗑 Del
        </button>
      </div>

      <div style={s.messages}>
        {messages.map((m, i) => {
          const hasMealBlock = mealBlocks[i] !== undefined
          // Always strip JSON blocks from assistant messages — prevents a flash of raw
          // JSON between onDone (message added) and onMealLogged (hasMealBlock set).
          const displayText = m.role === 'assistant' ? stripJsonBlock(m.content) : m.content

          return (
            <div key={i} style={s.messageWrapper(m.role)}>
              {displayText && (
                <div style={s.bubble(m.role)}>
                  {m.role === 'assistant' ? <MarkdownText text={displayText} /> : displayText}
                </div>
              )}
              {hasMealBlock && (
                <MealBlock
                  meal={mealBlocks[i]}
                  checked={checkedMealIdx === i}
                  onCheck={() => selectCard(checkedMealIdx === i ? null : i)}
                  onSave={(updated) => handleMealSave(i, m, updated)}
                  onAnalyze={() => handleAnalyze(i)}
                  analyzing={analyzingIdx === i}
                  onSchedule={() => handleSchedule(i)}
                  scheduling={schedulingIdx === i}
                  fridgeCheckKey={visible}
                />
              )}
            </div>
          )
        })}

        {streamBuffer !== null && streamBuffer !== '' && (
          <div style={s.bubble('assistant')}><MarkdownText text={stripStreamingJsonBlock(streamBuffer)} /></div>
        )}
        {streamBuffer === '' && (
          <div style={s.thinking}>{PIPELINE_STEPS[pipelineStep] || 'Thinking…'}</div>
        )}
        {analyzingIdx !== null && (
          <div style={s.thinking}>Analyzing…</div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {decideOpen && (
        <DecidePanel
          meal={decideMeal}
          saved={decideIdx !== null ? messages[decideIdx]?.ateDraft ?? null : null}
          onSave={decideMeal ? (meal) => handleSaveAteDraft(decideIdx, meal) : undefined}
          onClose={() => setDecideOpen(false)}
          onConfirm={() => {
            setDecideOpen(false)
            selectCard(null)
          }}
        />
      )}

      <div style={s.actionRow}>
        <div style={s.actionStack}>
          <div style={s.suppMenuWrapper}>
            {suppMenuOpen && !decideOpen && (
              <div style={s.suppMenu}>
                <span style={s.suppMenuLabel}>Supplements</span>
                {todaySupps.length === 0 ? (
                  <span style={{ fontSize: 12, color: 'var(--text-muted)', textAlign: 'center', padding: '4px 0' }}>
                    None added — Settings → Supplements
                  </span>
                ) : todaySupps.map(sup => {
                  const isDaily = sup.frequency === 'daily'
                  const taken = isDaily || !!sup.taken_today
                  return (
                    <button
                      key={sup.id}
                      style={s.suppPill(taken, isDaily)}
                      onClick={() => !isDaily && handleToggleSupplement(sup.id, !!sup.taken_today)}
                      title={sup.contents || sup.name}
                      disabled={isDaily}
                    >
                      {isDaily ? '⚡' : taken ? '✓' : '○'} {sup.name}
                    </button>
                  )
                })}
              </div>
            )}
            <button
              style={s.suppToggleBtn(suppMenuOpen && !decideOpen)}
              onClick={() => !decideOpen && setSuppMenuOpen(prev => !prev)}
              disabled={decideOpen}
              title="Supplements"
            >
              💊
            </button>
          </div>

          <button
            style={s.decideBtn(decideOpen)}
            onClick={() => {
              if (!decideOpen) {
                setDecideIdx(checkedMeal ? checkedMealIdx : null)
                setSuppMenuOpen(false)
              }
              setDecideOpen(prev => !prev)
            }}
            disabled={isBusy}
            title="Today I ate..."
          >
            ✅
          </button>
        </div>

        <SuggestButton onSuggest={handleSuggest} disabled={isBusy || decideOpen} />
      </div>

      <div style={s.inputRow}>
        {voiceSupported && (
          <button style={s.micBtn(isListening)} onClick={handleMic} title="Voice input">
            {isListening ? '🔴' : '🎤'}
          </button>
        )}
        <textarea
          style={s.input}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="What are you craving?"
          rows={1}
          disabled={isBusy}
        />
        {isBusy ? (
          <button style={s.stopBtn} onClick={handleStop}>
            Stop
          </button>
        ) : (
          <button
            style={s.sendBtn}
            onClick={() => sendMessage(input)}
          >
            Send
          </button>
        )}
      </div>
    </div>
  )
})
