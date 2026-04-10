import { useMemo, useState } from 'react';
import { CheckCircle2, XCircle, Clock3 } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/Card';
import TrackingCard from '@/components/tracking/TrackingCard';
import useTrackingConfig from '@/hooks/useTrackingConfig';
import { sanitizeTrackingValue, validateTrackingValue } from '@/utils/validators';

const PROVIDERS = [
  {
    key: 'gtm',
    title: 'Google Tag Manager (GTM)',
    description: 'Centralized tag management for marketing and analytics scripts.',
    fieldName: 'gtm_id',
    placeholder: 'GTM-XXXXXXX',
  },
  {
    key: 'meta',
    title: 'Meta Pixel',
    description: 'Meta conversion and audience tracking for campaigns.',
    fieldName: 'meta_pixel_id',
    placeholder: '123456789012345',
  },
  {
    key: 'ga4',
    title: 'Google Analytics (GA4)',
    description: 'Event analytics with modern Google Analytics properties.',
    fieldName: 'ga4_id',
    placeholder: 'G-XXXXXXXXXX',
  },
  {
    key: 'google_ads',
    title: 'Google Ads',
    description: 'Google Ads conversion tracking using Google tag (gtag.js).',
    fieldName: 'google_ads_id',
    placeholder: 'AW-1234567890',
  },
  {
    key: 'clarity',
    title: 'Microsoft Clarity',
    description: 'Session recordings, heatmaps, and behavior insights.',
    fieldName: 'clarity_id',
    placeholder: 'abcd12xy',
  },
];

const Toast = ({ type, message }) => {
  const isError = type === 'error';
  return (
    <div
      className={`flex items-center gap-2 rounded-xl border px-4 py-3 text-sm shadow-lg ${
        isError ? 'border-destructive/40 bg-destructive/10 text-destructive' : 'border-emerald-500/30 bg-emerald-500/10 text-emerald-700'
      }`}
    >
      {isError ? <XCircle className="h-4 w-4" /> : <CheckCircle2 className="h-4 w-4" />}
      <span>{message}</span>
    </div>
  );
};

export default function TrackingSettings() {
  const [toast, setToast] = useState(null);
  const {
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
  } = useTrackingConfig();

  const formattedLastUpdated = useMemo(() => {
    if (!lastUpdated) return 'Not saved yet';
    return new Intl.DateTimeFormat(undefined, {
      year: 'numeric',
      month: 'short',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    }).format(lastUpdated);
  }, [lastUpdated]);

  const showToast = (type, message) => {
    setToast({ type, message, id: Date.now() });
    window.setTimeout(() => setToast(null), 3200);
  };

  const handleIdChange = (fieldName, value) => {
    const provider = PROVIDERS.find((item) => item.fieldName === fieldName)?.key || '';
    updateId(fieldName, sanitizeTrackingValue(provider, value));
  };

  const handleSave = async () => {
    const result = await saveConfig();
    showToast(result.ok ? 'success' : 'error', result.message);
  };

  const handleTest = (provider) => {
    const result = testProvider(provider);
    showToast(result.ok ? 'success' : 'error', result.message);
  };

  return (
    <div className="space-y-6 p-4 md:p-6">
      <div className="rounded-2xl border border-border/60 bg-gradient-to-r from-slate-50 via-white to-slate-100 p-5 shadow-sm">
        <h1 className="text-2xl font-semibold tracking-tight text-slate-900">Tracking Integrations</h1>
        <p className="mt-2 max-w-3xl text-sm text-slate-600">
          Manage script-based integrations with secure validation, runtime loading, and controlled activation.
        </p>
        <div className="mt-3 flex items-center gap-2 text-xs text-slate-500">
          <Clock3 className="h-3.5 w-3.5" />
          <span>Last Updated: {formattedLastUpdated}</span>
        </div>
      </div>

      {error ? (
        <Card className="border-destructive/40 bg-destructive/10">
          <CardContent className="p-4 text-sm text-destructive">{error}</CardContent>
        </Card>
      ) : null}

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        {PROVIDERS.map((provider) => {
          const fieldError = errorsByField[provider.fieldName];
          const currentValue = config[provider.fieldName] || '';
          const formatValidation = validateTrackingValue(provider.key, currentValue);
          const showLiveError =
            config.enabled[provider.key] && currentValue && !formatValidation.isValid
              ? formatValidation.error
              : '';

          return (
            <TrackingCard
              key={provider.key}
              providerKey={provider.key}
              title={provider.title}
              description={provider.description}
              enabled={config.enabled[provider.key]}
              idValue={currentValue}
              placeholder={provider.placeholder}
              fieldName={provider.fieldName}
              error={fieldError || showLiveError}
              loading={loading}
              saving={saving}
              onToggle={(checked) => updateEnabled(provider.key, checked)}
              onIdChange={handleIdChange}
              onSave={handleSave}
              onTest={() => handleTest(provider.key)}
            />
          );
        })}
      </div>

      {toast ? (
        <div className="pointer-events-none fixed right-4 top-4 z-50 w-full max-w-md">
          <Toast type={toast.type} message={toast.message} />
        </div>
      ) : null}
    </div>
  );
}
