import { useState, useRef, useEffect, useCallback } from 'react'
import { createChatSocket } from '../services/api'
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
}

export default function ChatInterface({ onMealLogged }) {
  const [messages, setMessages] = useState([
    {
      role: 'assistant',
      content: "Good morning! Tell me what's in your fridge and I'll plan your breakfast.",
    },
  ])
  const [input, setInput] = useState('')
  // null = idle, '' = thinking (no tokens yet), string = streaming content
  const [streamBuffer, setStreamBuffer] = useState(null)
  const [connected, setConnected] = useState(false)
  const wsRef = useRef(null)
  const messagesEndRef = useRef(null)
  const reconnectTimer = useRef(null)
  const reconnectDelay = useRef(1000)
  const onMealLoggedRef = useRef(onMealLogged)
  const { isListening, startListening, stopListening, speak, supported: voiceSupported } = useVoice()
  const speakRef = useRef(speak)

  // Keep refs in sync so socket callbacks always see the latest props/functions
  useEffect(() => { onMealLoggedRef.current = onMealLogged }, [onMealLogged])
  useEffect(() => { speakRef.current = speak }, [speak])

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

    const ws = ensureSocket()
    if (ws.readyState === WebSocket.OPEN) {
      setStreamBuffer('')  // '' = thinking
      ws.send(JSON.stringify({ message: msg }))
    } else {
      // Backend not connected yet — wait for connection, then send
      setStreamBuffer('')
      ws.addEventListener('open', () => ws.send(JSON.stringify({ message: msg })), { once: true })
    }
  }, [streamBuffer, ensureSocket])

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage(input)
    }
  }

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
      <div style={s.header}>
        break FAST
        {!connected && wsRef.current && (
          <span style={s.connStatus}> — reconnecting…</span>
        )}
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
