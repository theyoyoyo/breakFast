import { useState, useEffect } from 'react'
import { getKitchenAppliances, toggleKitchenAppliance } from '../services/api'
import * as s from './KitchenSettings.styles'

export default function KitchenSettings({ onBack }) {
  const [appliances, setAppliances] = useState([])
  const [error, setError] = useState(null)

  useEffect(() => {
    getKitchenAppliances()
      .then(setAppliances)
      .catch(() => setError('Failed to load kitchen appliances'))
  }, [])

  const handleToggle = async (key, currentEnabled) => {
    const newEnabled = !currentEnabled
    // Optimistic update
    setAppliances(prev => prev.map(a => a.key === key ? { ...a, enabled: newEnabled } : a))
    try {
      await toggleKitchenAppliance(key, newEnabled)
    } catch {
      // Revert on failure
      setAppliances(prev => prev.map(a => a.key === key ? { ...a, enabled: currentEnabled } : a))
      setError('Failed to update appliance')
    }
  }

  return (
    <div style={s.container}>
      <div style={{ ...s.header, display: 'flex', alignItems: 'center', gap: 8 }}>
        <button style={s.backBtn} onClick={onBack}>←</button>
        <span>Kitchen</span>
      </div>
      <div style={s.body}>
        {error && <div style={s.error}>{error}</div>}
        <div style={s.grid}>
          {appliances.map(a => (
            <div
              key={a.key}
              style={s.tile(a.enabled)}
              onClick={() => handleToggle(a.key, a.enabled)}
            >
              <span style={s.tileName}>{a.name}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
