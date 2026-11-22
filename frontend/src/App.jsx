import { useState, useEffect, useRef } from 'react'
import { MessageCircle, Refrigerator, SlidersHorizontal, Star, Settings, LogOut } from 'lucide-react'
import ChatInterface from './components/ChatInterface'
import IngredientPanel from './components/IngredientPanel'
import PreferencesPanel from './components/PreferencesPanel'
import FavoritesPanel from './components/FavoritesPanel'
import SettingsPanel from './components/SettingsPanel'
import LoginScreen from './components/LoginScreen'
import { logout, checkAuth, getPreferences, onSessionEnded, NetworkError } from './services/api'
import { applyTheme } from './utils/theme'
import { applyAppearance } from './utils/appearance'
import { applyLanguage } from './utils/language'
import * as s from './App.styles'

const TABS = [
  { key: 'Chat', label: 'Chat', Icon: MessageCircle },
  { key: 'Ingredients', label: 'Fridge', Icon: Refrigerator },
  { key: 'Preferences', label: 'Preferences', Icon: SlidersHorizontal },
  { key: 'Favorites', label: 'Favorites', Icon: Star },
  { key: 'Settings', label: 'Settings', Icon: Settings },
]

// The open tab's name in the link (#fridge, #settings…), so a refresh reopens it; Chat has none
const tabHash = (key) => (key === 'Chat' ? '' : `#${TABS.find(t => t.key === key).label.toLowerCase()}`)

// The tab the link names, or Chat when it names none or an unknown one
const tabFromLink = () => {
  const hash = window.location.hash.toLowerCase()
  return TABS.find(t => tabHash(t.key) === hash)?.key ?? 'Chat'
}

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

function useIsNarrow(breakpoint = 540) {
  const [narrow, setNarrow] = useState(() => window.innerWidth < breakpoint)
  useEffect(() => {
    const onResize = () => setNarrow(window.innerWidth < breakpoint)
    window.addEventListener('resize', onResize)
    return () => window.removeEventListener('resize', onResize)
  }, [breakpoint])
  return narrow
}

export default function App() {
  const [auth, setAuth] = useState(getStoredAuth)
  const [authChecked, setAuthChecked] = useState(false)
  // A refresh with a stored session reopens the link's tab; a login starts on Chat
  const [activeTab, setActiveTab] = useState(() => (auth ? tabFromLink() : 'Chat'))
  const [offline, setOffline] = useState(false)
  // The login screen says why it's back when the server refused the session
  const [sessionEnded, setSessionEnded] = useState(false)
  const narrow = useIsNarrow()

  // A refused request already cleared the stored session: show the login with a note
  useEffect(() => onSessionEnded(() => {
    setAuth(null)
    setSessionEnded(true)
  }), [])

  // When the device's session ends (Logout, or refused at start), the next login starts on Chat
  useEffect(() => {
    if (!auth) setActiveTab('Chat')
  }, [auth])

  // Keep the open tab in the link while logged in. The link is replaced, not pushed,
  // so Back doesn't step through tabs.
  useEffect(() => {
    const hash = auth ? tabHash(activeTab) : ''
    if (window.location.hash === hash) return
    const { pathname, search } = window.location
    window.history.replaceState(window.history.state, '', pathname + search + hash)
  }, [auth, activeTab])

  // A tab typed into the link opens too
  useEffect(() => {
    if (!auth) return
    const onHashChange = () => setActiveTab(tabFromLink())
    window.addEventListener('hashchange', onHashChange)
    return () => window.removeEventListener('hashchange', onHashChange)
  }, [auth])

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

  // Apply the logged-in user's saved theme (orange if none), appearance (Auto if none) and AI language
  // (English if none), so a shared device follows the user
  const userId = auth?.user?.id
  useEffect(() => {
    if (!userId) return
    getPreferences()
      .then(prefs => {
        applyTheme(prefs.find(p => p.key === 'theme')?.value)
        applyAppearance(prefs.find(p => p.key === 'appearance')?.value)
        applyLanguage(prefs.find(p => p.key === 'response_language')?.value)
      })
      .catch(() => {}) // offline — keep this device's last theme and language
  }, [userId])

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
    return (
      <LoginScreen
        note={sessionEnded ? 'Your session ended. Please log in again.' : ''}
        onLogin={(data) => { setSessionEnded(false); setAuth(data) }}
      />
    )
  }

  // Demo triggers (name click, re-clicking Chat/Fridge) are for the demo account only
  const isDemo = auth.user.name === 'demo'

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
            style={s.tab(activeTab === key, narrow)}
            onClick={() => {
              if (key === activeTab && isDemo) {
                if (key === 'Chat') chatRef.current?.injectDemoSchedule()
                else if (key === 'Ingredients') ingredientRef.current?.injectDemoShopping()
                else setActiveTab(key)
              } else {
                setActiveTab(key)
              }
            }}
            title={label}
          >
            <Icon size={narrow ? 18 : 14} style={narrow ? { verticalAlign: -3 } : { marginRight: 4, verticalAlign: -2 }} />
            {!narrow && label}
          </button>
        ))}
        <div style={s.userInfo}>
          <span
            style={{ ...s.userChip(narrow), ...(isDemo ? { cursor: 'pointer' } : {}) }}
            onClick={isDemo ? () => chatRef.current?.injectDemoMeal() : undefined}
            title={isDemo ? 'Demo action' : auth.user.name}
          >
            <span style={s.userAvatar}>{(auth.user.name || '?').charAt(0).toUpperCase()}</span>
            {!narrow && <span style={s.userName}>{auth.user.name}</span>}
          </span>
          <button className="logout-btn" style={s.logoutBtn} onClick={handleLogout} title="Logout">
            <LogOut size={12} style={narrow ? { verticalAlign: -1 } : { marginRight: 4, verticalAlign: -1 }} />
            {!narrow && 'Logout'}
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
