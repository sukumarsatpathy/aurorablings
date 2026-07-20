/**
 * Access to the server-injected bootstrap payload.
 *
 * In production, nginx SSI embeds `window.__BOOT__` into index.html before
 * any JS runs (see backend/apps/banners/bootstrap.py). It carries:
 *   - banners:  the /api/v1/banners/active/ payload
 *   - settings: the /api/v1/features/public-settings/ data (or null)
 *
 * Consumers must treat it as an optimisation only — it is absent in dev and
 * whenever the SSI subrequest failed, in which case they fall back to the
 * APIs. It reflects state at HTML-delivery time (server-side cache TTL 5 min),
 * which is the same freshness the fetch-once-at-boot callers had before.
 */

export interface BootData {
  banners?: unknown[];
  settings?: Record<string, unknown> | null;
}

declare global {
  interface Window {
    __BOOT__?: BootData;
  }
}

export const getBootData = (): BootData | undefined => {
  if (typeof window === 'undefined') return undefined;
  const boot = window.__BOOT__;
  return boot && typeof boot === 'object' ? boot : undefined;
};

export const getBootSettings = (): Record<string, unknown> | undefined => {
  const settings = getBootData()?.settings;
  return settings && typeof settings === 'object' ? settings : undefined;
};
