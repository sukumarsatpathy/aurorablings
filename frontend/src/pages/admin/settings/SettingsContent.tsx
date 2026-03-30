import React, { useMemo, useState } from 'react';
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
                  </div>
                  <Button
                    className="md:ml-4"
                    disabled={disabled || savingKey === setting.key}
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
