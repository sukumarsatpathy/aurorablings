import { useCallback, useEffect, useMemo, useState } from 'react';
import trackingApi from '@/services/trackingApi';
import trackingLoader from '@/services/trackingLoader';
import { sanitizeTrackingConfig, validateTrackingConfig, validateTrackingValue } from '@/utils/validators';

const EMPTY_CONFIG = {
  gtm_id: '',
  meta_pixel_id: '',
  ga4_id: '',
  google_ads_id: '',
  clarity_id: '',
  enabled: {
    gtm: false,
    meta: false,
    ga4: false,
    google_ads: false,
    clarity: false,
  },
  last_updated: null,
};

const FIELD_BY_PROVIDER = {
  gtm: 'gtm_id',
  meta: 'meta_pixel_id',
  ga4: 'ga4_id',
  google_ads: 'google_ads_id',
  clarity: 'clarity_id',
};

export const useTrackingConfig = () => {
  const [config, setConfig] = useState(EMPTY_CONFIG);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [errorsByField, setErrorsByField] = useState({});

  const fetchConfig = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const remoteConfig = await trackingApi.getTrackingConfig();
      setConfig(sanitizeTrackingConfig(remoteConfig));
      setErrorsByField({});
    } catch (err) {
      setError(err?.response?.data?.message || 'Unable to load tracking settings.');
      setConfig(EMPTY_CONFIG);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void fetchConfig();
  }, [fetchConfig]);

  const updateId = useCallback((field, value) => {
    setConfig((previous) => ({
      ...previous,
      [field]: value,
    }));
  }, []);

  const updateEnabled = useCallback((provider, enabled) => {
    setConfig((previous) => ({
      ...previous,
      enabled: {
        ...previous.enabled,
        [provider]: Boolean(enabled),
      },
    }));
  }, []);

  const saveConfig = useCallback(async () => {
    const validation = validateTrackingConfig(config);
    setErrorsByField(validation.errors);

    if (!validation.isValid) {
      return {
        ok: false,
        message: 'Please fix invalid tracking IDs before saving.',
      };
    }

    setSaving(true);
    setError('');

    try {
      const persisted = await trackingApi.saveTrackingConfig(validation.sanitized);
      const safePersisted = sanitizeTrackingConfig({
        ...persisted,
        last_updated: persisted.last_updated || new Date().toISOString(),
      });
      setConfig(safePersisted);
      setErrorsByField({});
      trackingLoader.init(safePersisted);
      return { ok: true, config: safePersisted, message: 'Tracking settings saved successfully.' };
    } catch (err) {
      const message = err?.response?.data?.message || 'Failed to save tracking settings.';
      setError(message);
      return { ok: false, message };
    } finally {
      setSaving(false);
    }
  }, [config]);

  const testProvider = useCallback(
    (provider) => {
      const field = FIELD_BY_PROVIDER[provider];
      const idValue = config[field];

      if (!config.enabled[provider]) {
        return { ok: false, message: 'Enable this provider before testing.' };
      }

      const validation = validateTrackingValue(provider, idValue);
      if (!validation.isValid) {
        setErrorsByField((previous) => ({
          ...previous,
          [field]: validation.error,
        }));
        return { ok: false, message: validation.error };
      }

      trackingLoader.init(config);
      trackingLoader.testTracking(provider);
      return { ok: true, message: 'Test event fired. Check browser console and provider debugger.' };
    },
    [config]
  );

  const lastUpdated = useMemo(() => {
    if (!config.last_updated) return null;
    const date = new Date(config.last_updated);
    if (Number.isNaN(date.getTime())) return null;
    return date;
  }, [config.last_updated]);

  return {
    config,
    loading,
    saving,
    error,
    errorsByField,
    lastUpdated,
    updateId,
    updateEnabled,
    saveConfig,
    testProvider,
    refetch: fetchConfig,
  };
};

export default useTrackingConfig;
