import { useState } from 'react'
import ChatInterface from './components/ChatInterface'
import RecipeCard from './components/RecipeCard'
import ScheduleTimeline from './components/ScheduleTimeline'
import IngredientPanel from './components/IngredientPanel'
import PreferencesPanel from './components/PreferencesPanel'
import LoginScreen from './components/LoginScreen'
import { logout } from './services/api'

const TABS = ['Chat', 'Ingredients', 'Preferences']

const s = {
  app: {
    display: 'grid',
    height: '100vh',
    gridTemplateRows: 'auto 1fr',
    maxWidth: 1200,
    margin: '0 auto',
    padding: 0,
  },
  nav: {
    display: 'flex',
    gap: 4,
    padding: '12px 16px 0',
    borderBottom: '1px solid var(--border)',
    background: 'var(--surface)',
    alignItems: 'center',
  },
  tab: (active) => ({
    padding: '8px 18px',
    background: active ? 'var(--surface2)' : 'none',
    border: 'none',
    borderRadius: '8px 8px 0 0',
    color: active ? 'var(--accent)' : 'var(--text-muted)',
    fontWeight: active ? 700 : 400,
    fontSize: 14,
    cursor: 'pointer',
    transition: 'color 0.15s',
  }),
  main: {
    display: 'grid',
    gridTemplateColumns: '1fr 320px',
    gap: 12,
    padding: 12,
    overflow: 'hidden',
    height: '100%',
  },
  mainFull: {
    padding: 12,
    height: '100%',
    overflow: 'hidden',
  },
  sidebar: {
    display: 'flex',
    flexDirection: 'column',
    gap: 12,
    overflowY: 'auto',
  },
  userInfo: {
    marginLeft: 'auto',
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    fontSize: 13,
    color: 'var(--text-muted)',
  },
  logoutBtn: {
    background: 'none',
    border: '1px solid var(--border)',
    borderRadius: 8,
    padding: '4px 10px',
    color: 'var(--text-muted)',
    fontSize: 12,
    cursor: 'pointer',
  },
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

export default function App() {
  const [auth, setAuth] = useState(getStoredAuth)
  const [activeTab, setActiveTab] = useState('Chat')
  const [latestMeal, setLatestMeal] = useState(null)
  const [latestMealId, setLatestMealId] = useState(null)
  const [ingredientRefresh, setIngredientRefresh] = useState(0)

  if (!auth) {
    return <LoginScreen onLogin={(data) => setAuth(data)} />
  }

  const handleMealLogged = (meal) => {
    setLatestMeal(meal)
    setLatestMealId(meal?.id ?? null)
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
          <span>{auth.user.name}</span>
          <button style={s.logoutBtn} onClick={handleLogout}>Çıkış</button>
        </div>
      </nav>

      <div style={{ ...s.main, display: activeTab === 'Chat' ? undefined : 'none' }}>
        <ChatInterface onMealLogged={handleMealLogged} />

        <div style={s.sidebar}>
          {latestMeal && (
            <RecipeCard meal={latestMeal} mealId={latestMealId} />
          )}
          {latestMeal?.schedule && (
            <ScheduleTimeline schedule={latestMeal.schedule} />
          )}
        </div>
      </div>

      <div style={{ ...s.mainFull, display: activeTab === 'Ingredients' ? undefined : 'none' }}>
        <IngredientPanel refreshTrigger={ingredientRefresh} />
      </div>

      <div style={{ ...s.mainFull, display: activeTab === 'Preferences' ? undefined : 'none' }}>
        <PreferencesPanel />
      </div>
    </div>
  )
}
