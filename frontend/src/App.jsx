import { useState, useEffect, useRef } from 'react'
import ChatInterface from './components/ChatInterface'
import IngredientPanel from './components/IngredientPanel'
import PreferencesPanel from './components/PreferencesPanel'
import SettingsPanel from './components/SettingsPanel'
import LoginScreen from './components/LoginScreen'
import { logout, checkAuth } from './services/api'
import * as s from './App.styles'

const TABS = ['Chat', 'Ingredients', 'Preferences', 'Settings']

function getStoredAuth() {
  const token = localStorage.getItem('bf_token')
  const userStr = localStorage.getItem('bf_user')
  if (token && userStr) {
    try {
      return { token, user: JSON.parse(userStr) }
    } catch {
      return null
    }
  }
  return null
}

export default function App() {
  const [auth, setAuth] = useState(getStoredAuth)
  const [authChecked, setAuthChecked] = useState(false)
  const [activeTab, setActiveTab] = useState('Chat')

  // Validate stored token against backend on app start
  useEffect(() => {
    if (!auth) { setAuthChecked(true); return }
    checkAuth()
      .then(() => setAuthChecked(true))
      .catch(() => {
        logout()
        setAuth(null)
        setAuthChecked(true)
      })
  }, []) // eslint-disable-line react-hooks/exhaustive-deps
  const chatRef = useRef(null)
  const [ingredientRefresh, setIngredientRefresh] = useState(0)

  if (!authChecked) return null // wait for token validation
  if (!auth) {
    return <LoginScreen onLogin={(data) => setAuth(data)} />
  }

  const handleMealLogged = () => {
    setIngredientRefresh((n) => n + 1)
  }

  const handleLogout = () => {
    logout()
    setAuth(null)
  }

  return (
    <div style={s.app}>
      <nav style={s.nav}>
        {TABS.map((tab) => (
          <button
            key={tab}
            style={s.tab(activeTab === tab)}
            onClick={() => setActiveTab(tab)}
          >
            {tab}
          </button>
        ))}
        <div style={s.userInfo}>
          <span
            style={{ cursor: 'pointer' }}
            onClick={() => chatRef.current?.injectDemoMeal()}
            title="Inject demo meal"
          >{auth.user.name}</span>
          <button style={s.logoutBtn} onClick={handleLogout}>Logout</button>
        </div>
      </nav>

      <div style={{ ...s.mainFull, display: activeTab === 'Chat' ? undefined : 'none' }}>
        <ChatInterface ref={chatRef} onMealLogged={handleMealLogged} />
      </div>

      <div style={{ ...s.mainFull, display: activeTab === 'Ingredients' ? undefined : 'none' }}>
        <IngredientPanel refreshTrigger={ingredientRefresh} />
      </div>

      <div style={{ ...s.mainFull, display: activeTab === 'Preferences' ? undefined : 'none' }}>
        <PreferencesPanel />
      </div>

      <div style={{ ...s.mainFull, display: activeTab === 'Settings' ? undefined : 'none' }}>
        <SettingsPanel visible={activeTab === 'Settings'} />
      </div>
    </div>
  )
}
