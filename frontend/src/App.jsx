import { useState, useEffect, useRef } from 'react'
import { MessageCircle, Refrigerator, SlidersHorizontal, Star, Settings, LogOut } from 'lucide-react'
import ChatInterface from './components/ChatInterface'
import IngredientPanel from './components/IngredientPanel'
import PreferencesPanel from './components/PreferencesPanel'
import FavoritesPanel from './components/FavoritesPanel'
import SettingsPanel from './components/SettingsPanel'
import LoginScreen from './components/LoginScreen'
import { logout, checkAuth, NetworkError } from './services/api'
import * as s from './App.styles'

const TABS = [
  { key: 'Chat', label: 'Chat', Icon: MessageCircle },
  { key: 'Ingredients', label: 'Ingredients', Icon: Refrigerator },
  { key: 'Preferences', label: 'Preferences', Icon: SlidersHorizontal },
  { key: 'Favorites', label: 'Favorites', Icon: Star },
  { key: 'Settings', label: 'Settings', Icon: Settings },
]

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
  const [offline, setOffline] = useState(false)

  // Validate stored token against backend on app start
  useEffect(() => {
    if (!auth) { setAuthChecked(true); return }
    checkAuth()
      .then(() => { setAuthChecked(true); setOffline(false) })
      .catch((err) => {
        if (err instanceof NetworkError) {
          setOffline(true)
          setAuthChecked(true) // let user in with stale token
        } else {
          logout()
          setAuth(null)
          setAuthChecked(true)
        }
      })
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // Periodically check backend connectivity when offline
  useEffect(() => {
    if (!offline || !auth) return
    const id = setInterval(() => {
      checkAuth()
        .then(() => setOffline(false))
        .catch(() => {})
    }, 10_000)
    return () => clearInterval(id)
  }, [offline, auth])
  const chatRef = useRef(null)
  const ingredientRef = useRef(null)
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
      {offline && <div style={s.offlineBanner}>Backend unreachable — retrying...</div>}
      <nav style={s.nav}>
        {TABS.map(({ key, label, Icon }) => (
          <button
            key={key}
            style={s.tab(activeTab === key)}
            onClick={() => {
              if (key === activeTab && auth.user.name === 'demo') {
                if (key === 'Chat') chatRef.current?.injectDemoSchedule()
                else if (key === 'Ingredients') ingredientRef.current?.injectDemoShopping()
                else setActiveTab(key)
              } else {
                setActiveTab(key)
              }
            }}
          >
            <Icon size={14} style={{ marginRight: 4, verticalAlign: -2 }} />
            {label}
          </button>
        ))}
        <div style={s.userInfo}>
          <span
            style={{ cursor: 'pointer' }}
            onClick={() => chatRef.current?.injectDemoMeal()}
            title="Demo action"
          >{auth.user.name}</span>
          <button style={s.logoutBtn} onClick={handleLogout}>
            <LogOut size={12} style={{ marginRight: 4, verticalAlign: -1 }} />
            Logout
          </button>
        </div>
      </nav>

      <div style={{ ...s.mainFull, display: activeTab === 'Chat' ? undefined : 'none' }}>
        <ChatInterface ref={chatRef} onMealLogged={handleMealLogged} visible={activeTab === 'Chat'} />
      </div>
      <div style={{ ...s.mainFull, display: activeTab === 'Ingredients' ? undefined : 'none' }}>
        <IngredientPanel ref={ingredientRef} refreshTrigger={ingredientRefresh} visible={activeTab === 'Ingredients'} />
      </div>
      <div style={{ ...s.mainFull, display: activeTab === 'Preferences' ? undefined : 'none' }}>
        <PreferencesPanel />
      </div>
      <div style={{ ...s.mainFull, display: activeTab === 'Favorites' ? undefined : 'none' }}>
        <FavoritesPanel
          visible={activeTab === 'Favorites'}
          onSendToChat={(meal) => {
            chatRef.current?.injectFavoriteMeal(meal)
            setActiveTab('Chat')
          }}
        />
      </div>
      <div style={{ ...s.mainFull, display: activeTab === 'Settings' ? undefined : 'none' }}>
        <SettingsPanel visible={activeTab === 'Settings'} />
      </div>
    </div>
  )
}
