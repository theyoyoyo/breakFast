import { useState } from 'react'
import { Eye, EyeOff } from 'lucide-react'
import { login, NetworkError, LoginLimitError } from '../services/api'
import * as s from './LoginScreen.styles'
import Logo from './Logo'

/** The message for a rate-limited login: the wait in seconds or minutes, or "later" when unknown. */
export function retryMessage(seconds) {
  if (!seconds) return 'Too many failed logins. Try again later.'
  if (seconds < 60) return `Too many failed logins. Try again in ${seconds} seconds.`
  const minutes = Math.ceil(seconds / 60)
  return `Too many failed logins. Try again in ${minutes} minute${minutes === 1 ? '' : 's'}.`
}

function errorMessage(err) {
  if (err instanceof NetworkError) return 'Cannot reach server'
  if (err instanceof LoginLimitError) return retryMessage(err.retryAfter)
  return 'Invalid name or PIN'
}

/** `note` tells the user why the login is back (their session ended); none on a plain start. */
export default function LoginScreen({ onLogin, note = '' }) {
  const [name, setName] = useState('demo')
  const [pin, setPin] = useState('')
  // Our own show/hide button: the browser's built-in one hides once the field loses focus with text in it
  const [showPin, setShowPin] = useState(false)
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
      setError(errorMessage(err))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={s.container}>
      <Logo withName height={56} />
      <form style={s.form} onSubmit={handleSubmit}>
        {note && <div style={s.note} role="status">{note}</div>}
        <input
          style={s.input}
          type="text"
          placeholder="Name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          autoFocus
        />
        <div style={s.pinField}>
          <input
            style={{ ...s.input, ...s.pinInput }}
            className="bf-pin"
            type={showPin ? 'text' : 'password'}
            placeholder="PIN"
            value={pin}
            onChange={(e) => setPin(e.target.value)}
            inputMode="numeric"
            autoComplete="current-password"
          />
          <button
            type="button"
            style={s.revealBtn}
            onClick={() => setShowPin(v => !v)}
            aria-label={showPin ? 'Hide PIN' : 'Show PIN'}
            aria-pressed={showPin}
          >
            {showPin ? <EyeOff size={18} /> : <Eye size={18} />}
          </button>
        </div>
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
