import React, { useMemo, useRef, useState } from 'react';
import { Card } from '@/components/ui/Card';
import { Input } from '@/components/ui/Input';
import { Button } from '@/components/ui/Button';
import settingsService from '@/services/api/settings';
import type { AppSetting } from '@/types/setting';
import { categoryMenuToSettingCategory } from './helpers';
import { PaymentSettings } from './PaymentSettings';
import type { SettingsCategoryMenu } from './types';
import GTMCard from '@/components/tracking/GTMCard';
import TrackingCard from '@/components/tracking/TrackingCard';
import useGTMConfig from '@/hooks/useGTMConfig';
import useTrackingConfig from '@/hooks/useTrackingConfig';
import { sanitizeTrackingValue, validateTrackingValue } from '@/utils/validators';

const SECRET_SETTING_KEYS = new Set(['turnstile_secret_key']);
const TRACKING_PROVIDER_META = {
  pixel_settings: {
    key: 'meta',
    title: 'Pixel Settings',
    description: 'Meta conversion and audience tracking for campaigns.',
    fieldName: 'meta_pixel_id',
    placeholder: '123456789012345',
  },
  analytics_settings: {
    key: 'ga4',
    title: 'Analytics Settings',
    description: 'Google Analytics (GA4) event and page-view tracking.',
    fieldName: 'ga4_id',
    placeholder: 'G-XXXXXXXXXX',
  },
  google_ads_settings: {
    key: 'google_ads',
    title: 'Google Ads Settings',
    description: 'Google Ads conversion tracking using Google tag (gtag.js).',
    fieldName: 'google_ads_id',
    placeholder: 'AW-1234567890',
  },
  clarity_settings: {
    key: 'clarity',
    title: 'Clarity Settings',
    description: 'Microsoft Clarity session replay and heatmap tracking.',
    fieldName: 'clarity_id',
    placeholder: 'abcd12xy',
  },
} as const;

interface Props {
  category: SettingsCategoryMenu;
  settings: AppSetting[];
  canEdit: boolean;
  onRefresh: () => Promise<void>;
  onToast: (variant: 'success' | 'error' | 'info', message: string) => void;
}

const EmbeddedGTMSettings: React.FC<Pick<Props, 'canEdit' | 'onToast'>> = ({ canEdit, onToast }) => {
  const { config, loading, saving, validation, setEnabled, setGtmId, saveConfig, runTest } = useGTMConfig();

  const status = useMemo(() => {
    if (!config.gtm_container_id) return 'Not Configured';
    if (!validation.isValid) return 'Invalid';
    if (config.is_gtm_enabled) return 'Active';
    return 'Disabled';
  }, [config.gtm_container_id, config.is_gtm_enabled, validation.isValid]);

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-lg font-semibold text-foreground">GTM Settings</h2>
        <p className="text-xs text-muted-foreground">Manage Google Tag Manager container and runtime injection.</p>
      </div>
      <GTMCard
        enabled={config.is_gtm_enabled}
        gtmId={config.gtm_container_id}
        validationMessage={config.is_gtm_enabled && !validation.isValid ? validation.error : ''}
        status={status}
        loading={loading || !canEdit}
        saving={saving}
        canSave={canEdit && (!config.is_gtm_enabled || validation.isValid)}
        onToggle={(checked: boolean) => {
          if (!canEdit) return;
          setEnabled(checked);
        }}
        onIdChange={(value: string) => {
          if (!canEdit) return;
          setGtmId(value);
        }}
        onSave={async () => {
          if (!canEdit) {
            onToast('info', 'Read-only mode. You cannot edit settings.');
            return;
          }
          const result = await saveConfig();
          onToast(result.ok ? 'success' : 'error', result.message);
        }}
        onTest={() => {
          const result = runTest();
          onToast(result.ok ? 'success' : 'error', result.message);
        }}
      />
    </div>
  );
};

const EmbeddedTrackingProviderSettings: React.FC<
  Pick<Props, 'canEdit' | 'onToast'> &
    { category: 'pixel_settings' | 'analytics_settings' | 'google_ads_settings' | 'clarity_settings' }
