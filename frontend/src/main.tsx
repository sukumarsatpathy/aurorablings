import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import trackingLoader from './services/trackingLoader'

declare global {
  interface Window {
    dataLayer?: unknown[]
  }
}

const toBoolean = (value: unknown) => {
  if (typeof value === 'boolean') return value
  const normalized = String(value ?? '').trim().toLowerCase()
  return normalized === 'true' || normalized === '1' || normalized === 'yes'
}

const ensureBootstrapDataLayer = () => {
  if (typeof window === 'undefined') return
  window.dataLayer = window.dataLayer || []
}

const getValueFromSettingsArray = (settings: unknown, key: string) => {
  if (!Array.isArray(settings)) return undefined
  const target = settings.find((entry) => String((entry as any)?.key || '').trim() === key) as any
  return target?.value
}

const parsePublicGtmPayload = (raw: any) => {
  const payload = raw?.data?.data || raw?.data || raw || {}
  const objectShape = payload?.settings && typeof payload.settings === 'object' ? payload.settings : payload
  const gtmFromArray = getValueFromSettingsArray(payload?.settings, 'gtm_container_id')
  const enabledFromArray = getValueFromSettingsArray(payload?.settings, 'is_gtm_enabled')
  const gtmId = String(
    objectShape?.gtm_container_id ??
    objectShape?.gtm_id ??
    gtmFromArray ??
    ''
  ).trim()
  const isEnabled = toBoolean(
    objectShape?.is_gtm_enabled ??
    objectShape?.enabled?.gtm ??
    enabledFromArray ??
    false
  )
  return { gtmId, isEnabled }
}

const bootstrapGTM = async () => {
  ensureBootstrapDataLayer()
  try {
    const apiBase = String(import.meta.env.VITE_API_BASE_URL || '/api').replace(/\/$/, '')
    const response = await fetch(`${apiBase}/v1/features/public-settings/`, {
      method: 'GET',
      credentials: 'include',
      headers: { Accept: 'application/json' },
    })
    if (!response.ok) return

    const json = await response.json()
    const { gtmId, isEnabled } = parsePublicGtmPayload(json)
    if (isEnabled && gtmId) {
      trackingLoader.loadGTM(gtmId)
    }
  } catch {
    // Ignore GTM bootstrap failures to avoid blocking app startup.
  }
}

/**
 * Defer analytics until the browser is idle.
 *
 * This is the only GTM bootstrap now — index.html used to run a duplicate copy
 * inline in <head>, which fired the same public-settings request a second time
 * and blocked the parser before the hero image preload.
 *
 * Trade-off: GTM initialises up to ~1s later than before, so a small number of
 * very-fast-bounce sessions will go unrecorded. That is the right call for a
 * tag manager (it must never sit on the critical rendering path), but it can
 * look like a metrics regression if you are not expecting it.
 */
const whenIdle = (fn: () => void) => {
  if (typeof window === 'undefined') return
  if ('requestIdleCallback' in window) {
    window.requestIdleCallback(fn, { timeout: 3000 })
  } else {
    window.setTimeout(fn, 1000)
  }
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)

whenIdle(() => {
  void bootstrapGTM()
})
