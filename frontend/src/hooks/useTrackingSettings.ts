import { useEffect, useState } from 'react';
import apiClient from '@/services/api/client';

export interface TrackingSettings {
  clarity_tracking_id: string;
  clarity_enabled: boolean;
}

const CACHE_KEY = 'aurora:tracking_settings:public';
const DEFAULT_SETTINGS: TrackingSettings = {
  clarity_tracking_id: '',
  clarity_enabled: false,
};

const normalizeSettings = (raw: any): TrackingSettings => ({
  clarity_tracking_id: String(raw?.clarity_tracking_id || '').trim(),
  clarity_enabled: Boolean(raw?.clarity_enabled),
});

const readCachedSettings = (): TrackingSettings => {
  if (typeof window === 'undefined') return DEFAULT_SETTINGS;
  try {
    const raw = localStorage.getItem(CACHE_KEY);
    if (!raw) return DEFAULT_SETTINGS;
    return normalizeSettings(JSON.parse(raw));
  } catch {
    return DEFAULT_SETTINGS;
  }
};

export function useTrackingSettings() {
  const [settings, setSettings] = useState<TrackingSettings>(() => readCachedSettings());

  useEffect(() => {
    let mounted = true;

    const run = async () => {
      try {
        const response = await apiClient.get('/v1/settings/public/');
        const next = normalizeSettings(response?.data?.data || {});
        if (!mounted) return;
        setSettings(next);
        if (typeof window !== 'undefined') {
          localStorage.setItem(CACHE_KEY, JSON.stringify(next));
        }
      } catch {
        if (!mounted) return;
        setSettings(readCachedSettings());
      }
    };

    void run();

    return () => {
      mounted = false;
    };
  }, []);

  return settings;
}

export default useTrackingSettings;
