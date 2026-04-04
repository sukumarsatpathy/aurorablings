import apiClient from '@/services/api/client';
import { sanitizeTrackingConfig } from '@/utils/validators';

const TRACKING_ENDPOINT = '/v1/settings/tracking/';
const FEATURE_SETTINGS_ENDPOINT = '/v1/features/settings/';
const GTM_CONTAINER_KEY = 'gtm_container_id';
const GTM_ENABLED_KEY = 'is_gtm_enabled';

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
  const response = await apiClient.get(TRACKING_ENDPOINT, {
    headers: authHeaders(),
  });
  return normalizeServerResponse(response);
};

export const saveTrackingConfig = async (config) => {
  const safe = sanitizeTrackingConfig(config);
  const response = await apiClient.post(TRACKING_ENDPOINT, toServerShape(safe), {
    headers: authHeaders(),
  });
  return normalizeServerResponse(response);
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

export const getPublicGTMConfig = async () => {
  const response = await apiClient.get('/v1/features/public-settings/');
  const data = normalizePublicPayload(response);
  const legacyId = data.gtm_id || '';
  const legacyEnabled = data?.enabled?.gtm;
  return {
    gtm_container_id: String(data.gtm_container_id ?? legacyId ?? '').trim(),
    is_gtm_enabled: toBooleanSetting(data.is_gtm_enabled ?? legacyEnabled ?? false),
    last_updated: data.last_updated || data.updated_at || null,
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
