import { useState, useRef, useEffect, useCallback, useImperativeHandle, forwardRef } from 'react'
import { createChatSocket, getActiveSession, createSession, deleteSession, listSessions, getSessionMessages, saveSessionMessage, getTodaySupplements, toggleSupplement, analyzeMeal, getSchedule } from '../services/api'
import { useVoice } from '../hooks/useVoice'
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
    { name: 'Bread', amount: 3, unit: 'slices', ingredients: [] },
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
  const wsRef = useRef(null)
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
    setMessages(prev => {
      const newIdx = prev.length
      const newMsgs = [...prev, { role: 'assistant', content: fullContent }]
      setMealBlocks(blocks => ({ ...blocks, [newIdx]: normalized }))
      setCheckedMealIdx(newIdx)
      return newMsgs
    })
    if (sessionIdRef.current) {
      saveSessionMessage(sessionIdRef.current, 'assistant', fullContent).catch(() => {})
    }
  }, [])

  // Expose methods to parent via ref
  useImperativeHandle(ref, () => ({
    injectDemoMeal: () => {
      const introText = "Here's a nice classic spread breakfast for you! 🫕\n\nA balanced Turkish breakfast with fresh, wholesome ingredients."
      injectMealToChat(DEMO_MEAL, introText)
    },
    injectDemoSchedule: () => {
      setMessages(prev => [...prev, { role: 'assistant', content: DEMO_SCHEDULE }])
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
        const loaded = msgs.map(m => ({ role: m.role, content: m.content }))
        const allMsgs = [WELCOME_MSG, ...loaded]
        setMessages(allMsgs)
        setMealBlocks(parseMealBlocksFromMessages(allMsgs))
        setCheckedMealIdx(null)
        await refreshNavState(session.id)
      } catch {
        // Backend not available yet — will work once connected
      }
      loadTodaySupplements()
    })()
    return () => { cancelled = true }
  }, [refreshNavState, loadTodaySupplements, parseMealBlocksFromMessages])

  // Refresh supplements when Chat tab becomes visible (picks up Settings changes)
  useEffect(() => {
    if (visible) loadTodaySupplements()
  }, [visible]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, streamBuffer, analyzingIdx, pipelineStep])

  // Close socket and clear reconnect timer on unmount
  useEffect(() => () => {
    clearTimeout(reconnectTimer.current)
    wsRef.current?.close()
  }, [])

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
      // onDone
      (full) => {
        setPipelineStep(null)
        syncLyric(full) // keep client lyric index in sync if this was a fallback lyric
        if (abortedRef.current) {
          // Already handled by handleStop
          abortedRef.current = false
          setAborted(false)
        } else {
          setMessages((prev) => [...prev, { role: 'assistant', content: full }])
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
        setStreamBuffer(null)
        setPipelineStep(null)
        setConnected(false)
      },
      // onClose — auto-reconnect with exponential backoff (max 30s)
      () => {
        setStreamBuffer(null)
        setPipelineStep(null)
        setConnected(false)
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
      }
    )
    ws.addEventListener('open', () => {
      setConnected(true)
      reconnectDelay.current = 1000 // reset backoff on successful connect
    })
    wsRef.current = ws
    return ws
  }, [])

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
    const loaded = msgs.map(m => ({ role: m.role, content: m.content }))
    const allMsgs = [WELCOME_MSG, ...loaded]
    setMessages(allMsgs)
    setMealBlocks(parseMealBlocksFromMessages(allMsgs))
    setCheckedMealIdx(null)
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
      const analysisMsg = `📊 ${mealName} — Nutrition Analysis\n\n${displayText}`
      setMessages(prev => [...prev, { role: 'assistant', content: analysisMsg }])
    } catch {
      if (abortCtrl.cancelled) return
      setMessages(prev => [...prev, { role: 'assistant', content: `📊 ${meal.meal_name || meal.menu_name || 'Meal'} — Nutrition Analysis\n\n${nextLyric()}` }])
    } finally {
      analyzeAbortRef.current = null
      if (!abortCtrl.cancelled) setAnalyzingIdx(null)
    }
  }, [mealBlocks, analyzingIdx, streamBuffer])

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
      const scheduleMsg = `📋 ${mealName}${idTag} — Prep Plan\n\n${text}`
      setMessages(prev => [...prev, { role: 'assistant', content: scheduleMsg }])
    } catch {
      const idTag = meal.id ? ` (#${meal.id})` : ''
      setMessages(prev => [...prev, { role: 'assistant', content: `📋 ${mealName}${idTag} — Prep Plan\n\n${nextLyric()}` }])
    } finally {
      setSchedulingIdx(null)
    }
  }, [mealBlocks, schedulingIdx, streamBuffer])

  // True when anything is busy (streaming, analyzing, or scheduling)
  const isBusy = streamBuffer !== null || analyzingIdx !== null || schedulingIdx !== null

  // Get the checked meal for DecidePanel (priority: checked block > null)
  const checkedMeal = checkedMealIdx !== null ? mealBlocks[checkedMealIdx] : null

  const [suppMenuOpen, setSuppMenuOpen] = useState(false)
  const [decideOpen, setDecideOpen] = useState(false)
  // "Today I ate" draft: kept across close/reopen while the same chat meal stays selected.
  // Selecting another meal (or saving the selected one) gives a different source, so the draft is dropped.
  const decideDraftRef = useRef({ source: null, meal: null })
  const decideDraft = decideDraftRef.current.source === checkedMeal ? decideDraftRef.current.meal : null

  return (
    <div style={s.container}>
      <div style={{ ...s.header, display: 'flex', alignItems: 'center' }}>
        <span>break FAST</span>
        {!connected && wsRef.current && (
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
        <button style={{ ...s.newSessionBtn, color: 'var(--accent)' }} onClick={handleDeleteSession} title="Delete this session">
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
                  onCheck={() => setCheckedMealIdx(i)}
                  onSave={(updated) => setMealBlocks(prev => ({ ...prev, [i]: updated }))}
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
          meal={checkedMeal}
          draft={decideDraft}
          onDraftChange={(draftMeal) => { decideDraftRef.current = { source: checkedMeal, meal: draftMeal } }}
          onClose={() => setDecideOpen(false)}
          onConfirm={() => {
            decideDraftRef.current = { source: null, meal: null }
            setDecideOpen(false)
            setCheckedMealIdx(null)
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
              setDecideOpen(prev => !prev)
              if (!decideOpen) setSuppMenuOpen(false)
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
