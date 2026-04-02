export type ConsentCategory = 'necessary' | 'analytics' | 'marketing' | 'preferences';

export type ConsentStatus = 'accepted_all' | 'rejected_all' | 'customized' | 'withdrawn';

export type ConsentSource = 'banner' | 'settings_modal' | 'withdrawal';

export interface ConsentCategories {
  necessary: boolean;
  analytics: boolean;
  marketing: boolean;
  preferences: boolean;
}

export interface ConsentPayload {
  version: string;
  status: ConsentStatus;
  categories: ConsentCategories;
  consented_at: string;
  source: ConsentSource;
  anonymous_id: string;
  metadata?: Record<string, unknown>;
}

const CONSENT_STORAGE_KEY = 'aurora.cookie.consent';
const ANON_ID_STORAGE_KEY = 'aurora.cookie.anonymous_id';
const CONSENT_VERSION = '1.0';

const DEFAULT_CATEGORIES: ConsentCategories = {
  necessary: true,
  analytics: false,
  marketing: false,
  preferences: false,
};

const listeners = new Set<(consent: ConsentPayload | null) => void>();
let memoryConsent: ConsentPayload | null = null;

const getApiBaseUrl = (): string => {
  const raw = (import.meta.env.VITE_API_BASE_URL || '/api').replace(/\/+$/, '');
  return raw || '/api';
};

const buildPrivacyEndpoint = (path: string): string => {
  const base = getApiBaseUrl();
  if (base.endsWith('/v1')) {
    return `${base.replace(/\/v1$/, '')}/privacy/${path}`;
  }
  return `${base}/privacy/${path}`;
};

const generateAnonymousId = (): string => {
  const partA = Math.random().toString(36).slice(2, 10);
  const partB = Date.now().toString(36);
  return `anon_${partA}${partB}`;
};

export const getAnonymousId = (): string => {
  const existing = localStorage.getItem(ANON_ID_STORAGE_KEY);
  if (existing) return existing;

  const created = generateAnonymousId();
  localStorage.setItem(ANON_ID_STORAGE_KEY, created);
  return created;
};

export const getStoredConsent = (): ConsentPayload | null => {
  if (memoryConsent) return memoryConsent;

  const raw = localStorage.getItem(CONSENT_STORAGE_KEY);
  if (!raw) return null;

  try {
    const parsed = JSON.parse(raw) as ConsentPayload;
    if (!parsed?.categories?.necessary) {
      return null;
    }
    memoryConsent = parsed;
    return parsed;
  } catch {
    return null;
  }
};

const notifyConsentListeners = (consent: ConsentPayload | null) => {
  listeners.forEach((listener) => listener(consent));
  window.dispatchEvent(new CustomEvent('aurora:consent-updated', { detail: consent }));
};

export const subscribeToConsent = (listener: (consent: ConsentPayload | null) => void): (() => void) => {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
};

export const hasConsent = (category: ConsentCategory): boolean => {
  const consent = getStoredConsent();
  if (!consent) return false;
  return Boolean(consent.categories[category]);
};

export const canLoadAnalytics = (): boolean => hasConsent('analytics');

export const canLoadMarketing = (): boolean => hasConsent('marketing');

export const getDefaultCategories = (): ConsentCategories => ({ ...DEFAULT_CATEGORIES });

export const createConsentPayload = (
  status: ConsentStatus,
  categories: ConsentCategories,
  source: ConsentSource,
): ConsentPayload => ({
  version: CONSENT_VERSION,
  status,
  categories: {
    necessary: true,
    analytics: Boolean(categories.analytics),
    marketing: Boolean(categories.marketing),
    preferences: Boolean(categories.preferences),
  },
  consented_at: new Date().toISOString(),
  source,
  anonymous_id: getAnonymousId(),
});

const postConsentToApi = async (payload: ConsentPayload): Promise<void> => {
  const endpoint = payload.status === 'withdrawn' ? 'consent/withdraw/' : 'consent/';
  const requestBody =
    payload.status === 'withdrawn'
      ? {
          version: payload.version,
          source: payload.source,
          anonymous_id: payload.anonymous_id,
          metadata: payload.metadata || {},
        }
      : payload;
  try {
    await fetch(buildPrivacyEndpoint(endpoint), {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      credentials: 'include',
      body: JSON.stringify(requestBody),
    });
  } catch {
    // Non-blocking by design: local preference state remains source of truth.
  }
};

export const saveConsent = async (payload: ConsentPayload): Promise<void> => {
  const next: ConsentPayload = {
    ...payload,
    categories: {
      necessary: true,
      analytics: Boolean(payload.categories.analytics),
      marketing: Boolean(payload.categories.marketing),
      preferences: Boolean(payload.categories.preferences),
    },
  };

  localStorage.setItem(CONSENT_STORAGE_KEY, JSON.stringify(next));
  memoryConsent = next;
  notifyConsentListeners(next);
  await postConsentToApi(next);
};

export const withdrawConsent = async (): Promise<void> => {
  const payload = createConsentPayload('withdrawn', getDefaultCategories(), 'withdrawal');
  await saveConsent(payload);
};

export const clearConsent = (): void => {
  localStorage.removeItem(CONSENT_STORAGE_KEY);
  memoryConsent = null;
  notifyConsentListeners(null);
};

export const getConsentVersion = (): string => CONSENT_VERSION;
