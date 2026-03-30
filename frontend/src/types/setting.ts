export type SettingCategory =
  | 'general'
  | 'branding'
  | 'payment'
  | 'notification'
  | 'shipping'
  | 'inventory'
  | 'returns'
  | 'seo'
  | 'advanced';

export type SettingValueType = 'string' | 'integer' | 'int' | 'float' | 'boolean' | 'json' | 'text';

export interface AppSetting {
  id: string;
  key: string;
  value: string;
  typed_value: string | number | boolean | Record<string, unknown> | unknown[] | null;
  value_type: SettingValueType;
  category: SettingCategory;
  label: string;
  description: string;
  is_public: boolean;
  is_editable: boolean;
  updated_at: string;
}

export interface AppSettingWriteData {
  key: string;
  value: string;
  value_type: SettingValueType;
  category: SettingCategory;
  label: string;
  description: string;
  is_public: boolean;
  is_editable: boolean;
}
