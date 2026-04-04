import { useCallback, useEffect, useMemo, useState } from 'react';
import trackingApi from '@/services/trackingApi';
import { loadGTM, testGTMEvent } from '@/services/trackingLoader';
import { sanitizeGTMContainerId, validateGTMContainerId } from '@/utils/validators';

const DEFAULT_STATE = {
  gtm_container_id: '',
  is_gtm_enabled: false,
  last_updated: null,
};

export default function useGTMConfig() {
  const [config, setConfig] = useState(DEFAULT_STATE);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [accessDenied, setAccessDenied] = useState(false);

  const fetchConfig = useCallback(async () => {
    setLoading(true);
    setError('');
    setAccessDenied(false);
    try {
      const response = await trackingApi.getGTMConfig();
      setConfig({
        gtm_container_id: sanitizeGTMContainerId(response?.gtm_container_id || ''),
        is_gtm_enabled: Boolean(response?.is_gtm_enabled),
        last_updated: response?.last_updated || null,
      });
    } catch (err) {
      if (err?.response?.status === 403) {
        setAccessDenied(true);
      } else {
        setError(err?.response?.data?.message || 'Unable to load GTM settings.');
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void fetchConfig();
  }, [fetchConfig]);

  const setEnabled = useCallback((enabled) => {
    setConfig((previous) => ({
      ...previous,
      is_gtm_enabled: Boolean(enabled),
    }));
  }, []);

  const setGtmId = useCallback((value) => {
    setConfig((previous) => ({
      ...previous,
      gtm_container_id: sanitizeGTMContainerId(value),
    }));
  }, []);

  const validation = useMemo(() => {
    if (!config.is_gtm_enabled) {
      return { isValid: true, sanitized: sanitizeGTMContainerId(config.gtm_container_id), error: '' };
    }
    return validateGTMContainerId(config.gtm_container_id);
  }, [config.gtm_container_id, config.is_gtm_enabled]);

  const saveConfig = useCallback(async () => {
    if (!validation.isValid) {
      return { ok: false, message: validation.error };
    }

    setSaving(true);
    setError('');
    setAccessDenied(false);

    try {
      const payload = {
        gtm_container_id: validation.sanitized,
        is_gtm_enabled: config.is_gtm_enabled,
      };
      const saved = await trackingApi.saveGTMConfig(payload);
      const next = {
        gtm_container_id: sanitizeGTMContainerId(saved?.gtm_container_id || payload.gtm_container_id),
        is_gtm_enabled: Boolean(saved?.is_gtm_enabled),
        last_updated: saved?.last_updated || new Date().toISOString(),
      };
      setConfig(next);

      if (next.is_gtm_enabled) {
        loadGTM(next.gtm_container_id);
      }
      return { ok: true, message: 'GTM settings saved successfully.' };
    } catch (err) {
      if (err?.response?.status === 403) {
        setAccessDenied(true);
        return { ok: false, message: 'Access denied.' };
      }
      const message = err?.response?.data?.message || 'Failed to save GTM settings.';
      setError(message);
      return { ok: false, message };
    } finally {
      setSaving(false);
    }
  }, [config.is_gtm_enabled, validation]);

  const runTest = useCallback(() => {
    if (!config.is_gtm_enabled) {
      return { ok: false, message: 'Enable GTM before running a test event.' };
    }
    if (!validation.isValid) {
      return { ok: false, message: validation.error };
    }

    loadGTM(validation.sanitized);
    testGTMEvent();
    return { ok: true, message: 'Test event pushed to dataLayer.' };
  }, [config.is_gtm_enabled, validation]);

  return {
    config,
    loading,
    saving,
    error,
    accessDenied,
    validation,
    setEnabled,
    setGtmId,
    saveConfig,
    runTest,
    refetch: fetchConfig,
  };
}
