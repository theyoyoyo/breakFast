import { useState, useRef, useEffect, useCallback } from 'react'
import { createChatSocket, getActiveSession, createSession, deleteSession, listSessions, getSessionMessages, getTodaySupplements, toggleSupplement } from '../services/api'
import { useVoice } from '../hooks/useVoice'
import SuggestButton from './SuggestButton'
import DecidePanel from './DecidePanel'
import MealBlock from './MealBlock'
import * as s from './ChatInterface.styles'

const WELCOME_MSG = { role: 'assistant', content: "Good morning! Tell me what's in your fridge and I'll plan your breakfast." }

// Strip ```json { ... } ``` blocks from message text
const JSON_BLOCK_RE = /```json\s*\{.*?\}\s*```/gs
function stripJsonBlock(text) {
  return text.replace(JSON_BLOCK_RE, '').trim()
}

// Try to parse a ```json block from text
function parseJsonBlock(text) {
  const match = text.match(/```json\s*(\{.*?\})\s*```/s)
  if (!match) return null
  try { return JSON.parse(match[1]) } catch { return null }
}

export default function ChatInterface({ onMealLogged }) {
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
  const wsRef = useRef(null)
  const messagesEndRef = useRef(null)
  const reconnectTimer = useRef(null)
  const reconnectDelay = useRef(1000)
  const onMealLoggedRef = useRef(onMealLogged)
  const sessionIdRef = useRef(null)
  const abortedRef = useRef(false)
  const { isListening, startListening, stopListening, speak, supported: voiceSupported } = useVoice()
  const speakRef = useRef(speak)

  // Keep refs in sync so socket callbacks always see the latest props/functions
  useEffect(() => { onMealLoggedRef.current = onMealLogged }, [onMealLogged])
  useEffect(() => { speakRef.current = speak }, [speak])
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
      setTodaySupps(supps.filter(s => s.frequency === 'sometimes'))
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
        if (meal) blocks[i] = meal
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

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, streamBuffer])

  // Close socket and clear reconnect timer on unmount
  useEffect(() => () => {
    clearTimeout(reconnectTimer.current)
    wsRef.current?.close()
  }, [])

  const ensureSocket = useCallback(() => {
    const state = wsRef.current?.readyState
    if (state === WebSocket.OPEN || state === WebSocket.CONNECTING) return wsRef.current

    const ws = createChatSocket(
      // onToken — skip if aborted
      (chunk) => {
        if (!abortedRef.current) {
          setStreamBuffer((prev) => (prev ?? '') + chunk)
        }
      },
      // onDone
      (full) => {
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
        setMessages((prev) => {
          const lastIdx = prev.length - 1
          setMealBlocks((blocks) => ({ ...blocks, [lastIdx]: meal }))
          setCheckedMealIdx(lastIdx)
          return prev
        })
        onMealLoggedRef.current?.(meal)
      },
      // onError — don't spam chat with error messages, header already shows "reconnecting…"
      () => {
        setStreamBuffer(null)
        setConnected(false)
      },
      // onClose — auto-reconnect with exponential backoff (max 30s)
      () => {
        setStreamBuffer(null)
        setConnected(false)
        wsRef.current = null
        reconnectTimer.current = setTimeout(() => {
          reconnectDelay.current = Math.min(reconnectDelay.current * 2, 30000)
          ensureSocket()
        }, reconnectDelay.current)
      }
    )
    ws.addEventListener('open', () => {
      setConnected(true)
      reconnectDelay.current = 1000 // reset backoff on successful connect
    })
    wsRef.current = ws
    return ws
  }, [])

  const sendMessage = useCallback((text, type = 'chat', mode = null) => {
    const msg = text.trim()
    if (!msg || streamBuffer !== null) return

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
  }, [streamBuffer, ensureSocket])

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
    abortedRef.current = true
    setAborted(true)
    // Capture partial response and finalize with "[stopped]"
    setStreamBuffer((prev) => {
      const partial = prev || ''
      const stopped = partial ? partial + '\n\n[stopped]' : '[stopped]'
      setMessages((msgs) => [...msgs, { role: 'assistant', content: stopped }])
      return null
    })
  }, [])

  const handleSuggest = useCallback((mode) => {
    const modeLabels = {
      favorites: 'Sevdiğim yemeklerden kahvaltı öner',
      explore: 'Dünya mutfağından farklı bir kahvaltı öner',
    }
    const msg = modeLabels[mode] || 'Bana kahvaltı öner'
    sendMessage(msg, 'suggest', mode || null)
  }, [sendMessage])

  // Get the checked meal for DecidePanel (priority: checked block > null)
  const checkedMeal = checkedMealIdx !== null ? mealBlocks[checkedMealIdx] : null

  const [suppMenuOpen, setSuppMenuOpen] = useState(false)
  const [decideOpen, setDecideOpen] = useState(false)

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
          const displayText = hasMealBlock ? stripJsonBlock(m.content) : m.content

          return (
            <div key={i}>
              {displayText && (
                <div style={s.bubble(m.role)}>
                  {displayText}
                </div>
              )}
              {hasMealBlock && (
                <MealBlock
                  meal={mealBlocks[i]}
                  checked={checkedMealIdx === i}
                  onCheck={() => setCheckedMealIdx(prev => prev === i ? null : i)}
                  onSave={(updated) => setMealBlocks(prev => ({ ...prev, [i]: updated }))}
                />
              )}
            </div>
          )
        })}

        {streamBuffer !== null && streamBuffer !== '' && (
          <div style={s.bubble('assistant')}>{streamBuffer}</div>
        )}
        {streamBuffer === '' && (
          <div style={s.thinking}>thinking…</div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {decideOpen && (
        <DecidePanel
          meal={checkedMeal}
          onClose={() => setDecideOpen(false)}
          onConfirm={() => {
            setDecideOpen(false)
            setCheckedMealIdx(null)
          }}
        />
      )}

      <div style={s.actionRow}>
        {todaySupps.length > 0 && (
          <div style={s.suppMenuWrapper}>
            {suppMenuOpen && !decideOpen && (
              <div style={s.suppMenu}>
                <span style={s.suppMenuLabel}>Supplements</span>
                {todaySupps.map(sup => (
                  <button
                    key={sup.id}
                    style={s.suppPill(!!sup.taken_today)}
                    onClick={() => handleToggleSupplement(sup.id, !!sup.taken_today)}
                    title={sup.contents || sup.name}
                  >
                    {sup.taken_today ? '✓' : '○'} {sup.name}
                  </button>
                ))}
              </div>
            )}
            <button
              style={s.suppToggleBtn(suppMenuOpen && !decideOpen)}
              onClick={() => !decideOpen && setSuppMenuOpen(prev => !prev)}
              disabled={decideOpen}
              title="Toggle supplements"
            >
              Supps
            </button>
          </div>
        )}

        <button
          style={s.decideBtn(decideOpen)}
          onClick={() => {
            setDecideOpen(prev => !prev)
            if (!decideOpen) setSuppMenuOpen(false)
          }}
          disabled={streamBuffer !== null}
          title="Today I ate..."
        >
          ✅
        </button>

        <SuggestButton onSuggest={handleSuggest} disabled={streamBuffer !== null || decideOpen} />
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
          placeholder="Canın ne çekiyor?"
          rows={1}
          disabled={streamBuffer !== null}
        />
        {streamBuffer !== null ? (
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
}
