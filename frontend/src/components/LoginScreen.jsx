import { useState } from 'react'
import { login } from '../services/api'

const s = {
  container: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    height: '100vh',
    background: 'var(--bg)',
    gap: 24,
  },
  title: {
    fontSize: 32,
    fontWeight: 700,
    color: 'var(--accent)',
    letterSpacing: '0.02em',
  },
  form: {
    display: 'flex',
    flexDirection: 'column',
    gap: 12,
    width: 280,
  },
  input: {
    background: 'var(--surface2)',
    border: '1px solid var(--border)',
    borderRadius: 12,
    padding: '12px 16px',
    color: 'var(--text)',
    fontSize: 16,
    outline: 'none',
  },
  btn: {
    background: 'var(--accent)',
    color: '#fff',
    border: 'none',
    borderRadius: 12,
    padding: '12px 18px',
    fontWeight: 600,
    fontSize: 16,
    cursor: 'pointer',
    transition: 'opacity 0.15s',
  },
  error: {
    color: '#e74c3c',
    fontSize: 14,
    textAlign: 'center',
  },
}

export default function LoginScreen({ onLogin }) {
  const [name, setName] = useState('demo')
  const [pin, setPin] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!name.trim() || !pin.trim()) return

    setLoading(true)
    setError('')
    try {
      const data = await login(name.trim(), pin.trim())
      // Store auth in localStorage
      localStorage.setItem('bf_token', data.token)
      localStorage.setItem('bf_user', JSON.stringify(data.user))
      onLogin(data)
    } catch {
      setError('Geçersiz isim veya PIN')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={s.container}>
      <div style={s.title}>break FAST</div>
      <form style={s.form} onSubmit={handleSubmit}>
        <input
          style={s.input}
          type="text"
          placeholder="İsim"
          value={name}
          onChange={(e) => setName(e.target.value)}
          autoFocus
        />
        <input
          style={s.input}
          type="password"
          placeholder="PIN"
          value={pin}
          onChange={(e) => setPin(e.target.value)}
          inputMode="numeric"
        />
        <button
          style={{ ...s.btn, opacity: loading ? 0.5 : 1 }}
          type="submit"
          disabled={loading}
        >
          {loading ? 'Giriş yapılıyor...' : 'Giriş'}
        </button>
        {error && <div style={s.error}>{error}</div>}
      </form>
    </div>
  )
}
