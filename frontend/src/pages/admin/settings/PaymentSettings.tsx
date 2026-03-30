import React, { useEffect, useMemo, useState } from 'react';
import { Card } from '@/components/ui/Card';
import settingsService from '@/services/api/settings';
import notificationsAdminService, { type NotificationEmailPreviewTest } from '@/services/api/adminNotifications';
import { Button } from '@/components/ui/Button';
import type { AppSetting, SettingCategory } from '@/types/setting';
import { CashfreeForm } from './CashfreeForm';
import { RazorpayForm } from './RazorpayForm';
import { PaymentGatewayCard } from './PaymentGatewayCard';
import { getBundlesForCategory, makePayloadFromBundle, validateBundleValues } from './helpers';
import type { PluginSettingBundle } from './types';

interface Props {
  title: string;
  category: SettingCategory;
  settings: AppSetting[];
  canEdit: boolean;
  onRefresh: () => Promise<void>;
  onToast: (variant: 'success' | 'error' | 'info', message: string) => void;
}

export const PaymentSettings: React.FC<Props> = ({
  title,
  category,
  settings,
  canEdit,
  onRefresh,
  onToast,
}) => {
  const defaults = useMemo(() => {
    if (category === 'payment') return ['cashfree', 'razorpay'];
    return [];
  }, [category]);

  const bundles = useMemo(
    () => getBundlesForCategory(settings, category, defaults),
    [settings, category, defaults]
  );
  const [valuesByKey, setValuesByKey] = useState<Record<string, Record<string, unknown>>>({});
  const [savingKey, setSavingKey] = useState<string>('');
  const [testingPreview, setTestingPreview] = useState(false);
  const [previewResult, setPreviewResult] = useState<NotificationEmailPreviewTest | null>(null);

  useEffect(() => {
    const next: Record<string, Record<string, unknown>> = {};
    for (const bundle of bundles) {
      next[bundle.configKey] = bundle.value;
    }
    setValuesByKey(next);
  }, [bundles]);

  const saveBundle = async (bundle: PluginSettingBundle) => {
    const value = valuesByKey[bundle.configKey] || {};
    const errors = validateBundleValues(bundle.schema, value);
    if (errors.length > 0) {
      onToast('error', errors[0]);
      return;
    }

    try {
      setSavingKey(bundle.configKey);
      const payload = makePayloadFromBundle(bundle, value);
      if (bundle.configSetting) {
        await settingsService.update(bundle.configSetting.key, payload);
      } else {
        await settingsService.create(payload);
      }
      onToast('success', `${bundle.title} settings saved.`);
      await onRefresh();
    } catch (error: any) {
      const message = error?.response?.data?.message || `Failed to save ${bundle.title} settings.`;
      onToast('error', message);
    } finally {
      setSavingKey('');
    }
  };

  const runPreviewTest = async () => {
    try {
      setTestingPreview(true);
      const response = await notificationsAdminService.testEmailPreviewUrl();
      const payload = response?.data?.data || response?.data || response;
      setPreviewResult(payload as NotificationEmailPreviewTest);
      onToast('success', 'Email preview URL tested.');
    } catch (error: any) {
      setPreviewResult(null);
      onToast('error', error?.response?.data?.message || 'Failed to test email preview URL.');
    } finally {
      setTestingPreview(false);
    }
  };

  const auditRows = bundles
    .map((b) => ({
      key: b.configKey,
      updatedAt: b.configSetting?.updated_at || '',
      editable: b.configSetting?.is_editable ?? true,
      public: b.configSetting?.is_public ?? false,
    }))
    .sort((a, b) => (a.updatedAt < b.updatedAt ? 1 : -1));

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-lg font-semibold text-foreground">{title}</h2>
        <p className="text-xs text-muted-foreground">Schema-driven plugin forms with per-gateway save and audit metadata.</p>
      </div>

      {bundles.length === 0 ? (
        <Card className="rounded-2xl border border-border/70 bg-white p-5 text-sm text-muted-foreground">
          No schema-driven plugin settings found for {title}. Create setting keys like <code>{`${category}.your_plugin`}</code> with JSON value to enable this section.
        </Card>
      ) : bundles.map((bundle) => {
        const value = valuesByKey[bundle.configKey] || bundle.value;
        const onChange = (next: Record<string, unknown>) => {
          setValuesByKey((prev) => ({ ...prev, [bundle.configKey]: next }));
        };
        const onSave = () => saveBundle(bundle);
        const saving = savingKey === bundle.configKey;
        const pluginKey = bundle.pluginKey.toLowerCase();

        if (pluginKey === 'cashfree') {
          return (
            <CashfreeForm
              key={bundle.configKey}
              bundle={bundle}
              value={value}
              saving={saving}
              canEdit={canEdit}
              onChange={onChange}
              onSave={onSave}
            />
          );
        }
        if (pluginKey === 'razorpay') {
          return (
            <RazorpayForm
              key={bundle.configKey}
              bundle={bundle}
              value={value}
              saving={saving}
              canEdit={canEdit}
              onChange={onChange}
              onSave={onSave}
            />
          );
        }
        return (
          <PaymentGatewayCard
            key={bundle.configKey}
            bundle={bundle}
            value={value}
            saving={saving}
            canEdit={canEdit}
            onChange={onChange}
            onSave={onSave}
          />
        );
      })}

      {category === 'notification' ? (
        <Card className="rounded-2xl border border-border/70 bg-white p-4">
          <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
            <div>
              <h3 className="text-sm font-semibold text-foreground">Welcome Email Logo Check</h3>
              <p className="text-xs text-muted-foreground">
                Test the resolved logo URL used in welcome emails before sending.
              </p>
            </div>
            <Button disabled={testingPreview} onClick={runPreviewTest}>
              {testingPreview ? 'Testing...' : 'Test Email Preview URL'}
            </Button>
          </div>

          {previewResult ? (
            <div className="mt-4 rounded-xl border border-border/60 bg-muted/10 p-3 text-xs space-y-1">
              <p><span className="font-semibold text-foreground">Logo URL:</span> <a className="text-[#517b4b] underline break-all" href={previewResult.logo_url} target="_blank" rel="noreferrer">{previewResult.logo_url}</a></p>
              <p><span className="font-semibold text-foreground">Public Host:</span> {previewResult.is_public_host ? 'Yes' : 'No'}</p>
              <p><span className="font-semibold text-foreground">Reachable:</span> {previewResult.reachable ? 'Yes' : 'No'}</p>
              <p><span className="font-semibold text-foreground">HTTP Status:</span> {previewResult.http_status ?? 'N/A'}</p>
              <p><span className="font-semibold text-foreground">Content-Type:</span> {previewResult.content_type || 'N/A'}</p>
              {previewResult.error_message ? (
                <p><span className="font-semibold text-foreground">Error:</span> {previewResult.error_message}</p>
              ) : null}
              <p><span className="font-semibold text-foreground">Advice:</span> {previewResult.advice}</p>
            </div>
          ) : null}
        </Card>
      ) : null}

      <Card className="rounded-2xl border border-border/70 bg-white p-4">
        <h3 className="text-sm font-semibold text-foreground">Audit Log</h3>
        <div className="mt-3 space-y-2">
          {auditRows.map((row) => (
            <div key={row.key} className="rounded-xl border border-border/60 bg-muted/10 px-3 py-2 text-xs">
              <p className="font-medium text-foreground">{row.key}</p>
              <p className="text-muted-foreground">
                Last updated: {row.updatedAt ? new Date(row.updatedAt).toLocaleString() : 'Never'} • Editable: {row.editable ? 'Yes' : 'No'} • Public: {row.public ? 'Yes' : 'No'}
              </p>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
};
