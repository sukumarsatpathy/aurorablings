import type { AppSetting, SettingCategory } from '@/types/setting';

export type SettingsCategoryMenu = 'general' | 'branding' | 'payment' | 'notification' | 'shipping' | 'advanced';

export type DynamicFieldType = 'text' | 'password' | 'select' | 'toggle';

export interface DynamicFieldOption {
  label: string;
  value: string;
}

export interface DynamicFieldSchema {
  type: DynamicFieldType;
  label: string;
  description?: string;
  required?: boolean;
  placeholder?: string;
  options?: DynamicFieldOption[];
  default?: string | number | boolean;
}

export interface DynamicFormSchema {
  title?: string;
  description?: string;
  fields: Record<string, DynamicFieldSchema>;
}

export interface PluginSettingBundle {
  pluginKey: string;
  title: string;
  category: SettingCategory;
  configKey: string;
  schemaKey: string;
  configSetting: AppSetting | null;
  schemaSetting: AppSetting | null;
  schema: DynamicFormSchema;
  value: Record<string, unknown>;
}

export interface SettingsToast {
  id: string;
  variant: 'success' | 'error' | 'info';
  message: string;
}
