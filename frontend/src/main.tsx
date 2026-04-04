import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import trackingLoader from './services/trackingLoader'

const toBoolean = (value: unknown) => {
  if (typeof value === 'boolean') return value
  const normalized = String(value ?? '').trim().toLowerCase()
  return normalized === 'true' || normalized === '1' || normalized === 'yes'
}

const bootstrapGTM = async () => {
  try {
    const apiBase = String(import.meta.env.VITE_API_BASE_URL || '/api').replace(/\/$/, '')
    const response = await fetch(`${apiBase}/v1/features/public-settings/`, {
      method: 'GET',
      credentials: 'include',
      headers: { Accept: 'application/json' },
    })
    if (!response.ok) return

    const json = await response.json()
    const payload = json?.data?.data || json?.data || json || {}
    const gtmId = String(payload.gtm_container_id || payload.gtm_id || '').trim()
    const isEnabled = toBoolean(payload.is_gtm_enabled ?? payload?.enabled?.gtm ?? false)
    if (isEnabled && gtmId) {
      trackingLoader.loadGTM(gtmId)
    }
  } catch {
    // Ignore GTM bootstrap failures to avoid blocking app startup.
  }
}

void bootstrapGTM()

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
