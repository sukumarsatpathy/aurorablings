import apiClient from '@/services/api/client';
import { sanitizeTrackingConfig } from '@/utils/validators';

const TRACKING_ENDPOINT = '/v1/settings/tracking/';
const FEATURE_SETTINGS_ENDPOINT = '/v1/features/settings/';
const GTM_CONTAINER_KEY = 'gtm_container_id';
const GTM_ENABLED_KEY = 'is_gtm_enabled';
const META_PIXEL_KEY = 'meta_pixel_id';
const META_ENABLED_KEY = 'is_meta_enabled';
const GA4_KEY = 'ga4_id';
const GA4_ENABLED_KEY = 'is_ga4_enabled';
const CLARITY_TRACKING_KEY = 'CLARITY_TRACKING_ID';
const CLARITY_ENABLED_KEY = 'CLARITY_ENABLED';

const authHeaders = () => {
  const token = localStorage.getItem('auth_token');
  return token ? { Authorization: `Bearer ${token}` } : {};
};

const toServerShape = (config) => ({
  gtm_id: config.gtm_id || '',
  meta_pixel_id: config.meta_pixel_id || '',
  ga4_id: config.ga4_id || '',
  clarity_id: config.clarity_id || '',
  enabled: {
    gtm: Boolean(config.enabled?.gtm),
    meta: Boolean(config.enabled?.meta),
    ga4: Boolean(config.enabled?.ga4),
    clarity: Boolean(config.enabled?.clarity),
  },
});

const normalizeServerResponse = (payload) => {
  const raw = payload?.data?.data || payload?.data || payload || {};
  const safe = sanitizeTrackingConfig(raw);
  return {
    ...safe,
    last_updated: raw.last_updated || raw.updated_at || safe.last_updated || null,
  };
};

export const getTrackingConfig = async () => {
  try {
    const response = await apiClient.get(TRACKING_ENDPOINT, {
      headers: authHeaders(),
    });
    return normalizeServerResponse(response);
  } catch (error) {
    if (!isNotFound(error)) throw error;

    const response = await apiClient.get(FEATURE_SETTINGS_ENDPOINT, {
      headers: authHeaders(),
    });
    const rows = Array.isArray(response?.data?.data)
      ? response.data.data
      : Array.isArray(response?.data?.data?.results)
        ? response.data.data.results
        : Array.isArray(response?.data?.results)
          ? response.data.results
          : [];

    const getSetting = (key) => rows.find((row) => String(row?.key || '').trim() === key);
    const gtmId = String(getSetting(GTM_CONTAINER_KEY)?.value || '').trim();
    const gtmEnabled = toBooleanSetting(getSetting(GTM_ENABLED_KEY)?.value);
    const metaId = String(getSetting(META_PIXEL_KEY)?.value || '').trim();
    const metaEnabled = toBooleanSetting(getSetting(META_ENABLED_KEY)?.value);
    const ga4Id = String(getSetting(GA4_KEY)?.value || '').trim();
    const ga4Enabled = toBooleanSetting(getSetting(GA4_ENABLED_KEY)?.value);
    const clarityId = String(getSetting(CLARITY_TRACKING_KEY)?.value || '').trim();
    const clarityEnabled = toBooleanSetting(getSetting(CLARITY_ENABLED_KEY)?.value);

    const allUpdatedAt = rows
      .map((row) => row?.updated_at)
      .filter(Boolean)
      .sort()
      .reverse();

    return {
      gtm_id: gtmId,
      meta_pixel_id: metaId,
      ga4_id: ga4Id,
      clarity_id: clarityId,
      enabled: {
        gtm: gtmEnabled,
        meta: metaEnabled,
        ga4: ga4Enabled,
        clarity: clarityEnabled,
      },
      last_updated: allUpdatedAt[0] || null,
    };
  }
};