> = ({ category, canEdit, onToast }) => {
  const provider = TRACKING_PROVIDER_META[category];
  const { config, loading, saving, errorsByField, updateId, updateEnabled, saveConfig, testProvider } = useTrackingConfig();
  const trackingConfig = (config || {}) as any;
  const trackingErrors = (errorsByField || {}) as Record<string, string>;

  const currentValue = String(trackingConfig[provider.fieldName] || '');
  const fieldError = trackingErrors[provider.fieldName];
  const formatValidation = validateTrackingValue(provider.key, currentValue);
  const showLiveError =
    Boolean(trackingConfig.enabled?.[provider.key]) && currentValue && !formatValidation.isValid
      ? formatValidation.error
      : '';

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-lg font-semibold text-foreground">{provider.title}</h2>
        <p className="text-xs text-muted-foreground">{provider.description}</p>
      </div>
      <TrackingCard
        providerKey={provider.key}
        title={provider.title}
        description={provider.description}
        enabled={Boolean(trackingConfig.enabled?.[provider.key])}
        idValue={currentValue}
        placeholder={provider.placeholder}
        fieldName={provider.fieldName}
        error={fieldError || showLiveError}
        loading={loading || !canEdit}
        saving={saving}
        onToggle={(checked: boolean) => {
          if (!canEdit) return;
          updateEnabled(provider.key, checked);
        }}
        onIdChange={(fieldName: string, value: string) => {
          if (!canEdit) return;
          updateId(fieldName, sanitizeTrackingValue(provider.key, value));
        }}
        onSave={async () => {
          if (!canEdit) {
            onToast('info', 'Read-only mode. You cannot edit settings.');
            return;
          }
          const result = await saveConfig();
          onToast(result.ok ? 'success' : 'error', result.message);
        }}
        onTest={() => {
          const result = testProvider(provider.key);
          onToast(result.ok ? 'success' : 'error', result.message);
        }}
      />
    </div>
  );
};

