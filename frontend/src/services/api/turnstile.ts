import apiClient from './client';

export interface TurnstilePublicConfig {
  turnstile_enabled: boolean;
  turnstile_site_key: string;
}

let cachedConfig: TurnstilePublicConfig | null = null;
let cachedAt = 0;
const CACHE_TTL_MS = 60 * 1000;

const normalizeConfig = (raw: any): TurnstilePublicConfig => ({
  turnstile_enabled: Boolean(raw?.turnstile_enabled),
  turnstile_site_key: String(raw?.turnstile_site_key || ''),
});

const turnstileService = {
  async getPublicConfig(forceRefresh = false): Promise<TurnstilePublicConfig> {
    const now = Date.now();
    if (!forceRefresh && cachedConfig && now - cachedAt < CACHE_TTL_MS) {
      return cachedConfig;
    }

    const response = await apiClient.get('/settings/public');
    const config = normalizeConfig(response?.data?.data || {});
    cachedConfig = config;
    cachedAt = now;
    return config;
  },
};

export default turnstileService;
