import React, { useMemo, useRef, useState } from 'react';
import { Card } from '@/components/ui/Card';
import { Input } from '@/components/ui/Input';
import { Button } from '@/components/ui/Button';
import settingsService from '@/services/api/settings';
import type { AppSetting } from '@/types/setting';
import { categoryMenuToSettingCategory } from './helpers';
import { PaymentSettings } from './PaymentSettings';
import type { SettingsCategoryMenu } from './types';

const SECRET_SETTING_KEYS = new Set(['turnstile_secret_key']);

interface Props {
  category: SettingsCategoryMenu;
  settings: AppSetting[];
  canEdit: boolean;
  onRefresh: () => Promise<void>;
  onToast: (variant: 'success' | 'error' | 'info', message: string) => void;
}

export const SettingsContent: React.FC<Props> = ({
  category,
  settings,
  canEdit,
  onRefresh,
  onToast,
}) => {
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