export const saveTrackingConfig = async (config) => {
  const safe = sanitizeTrackingConfig(config);
  try {
    const response = await apiClient.post(TRACKING_ENDPOINT, toServerShape(safe), {
      headers: authHeaders(),
    });
    return normalizeServerResponse(response);
  } catch (error) {
    if (!isNotFound(error)) throw error;

    await Promise.all([
      upsertFeatureSetting(GTM_CONTAINER_KEY, safe.gtm_id, 'string', {
        category: 'advanced',
        label: 'GTM Container ID',
        description: 'Google Tag Manager container ID used for storefront tracking.',
        is_public: true,
      }),
      upsertFeatureSetting(GTM_ENABLED_KEY, String(Boolean(safe.enabled?.gtm)), 'boolean', {
        category: 'advanced',
        label: 'Enable GTM',
        description: 'Controls whether GTM script should be injected at runtime.',
        is_public: true,
      }),
      upsertFeatureSetting(META_PIXEL_KEY, safe.meta_pixel_id, 'string', {
        category: 'advanced',
        label: 'Meta Pixel ID',
        description: 'Meta Pixel ID for conversion tracking.',
        is_public: false,
      }),
      upsertFeatureSetting(META_ENABLED_KEY, String(Boolean(safe.enabled?.meta)), 'boolean', {
        category: 'advanced',
        label: 'Enable Meta Pixel',
        description: 'Controls whether Meta Pixel should be injected at runtime.',
        is_public: false,
      }),
      upsertFeatureSetting(GA4_KEY, safe.ga4_id, 'string', {
        category: 'advanced',
        label: 'GA4 Measurement ID',
        description: 'Google Analytics 4 measurement ID.',
        is_public: false,
      }),
      upsertFeatureSetting(GA4_ENABLED_KEY, String(Boolean(safe.enabled?.ga4)), 'boolean', {
        category: 'advanced',
        label: 'Enable GA4',
        description: 'Controls whether GA4 should be injected at runtime.',
        is_public: false,
      }),
      upsertFeatureSetting(CLARITY_TRACKING_KEY, safe.clarity_id, 'string', {
        category: 'advanced',
        label: 'Clarity Tracking ID',
        description: 'Microsoft Clarity project tracking ID used for storefront runtime analytics.',
        is_public: false,
      }),
      upsertFeatureSetting(CLARITY_ENABLED_KEY, String(Boolean(safe.enabled?.clarity)), 'boolean', {
        category: 'advanced',
        label: 'Enable Clarity',
        description: 'Controls whether Microsoft Clarity is injected on storefront pages.',
        is_public: false,
      }),
    ]);

    return {
      ...safe,
      last_updated: new Date().toISOString(),
    };
  }
};

const normalizeGTMResponse = (payload) => {
  const raw = payload?.data?.data || payload?.data || payload || {};
  const legacyId = raw.gtm_id || '';
  const legacyEnabled = raw.enabled?.gtm;
  return {
    gtm_container_id: String(raw.gtm_container_id ?? legacyId ?? '').trim(),
    is_gtm_enabled: Boolean(raw.is_gtm_enabled ?? legacyEnabled ?? false),
    last_updated: raw.last_updated || raw.updated_at || null,
  };
};

const parseSettingDetail = (payload) => {
  const raw = payload?.data?.data || payload?.data || payload || {};
  return {
    key: String(raw.key || '').trim(),
    value: raw.value,
    value_type: String(raw.value_type || 'string'),
    updated_at: raw.updated_at || null,
    label: String(raw.label || '').trim(),
  };
};

const toBooleanSetting = (value) => {
  if (typeof value === 'boolean') return value;
  const asText = String(value ?? '').trim().toLowerCase();
  return asText === 'true' || asText === '1' || asText === 'yes';
};

const isNotFound = (error) => Number(error?.response?.status) === 404;

const upsertFeatureSetting = async (key, value, valueType, defaults = {}) => {
  const detailPath = `${FEATURE_SETTINGS_ENDPOINT}${encodeURIComponent(key)}/`;
  const payload = {
    key,
    value: String(value ?? ''),
    value_type: valueType,
    category: defaults.category || 'advanced',
    label: defaults.label || key,
    description: defaults.description || '',
    is_public: Boolean(defaults.is_public),
    is_editable: true,
  };

  try {
    await apiClient.patch(detailPath, payload, {
      headers: authHeaders(),
    });
  } catch (error) {
    if (!isNotFound(error)) throw error;
    await apiClient.post(FEATURE_SETTINGS_ENDPOINT, payload, {
      headers: authHeaders(),
    });
  }
};

