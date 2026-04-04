import { useMemo, useState } from 'react';
import { CheckCircle2, XCircle, ShieldX, Clock3 } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/Card';
import { Skeleton } from '@/components/ui/Skeleton';
import GTMCard from '@/components/tracking/GTMCard';
import useGTMConfig from '@/hooks/useGTMConfig';

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

export default function GTMSettings() {
  const [toast, setToast] = useState(null);
  const { config, loading, saving, error, accessDenied, validation, setEnabled, setGtmId, saveConfig, runTest } = useGTMConfig();

  const status = useMemo(() => {
    if (!config.gtm_container_id) return 'Not Configured';
    if (!validation.isValid) return 'Invalid';
    if (config.is_gtm_enabled) return 'Active';
    return 'Disabled';
  }, [config.gtm_container_id, config.is_gtm_enabled, validation.isValid]);

  const showToast = (type, message) => {
    setToast({ type, message });
    window.setTimeout(() => setToast(null), 3200);
  };

  const onSave = async () => {
    const result = await saveConfig();
    showToast(result.ok ? 'success' : 'error', result.message);
  };

  const onTest = () => {
    const result = runTest();
    showToast(result.ok ? 'success' : 'error', result.message);
  };

  const formattedLastUpdated = useMemo(() => {
    if (!config.last_updated) return 'Not saved yet';
    const date = new Date(config.last_updated);
    if (Number.isNaN(date.getTime())) return 'Not saved yet';
    return new Intl.DateTimeFormat(undefined, {
      year: 'numeric',
      month: 'short',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    }).format(date);
  }, [config.last_updated]);

  if (accessDenied) {
    return (
      <div className="space-y-6 p-4 md:p-6">
        <Card className="border-destructive/40 bg-destructive/10">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-destructive">
              <ShieldX className="h-5 w-5" />
              Access Denied
            </CardTitle>
            <CardDescription className="text-destructive/90">
              You do not have permission to manage GTM settings.
            </CardDescription>
          </CardHeader>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6 p-4 md:p-6">
      <div className="rounded-2xl border border-border/60 bg-gradient-to-r from-slate-50 via-white to-slate-100 p-5 shadow-sm">
        <h1 className="text-2xl font-semibold tracking-tight text-slate-900">Google Tag Manager Settings</h1>
        <p className="mt-2 max-w-3xl text-sm text-slate-600">Manage GTM container for tracking and analytics</p>
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

      {loading ? (
        <Card>
          <CardContent className="space-y-3 p-6">
            <Skeleton className="h-6 w-1/3" />
            <Skeleton className="h-14 w-full" />
            <Skeleton className="h-11 w-full" />
            <div className="grid grid-cols-2 gap-2">
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
            </div>
          </CardContent>
        </Card>
      ) : (
        <GTMCard
          enabled={config.is_gtm_enabled}
          gtmId={config.gtm_container_id}
          validationMessage={config.is_gtm_enabled && !validation.isValid ? validation.error : ''}
          status={status}
          loading={loading}
          saving={saving}
          canSave={!config.is_gtm_enabled || validation.isValid}
          onToggle={setEnabled}
          onIdChange={setGtmId}
          onSave={onSave}
          onTest={onTest}
        />
      )}

      {toast ? (
        <div className="pointer-events-none fixed right-4 top-4 z-50 w-full max-w-md">
          <Toast type={toast.type} message={toast.message} />
        </div>
      ) : null}
    </div>
  );
}