export const SettingsContent: React.FC<Props> = ({
  category,
  settings,
  canEdit,
  onRefresh,
  onToast,
}) => {
  if (category === 'gtm_settings') {
    return <EmbeddedGTMSettings canEdit={canEdit} onToast={onToast} />;
  }

  if (
    category === 'pixel_settings' ||
    category === 'analytics_settings' ||
    category === 'google_ads_settings' ||
    category === 'clarity_settings'
  ) {
    return <EmbeddedTrackingProviderSettings category={category} canEdit={canEdit} onToast={onToast} />;
  }

  const settingCategory = categoryMenuToSettingCategory(category);
  const categorySettings = useMemo(
    () => settings.filter((s) => s.category === settingCategory),
    [settings, settingCategory]
  );
  const [quickValues, setQuickValues] = useState<Record<string, string>>({});
  const [savingKey, setSavingKey] = useState('');
  const [uploadingKey, setUploadingKey] = useState('');
  const fileInputRefs = useRef<Record<string, HTMLInputElement | null>>({});

  const isBrandingAssetSetting = (settingKey: string) =>
    settingKey === 'branding_logo_url' || settingKey === 'branding_favicon_url';

  const getBackendOrigin = (): string => {
    const baseURL = String(import.meta.env.VITE_API_BASE_URL || '').trim();
    const explicitBackendOrigin = String(import.meta.env.VITE_BACKEND_ORIGIN || '').trim();

    if (explicitBackendOrigin) {
      try {
        return new URL(explicitBackendOrigin).origin;
      } catch {
        // ignore invalid env and continue fallback
      }
    }

    try {
      if (baseURL) {
        const parsed = new URL(baseURL, window.location.origin);
        if (/^https?:$/i.test(parsed.protocol) && parsed.origin !== window.location.origin) {
          return parsed.origin;
        }
      }
    } catch {
      // ignore and fallback
    }

    if (['localhost', '127.0.0.1'].includes(window.location.hostname)) {
      return `${window.location.protocol}//${window.location.hostname}:8000`;
    }

    return window.location.origin;
  };

  const toPreviewUrl = (raw: string): string => {
    const value = String(raw || '').trim();
    if (!value) return '';
    if (/^https?:\/\//i.test(value)) return value;
    const backendOrigin = getBackendOrigin();
    return value.startsWith('/') ? `${backendOrigin}${value}` : `${backendOrigin}/${value}`;
  };

  const saveQuick = async (setting: AppSetting) => {
    const nextValue = quickValues[setting.key] ?? setting.value;
    try {
      setSavingKey(setting.key);
      await settingsService.update(setting.key, {
        key: setting.key,
        value: nextValue,
        value_type: setting.value_type,
        category: setting.category,
        label: setting.label,
        description: setting.description,
        is_public: setting.is_public,
        is_editable: setting.is_editable,
      });
      onToast('success', `${setting.label || setting.key} updated.`);
      await onRefresh();
    } catch (error: any) {
      onToast('error', error?.response?.data?.message || 'Failed to update setting.');
    } finally {
      setSavingKey('');
    }
  };

  const uploadBrandingAsset = async (setting: AppSetting, file: File) => {
    try {
      setUploadingKey(setting.key);
      const response = await settingsService.uploadAsset(file, setting.key);
      const payload = response?.data || response || {};
      const uploadedUrl = String(payload.url || payload.absolute_url || '').trim();
      if (!uploadedUrl) {
        onToast('error', 'Upload succeeded but URL was not returned.');
        return;
      }
      setQuickValues((prev) => ({ ...prev, [setting.key]: uploadedUrl }));
      await settingsService.update(setting.key, {
        key: setting.key,
        value: uploadedUrl,
        value_type: setting.value_type,
        category: setting.category,
        label: setting.label,
        description: setting.description,
        is_public: setting.is_public,
        is_editable: setting.is_editable,
      });
      onToast('success', `${setting.label || setting.key} uploaded and saved.`);
      await onRefresh();
    } catch (error: any) {
      onToast('error', error?.response?.data?.message || 'Failed to upload branding asset.');
    } finally {
      setUploadingKey('');
    }
  };

  if (category === 'payment' || category === 'notification' || category === 'shipping') {
    return (
      <PaymentSettings
        title={category === 'payment' ? 'Payment Settings' : `${category[0].toUpperCase()}${category.slice(1)} Settings`}
        category={settingCategory}
        settings={settings}
        canEdit={canEdit}
        onRefresh={onRefresh}
        onToast={onToast}
      />
    );
  }

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-lg font-semibold text-foreground">
          {category[0].toUpperCase() + category.slice(1)} Settings
        </h2>
        <p className="text-xs text-muted-foreground">Quick-edit standard settings for this category.</p>
      </div>

      {categorySettings.length === 0 ? (
        <Card className="rounded-2xl border border-border/70 bg-white p-5 text-sm text-muted-foreground">
          No settings found in this category.
        </Card>
      ) : (
        <div className="space-y-3">
          {categorySettings.map((setting) => {
            const disabled = !canEdit || !setting.is_editable;
            const isSecret = SECRET_SETTING_KEYS.has(setting.key);
            const inputValue = quickValues[setting.key] ?? setting.value;
            return (
              <Card key={setting.id} className="rounded-2xl border border-border/70 bg-white p-4">
                <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
                  <div className="w-full space-y-1">
                    <p className="text-sm font-semibold text-foreground">{setting.label || setting.key}</p>
                    <p className="text-xs text-muted-foreground">{setting.key}</p>
                    <Input
                      type={isSecret ? 'password' : 'text'}
                      value={inputValue}
                      autoComplete={isSecret ? 'off' : undefined}
                      disabled={disabled}
                      onChange={(e) => setQuickValues((prev) => ({ ...prev, [setting.key]: e.target.value }))}
                    />
                    {category === 'branding' && isBrandingAssetSetting(setting.key) ? (
                      <div className="pt-1 space-y-2">
                        {inputValue ? (
                          <div className="rounded-lg border border-border/60 bg-muted/10 p-2 inline-flex items-center gap-3">
                            <img
                              src={toPreviewUrl(inputValue)}
                              alt={setting.key === 'branding_favicon_url' ? 'Favicon Preview' : 'Logo Preview'}
                              className={
                                setting.key === 'branding_favicon_url'
                                  ? 'h-8 w-8 rounded object-contain bg-white border border-border/50'
                                  : 'h-10 w-24 rounded object-contain bg-white border border-border/50'
                              }
                              onError={(event) => {
                                const img = event.currentTarget as HTMLImageElement;
                                img.style.display = 'none';
                              }}
                            />
                            <a
                              href={toPreviewUrl(inputValue)}
                              target="_blank"
                              rel="noreferrer"
                              className="text-xs text-primary hover:underline break-all"
                            >
                              Open image
                            </a>
                          </div>
                        ) : null}
                        <div className="flex items-center gap-2">
                        <input
                          ref={(node) => {
                            fileInputRefs.current[setting.key] = node;
                          }}
                          type="file"
                          accept="image/png,image/jpeg,image/webp"
                          className="hidden"
                          onChange={(event) => {
                            const file = event.target.files?.[0];
                            if (file) {
                              void uploadBrandingAsset(setting, file);
                            }
                            event.currentTarget.value = '';
                          }}
                        />
                        <Button
                          type="button"
                          variant="outline"
                          disabled={disabled || uploadingKey === setting.key}
                          onClick={() => fileInputRefs.current[setting.key]?.click()}
                        >
                          {uploadingKey === setting.key
                            ? 'Uploading...'
                            : setting.key === 'branding_favicon_url'
                              ? 'Upload Favicon'
                              : 'Upload Logo'}
                        </Button>
                        </div>
                      </div>
                    ) : null}
                  </div>
                  <Button
                    className="md:ml-4"
                    disabled={disabled || savingKey === setting.key || uploadingKey === setting.key}
                    onClick={() => saveQuick(setting)}
                  >
                    {savingKey === setting.key ? 'Saving...' : 'Save'}
                  </Button>
                </div>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
};