const normalizePublicPayload = (payload) => payload?.data?.data || payload?.data || payload || {};

const getSettingValueFromArray = (settings, key) => {
  if (!Array.isArray(settings)) return undefined;
  const match = settings.find((entry) => String(entry?.key || '').trim() === key);
  return match?.value;
};

export const getPublicGTMConfig = async () => {
  const response = await apiClient.get('/v1/features/public-settings/');
  const data = normalizePublicPayload(response);
  const objectShape = data?.settings && typeof data.settings === 'object' ? data.settings : data;
  const legacyId = objectShape?.gtm_id || '';
  const legacyEnabled = objectShape?.enabled?.gtm;
  const gtmFromSettingsArray = getSettingValueFromArray(data?.settings, GTM_CONTAINER_KEY);
  const enabledFromSettingsArray = getSettingValueFromArray(data?.settings, GTM_ENABLED_KEY);
  return {
    gtm_container_id: String(objectShape?.gtm_container_id ?? legacyId ?? gtmFromSettingsArray ?? '').trim(),
    is_gtm_enabled: toBooleanSetting(objectShape?.is_gtm_enabled ?? legacyEnabled ?? enabledFromSettingsArray ?? false),
    last_updated: objectShape?.last_updated || objectShape?.updated_at || data?.last_updated || data?.updated_at || null,
  };
};

export const getGTMConfig = async () => {
  try {
    const response = await apiClient.get(TRACKING_ENDPOINT, {
      headers: authHeaders(),
    });
    return normalizeGTMResponse(response);
  } catch (error) {
    if (!isNotFound(error)) throw error;

    const safeGetSetting = async (key) => {
      try {
        const response = await apiClient.get(`${FEATURE_SETTINGS_ENDPOINT}${key}/`, {
          headers: authHeaders(),
        });
        return parseSettingDetail(response);
      } catch (innerError) {
        if (isNotFound(innerError)) {
          return { key, value: '', value_type: 'string', updated_at: null, label: '' };
        }
        throw innerError;
      }
    };

    const [containerSetting, enabledSetting] = await Promise.all([
      safeGetSetting(GTM_CONTAINER_KEY),
      safeGetSetting(GTM_ENABLED_KEY),
    ]);

    return {
      gtm_container_id: String(containerSetting.value || '').trim(),
      is_gtm_enabled: toBooleanSetting(enabledSetting.value),
      last_updated: containerSetting.updated_at || enabledSetting.updated_at || null,
    };
  }
};

export const saveGTMConfig = async (config) => {
  const payload = {
    gtm_container_id: String(config?.gtm_container_id || '').trim(),
    is_gtm_enabled: Boolean(config?.is_gtm_enabled),
  };

  try {
    const response = await apiClient.post(TRACKING_ENDPOINT, payload, {
      headers: authHeaders(),
    });
    return normalizeGTMResponse(response);
  } catch (error) {
    if (!isNotFound(error)) throw error;

    await Promise.all([
      upsertFeatureSetting(GTM_CONTAINER_KEY, payload.gtm_container_id, 'string', {
        category: 'advanced',
        label: 'GTM Container ID',
        description: 'Google Tag Manager container ID used for storefront tracking.',
        is_public: true,
      }),
      upsertFeatureSetting(GTM_ENABLED_KEY, String(payload.is_gtm_enabled), 'boolean', {
        category: 'advanced',
        label: 'Enable GTM',
        description: 'Controls whether GTM script should be injected at runtime.',
        is_public: true,
      }),
    ]);

    return {
      ...payload,
      last_updated: new Date().toISOString(),
    };
  }
};

const trackingApi = {
  getTrackingConfig,
  saveTrackingConfig,
  getGTMConfig,
  getPublicGTMConfig,
  saveGTMConfig,
};

export default trackingApi;
