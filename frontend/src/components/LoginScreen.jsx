import { useState } from 'react'
import { login, NetworkError } from '../services/api'
import * as s from './LoginScreen.styles'

export default function LoginScreen({ onLogin }) {
  const [name, setName] = useState('demo')
  const [pin, setPin] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!name.trim()) return

    setLoading(true)
    setError('')
    try {
      const data = await login(name.trim(), pin.trim())
      // Store auth in localStorage
      localStorage.setItem('bf_token', data.token)
      localStorage.setItem('bf_user', JSON.stringify(data.user))
      onLogin(data)
    } catch (err) {
      setError(err instanceof NetworkError ? 'Cannot reach server' : 'Invalid name or PIN')
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
          placeholder="Name"
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
          {loading ? 'Logging in...' : 'Login'}
        </button>
        {error && <div style={s.error}>{error}</div>}
      </form>
    </div>
  )
}
