import { useState } from 'react'
import ChatInterface from './components/ChatInterface'
import RecipeCard from './components/RecipeCard'
import ScheduleTimeline from './components/ScheduleTimeline'
import IngredientPanel from './components/IngredientPanel'
import PreferencesPanel from './components/PreferencesPanel'

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
}

export default function App() {
  const [activeTab, setActiveTab] = useState('Chat')
  const [latestMeal, setLatestMeal] = useState(null)
  const [latestMealId, setLatestMealId] = useState(null)
  const [ingredientRefresh, setIngredientRefresh] = useState(0)

  const handleMealLogged = (meal) => {
    setLatestMeal(meal)
    setLatestMealId(meal?.id ?? null)
    // Refresh ingredient panel since meal logging might affect inventory context
    setIngredientRefresh((n) => n + 1)
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
