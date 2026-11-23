import { useState, useRef, useEffect, useCallback, useImperativeHandle, forwardRef } from 'react'
import { createChatSocket, checkAuth, getActiveSession, createSession, deleteSession, listSessions, getSessionMessages, saveSessionMessage, updateSessionMessage, saveAteDraft, selectSessionMessage, getTodaySupplements, toggleSupplement, analyzeMeal, getSchedule } from '../services/api'
import { useVoice } from '../hooks/useVoice'
import { emitSyncNotice, useSyncNotice } from '../hooks/useSyncNotice'
import ChatBar from './ChatBar'
import DecidePanel from './DecidePanel'
import MealBlock from './MealBlock'
import MarkdownText from './MarkdownText'
import PrepPlanText from './PrepPlanText'
import { normalizeMeal } from '../utils/ingredients'
import { isPrepPlan } from '../utils/prepPlan'
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
  const unmountedRef = useRef(false) // a session check that answers after unmount mustn't reconnect
  const onMealLoggedRef = useRef(onMealLogged)
  const sessionIdRef = useRef(null)
  const abortedRef = useRef(false)
  const analyzeAbortRef = useRef(null)
  const { isListening, startListening, stopListening, supported: voiceSupported } = useVoice()

  // Inject a meal into chat (used by favorites send-to-chat)
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

    let opened = false
    const ws = createChatSocket({
      // Skipped once the reply was stopped; the pipeline step clears when tokens start flowing
      onToken: (chunk) => {
        if (!abortedRef.current) {
          setPipelineStep(null)
          setStreamBuffer((prev) => (prev ?? '') + chunk)
        }
      },
      // messageId is the saved reply's id (lets a card edit save into it)
      onDone: (full, messageId) => {
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
      // A suggested meal: attached to the last assistant message as its card, and selected
      onMealLogged: (meal) => {
        const normalized = normalizeMeal(meal)
        setMessages((prev) => {
          const lastIdx = prev.length - 1
          setMealBlocks((blocks) => ({ ...blocks, [lastIdx]: normalized }))
          setCheckedMealIdx(lastIdx)
          return prev
        })
        onMealLoggedRef.current?.(normalized)
      },
      // No error message in the chat: the header already shows "reconnecting…"
      onError: () => {
        if (wsRef.current !== ws) return // an old socket, already replaced
        setStreamBuffer(null)
        setPipelineStep(null)
        setConnected(false)
      },
      // Auto-reconnect with exponential backoff (max 30s).
      // Skipped for a socket already replaced or closed on unmount (wsRef no longer points to it).
      onClose: () => {
        if (wsRef.current !== ws) return
        setStreamBuffer(null)
        setPipelineStep(null)
        setConnected(false)
        // A stopped reply's done can't arrive on this socket any more
        abortedRef.current = false
        setAborted(false)
        wsRef.current = null
        const reconnect = () => {
          reconnectTimer.current = setTimeout(() => {
            reconnectDelay.current = Math.min(reconnectDelay.current * 2, 30000)
            ensureSocket()
          }, reconnectDelay.current)
        }
        if (opened) { reconnect(); return }
        // Never opened: the server may have refused the session (a restart ends them all), which a
        // socket can't tell. One request can: its 401 ends the session and the app shows the login,
        // so only another answer reconnects (skipped after unmount or once a new socket is open).
        const retry = () => { if (!unmountedRef.current && !wsRef.current) reconnect() }
        checkAuth().then(retry, (err) => { if (err?.status !== 401) retry() })
      },
      // Pipeline step updates
      onProgress: (step) => {
        setPipelineStep(step)
      },
      // A session changed elsewhere: reload it if it's on screen, else only Back / Next may have changed
      onSessionUpdated: (changedId) => {
        if (changedId === sessionIdRef.current) setSyncPending(true)
        else if (sessionIdRef.current) refreshNavState(sessionIdRef.current)
      },
      // Any other change (supplements, shopping suggestions) goes to every panel
      onNotice: emitSyncNotice,
    })
    ws.addEventListener('open', () => {
      opened = true
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
    unmountedRef.current = false
    ensureSocket()
    return () => {
      unmountedRef.current = true
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

  const sendMessage = useCallback((text, type = 'chat', mode = null) => {
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

  // The server reads the chat so far from the session (services/chat_block.py), and leaves these
  // button texts out of it: they are mirrored there as SUGGEST_MESSAGES, so edit both
  const handleSuggest = useCallback((mode) => {
    const modeLabels = {
      favorites: 'Suggest breakfast from my favorite meals',
      explore: 'Suggest a different breakfast from world cuisines',
    }
    sendMessage(modeLabels[mode] || 'Suggest Breakfast', 'suggest', mode || null)
  }, [sendMessage])

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

  // Save a card's "Today I ate" version with its message, so the panel opens from it on every device
  // (null clears it once the meal is logged). A card whose message has no id yet (not saved) keeps
  // it on this device only.
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

  const [decideOpen, setDecideOpen] = useState(false)
  // The card "Today I ate" opened from (its message index), kept while the panel is open
  const [decideIdx, setDecideIdx] = useState(null)
  const decideMeal = decideIdx !== null ? mealBlocks[decideIdx] ?? null : null

  return (
    <div style={s.container}>
      <div style={{ ...s.header, display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: 6 }}>
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
                  {m.role !== 'assistant' ? displayText
                    : isPrepPlan(displayText) ? <PrepPlanText text={displayText} />
                    : <MarkdownText text={displayText} />}
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
          supplements={todaySupps}
          onToggleSupplement={handleToggleSupplement}
          onClose={() => setDecideOpen(false)}
          onConfirm={() => {
            // Logged: the card is unselected and its saved version cleared, on every device
            setDecideOpen(false)
            selectCard(null)
            if (decideIdx !== null && messages[decideIdx]?.ateDraft) {
              handleSaveAteDraft(decideIdx, null).catch(() => {})
            }
          }}
        />
      )}

      <ChatBar
        input={input}
        onInputChange={setInput}
        onKeyDown={handleKeyDown}
        onSend={() => sendMessage(input)}
        onStop={handleStop}
        busy={isBusy}
        onSuggest={handleSuggest}
        suggestDisabled={isBusy || decideOpen}
        onTodayIAte={() => {
          if (!decideOpen) setDecideIdx(checkedMeal ? checkedMealIdx : null)
          setDecideOpen(prev => !prev)
        }}
        voice={{ supported: voiceSupported, listening: isListening, onMic: handleMic }}
      />
    </div>
  )
})
