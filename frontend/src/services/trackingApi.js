import apiClient from '@/services/api/client';
import { sanitizeTrackingConfig } from '@/utils/validators';

const TRACKING_ENDPOINT = '/v1/settings/tracking/';

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

export const getGTMConfig = async () => {
  const response = await apiClient.get(TRACKING_ENDPOINT, {
    headers: authHeaders(),
  });
  return normalizeGTMResponse(response);
};

export const saveGTMConfig = async (config) => {
  const payload = {
    gtm_container_id: String(config?.gtm_container_id || '').trim(),
    is_gtm_enabled: Boolean(config?.is_gtm_enabled),
  };
  const response = await apiClient.post(TRACKING_ENDPOINT, payload, {
    headers: authHeaders(),
  });
  return normalizeGTMResponse(response);
};

const trackingApi = {
  getTrackingConfig,
  saveTrackingConfig,
  getGTMConfig,
  saveGTMConfig,
};

export default trackingApi;
