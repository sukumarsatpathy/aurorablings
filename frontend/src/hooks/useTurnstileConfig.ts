import { useEffect, useState } from 'react';
import turnstileService, { type TurnstilePublicConfig } from '@/services/api/turnstile';

const DEFAULT_CONFIG: TurnstilePublicConfig = {
  turnstile_enabled: false,
  turnstile_site_key: '',
};

export function useTurnstileConfig() {
  const [config, setConfig] = useState<TurnstilePublicConfig>(DEFAULT_CONFIG);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let mounted = true;
    const run = async () => {
      try {
        const next = await turnstileService.getPublicConfig();
        if (mounted) {
          setConfig(next);
        }
      } catch {
        if (mounted) {
          setConfig(DEFAULT_CONFIG);
        }
      } finally {
        if (mounted) {
          setLoading(false);
        }
      }
    };
    void run();
    return () => {
      mounted = false;
    };
  }, []);

  return {
    turnstileEnabled: config.turnstile_enabled,
    turnstileSiteKey: config.turnstile_site_key,
    loading,
  };
}
