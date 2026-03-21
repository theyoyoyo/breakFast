import { useState, useRef, useEffect, useCallback } from 'react'
import { createChatSocket, getActiveSession, createSession, deleteSession, listSessions, getSessionMessages } from '../services/api'
import { useVoice } from '../hooks/useVoice'

const s = {
  container: {
    display: 'flex',
    flexDirection: 'column',
    height: '100%',
    background: 'var(--surface)',
    borderRadius: 'var(--radius)',
    overflow: 'hidden',
  },
  header: {
    padding: '16px 20px',
    borderBottom: '1px solid var(--border)',
    fontWeight: 600,
    fontSize: 16,
    color: 'var(--accent)',
    letterSpacing: '0.02em',
  },
  messages: {
    flex: 1,
    overflowY: 'auto',
    padding: '16px',
    display: 'flex',
    flexDirection: 'column',
    gap: 12,
  },
  bubble: (role) => ({
    maxWidth: '80%',
    alignSelf: role === 'user' ? 'flex-end' : 'flex-start',
    background: role === 'user' ? 'var(--accent2)' : 'var(--surface2)',
    color: 'var(--text)',
    borderRadius: role === 'user' ? '18px 18px 4px 18px' : '18px 18px 18px 4px',
    padding: '10px 14px',
    fontSize: 14,
    lineHeight: 1.6,
    whiteSpace: 'pre-wrap',
  }),
  inputRow: {
    display: 'flex',
    gap: 8,
    padding: '12px 16px',
    borderTop: '1px solid var(--border)',
    background: 'var(--surface)',
  },
  input: {
    flex: 1,
    background: 'var(--surface2)',
    border: '1px solid var(--border)',
    borderRadius: 24,
    padding: '10px 16px',
    color: 'var(--text)',
    fontSize: 14,
    outline: 'none',
    resize: 'none',
    minHeight: 42,
    maxHeight: 120,
  },
  sendBtn: {
    background: 'var(--accent)',
    color: '#fff',
    border: 'none',
    borderRadius: 24,
    padding: '10px 18px',
    fontWeight: 600,
    fontSize: 14,
    transition: 'opacity 0.15s',
  },
  micBtn: (active) => ({
    background: active ? 'var(--accent2)' : 'var(--surface2)',
    color: 'var(--text)',
    border: '1px solid var(--border)',
    borderRadius: 24,
    padding: '10px 14px',
    fontSize: 16,
    transition: 'background 0.15s',
  }),
  thinking: {
    alignSelf: 'flex-start',
    color: 'var(--text-muted)',
    fontSize: 13,
    padding: '6px 4px',
  },
  connStatus: {
    fontSize: 12,
    fontWeight: 400,
    color: 'var(--text-muted)',
  },
  newSessionBtn: {
    background: 'none',
    border: '1px solid var(--border)',
    borderRadius: 8,
    padding: '4px 10px',
    fontSize: 12,
    color: 'var(--text-muted)',
    cursor: 'pointer',
    marginLeft: 'auto',
  },
}

const WELCOME_MSG = { role: 'assistant', content: "Good morning! Tell me what's in your fridge and I'll plan your breakfast." }

export default function ChatInterface({ onMealLogged }) {
  const [messages, setMessages] = useState([WELCOME_MSG])
  const [input, setInput] = useState('')
  // null = idle, '' = thinking (no tokens yet), string = streaming content
  const [streamBuffer, setStreamBuffer] = useState(null)
  const [connected, setConnected] = useState(false)
  const [sessionId, setSessionId] = useState(null)
  const [hasOlder, setHasOlder] = useState(false)
  const [hasNewer, setHasNewer] = useState(false)
  const wsRef = useRef(null)
  const messagesEndRef = useRef(null)
  const reconnectTimer = useRef(null)
  const reconnectDelay = useRef(1000)
  const onMealLoggedRef = useRef(onMealLogged)
  const sessionIdRef = useRef(null)
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
        setMessages([WELCOME_MSG, ...loaded])
        await refreshNavState(session.id)
      } catch {
        // Backend not available yet — will work once connected
      }
    })()
    return () => { cancelled = true }
  }, [refreshNavState])

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
      // onToken
      (chunk) => setStreamBuffer((prev) => (prev ?? '') + chunk),
      // onDone
      (full) => {
        setMessages((prev) => [...prev, { role: 'assistant', content: full }])
        setStreamBuffer(null)
      },
      // onMealLogged
      (meal) => onMealLoggedRef.current?.(meal),
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

  const sendMessage = useCallback((text) => {
    const msg = text.trim()
    if (!msg || streamBuffer !== null) return

    setMessages((prev) => [...prev, { role: 'user', content: msg }])
    setInput('')

    const payload = { message: msg }
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
    setMessages([WELCOME_MSG, ...loaded])
    setStreamBuffer(null)
    setInput('')
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ session_id: targetId }))
    }
    await refreshNavState(targetId)
  }, [refreshNavState])

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

  return (
    <div style={s.container}>
      <div style={{ ...s.header, display: 'flex', alignItems: 'center' }}>
        <span>break FAST</span>
        {!connected && wsRef.current && (
          <span style={s.connStatus}> — reconnecting…</span>
        )}
        {hasOlder && (
          <button style={s.newSessionBtn} onClick={handleBack} title="Previous session">
            Back
          </button>
        )}
        {hasNewer && (
          <button style={s.newSessionBtn} onClick={handleNext} title="Next session">
            Next
          </button>
        )}
        <button style={s.newSessionBtn} onClick={handleNewSession} title="Start a new conversation">
          + New
        </button>
        <button style={{ ...s.newSessionBtn, color: 'var(--accent)' }} onClick={handleDeleteSession} title="Delete this session">
          Del
        </button>
      </div>

      <div style={s.messages}>
        {messages.map((m, i) => (
          <div key={i} style={s.bubble(m.role)}>
            {m.content}
          </div>
        ))}

        {streamBuffer !== null && streamBuffer !== '' && (
          <div style={s.bubble('assistant')}>{streamBuffer}</div>
        )}
        {streamBuffer === '' && (
          <div style={s.thinking}>thinking…</div>
        )}

        <div ref={messagesEndRef} />
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
          placeholder="What's in your fridge?"
          rows={1}
          disabled={streamBuffer !== null}
        />
        <button
          style={{ ...s.sendBtn, opacity: streamBuffer !== null ? 0.5 : 1 }}
          onClick={() => sendMessage(input)}
          disabled={streamBuffer !== null}
        >
          Send
        </button>
      </div>
    </div>
  )
}
