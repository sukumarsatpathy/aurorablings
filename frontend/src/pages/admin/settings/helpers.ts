import type { AppSetting, AppSettingWriteData, SettingCategory, SettingValueType } from '@/types/setting';
import type { DynamicFormSchema, PluginSettingBundle, SettingsCategoryMenu } from './types';

const safeParseJson = (value: string | null | undefined): unknown => {
  if (!value || !value.trim()) return null;
  try {
    return JSON.parse(value);
  } catch {
    return null;
  }
};

const normalizeValueType = (valueType: SettingValueType): Exclude<SettingValueType, 'int'> => {
  if (valueType === 'int') return 'integer';
  return valueType;
};

const coerceValueToString = (value: unknown, valueType: SettingValueType): string => {
  const normalized = normalizeValueType(valueType);
  if (normalized === 'json') {
    return JSON.stringify(value ?? {});
  }
  if (normalized === 'boolean') {
    return value ? 'true' : 'false';
  }
  return String(value ?? '');
};

export const categoryMenuToSettingCategory = (category: SettingsCategoryMenu): SettingCategory => {
  return category;
};

export const getDefaultPluginSchema = (pluginKey: string): DynamicFormSchema => {
  const lower = pluginKey.toLowerCase();
  if (lower === 'cashfree') {
    return {
      title: 'Cashfree',
      description: 'Configure Cashfree payments',
      fields: {
        enabled: { type: 'toggle', label: 'Enabled', default: false },
        environment: {
          type: 'select',
          label: 'Environment',
          required: true,
          options: [
            { label: 'Sandbox', value: 'sandbox' },
            { label: 'Production', value: 'production' },
          ],
          default: 'sandbox',
        },
        app_id: { type: 'text', label: 'App ID', required: true, placeholder: 'CF_APP_ID' },
        secret_key: { type: 'password', label: 'Secret Key', required: true, placeholder: 'CF_SECRET_KEY' },
        webhook_secret: { type: 'password', label: 'Webhook Secret', required: false, placeholder: 'Webhook secret' },
      },
    };
  }
  if (lower === 'razorpay') {
    return {
      title: 'Razorpay',
      description: 'Configure Razorpay payments',
      fields: {
        enabled: { type: 'toggle', label: 'Enabled', default: false },
        key_id: { type: 'text', label: 'Key ID', required: true },
        key_secret: { type: 'password', label: 'Key Secret', required: true },
        webhook_secret: { type: 'password', label: 'Webhook Secret', required: false },
      },
    };
  }
  return {
    title: pluginKey.replace(/[_-]/g, ' ').replace(/\b\w/g, (m) => m.toUpperCase()),
    description: 'Plugin configuration',
    fields: {
      enabled: { type: 'toggle', label: 'Enabled', default: false },
    },
  };
};

const normalizeSchema = (rawSchema: unknown, fallbackPlugin: string): DynamicFormSchema => {
  if (!rawSchema || typeof rawSchema !== 'object') {
    return getDefaultPluginSchema(fallbackPlugin);
  }

  const schema = rawSchema as {
    title?: unknown;
    description?: unknown;
    fields?: Record<string, unknown>;
  };
  const fields = schema.fields;
  if (!fields || typeof fields !== 'object') {
    return getDefaultPluginSchema(fallbackPlugin);
  }

  const normalizedFields: DynamicFormSchema['fields'] = {};
  for (const [key, field] of Object.entries(fields)) {
    if (!field || typeof field !== 'object') continue;
    const f = field as Record<string, unknown>;
    const type = String(f.type || 'text') as DynamicFormSchema['fields'][string]['type'];
    if (!['text', 'password', 'select', 'toggle'].includes(type)) continue;
    const options = Array.isArray(f.options)
      ? (f.options
          .map((opt) => {
            if (!opt || typeof opt !== 'object') return null;
            const o = opt as Record<string, unknown>;
            const label = String(o.label || '');
            const value = String(o.value || '');
            if (!label || !value) return null;
            return { label, value };
          })
          .filter(Boolean) as Array<{ label: string; value: string }>)
      : undefined;
    normalizedFields[key] = {
      type,
      label: String(f.label || key),
      description: f.description ? String(f.description) : undefined,
      required: Boolean(f.required),
      placeholder: f.placeholder ? String(f.placeholder) : undefined,
      options,
      default: f.default as string | number | boolean | undefined,
    };
  }

  if (Object.keys(normalizedFields).length === 0) {
    return getDefaultPluginSchema(fallbackPlugin);
  }

  return {
      title: schema.title ? String(schema.title) : undefined,
      description: schema.description ? String(schema.description) : undefined,
    fields: normalizedFields,
  };
};

const buildDefaultValues = (schema: DynamicFormSchema): Record<string, unknown> => {
  const result: Record<string, unknown> = {};
  for (const [fieldKey, field] of Object.entries(schema.fields)) {
    if (typeof field.default !== 'undefined') {
      result[fieldKey] = field.default;
      continue;
    }
    if (field.type === 'toggle') {
      result[fieldKey] = false;
      continue;
    }
    if (field.type === 'select') {
      result[fieldKey] = field.options?.[0]?.value ?? '';
      continue;
    }
    result[fieldKey] = '';
  }
  return result;
};

const coerceFieldValue = (field: DynamicFormSchema['fields'][string], raw: unknown): unknown => {
  if (field.type === 'toggle') {
    if (typeof raw === 'boolean') return raw;
    if (typeof raw === 'string') {
      const v = raw.trim().toLowerCase();
      if (['true', '1', 'yes', 'on'].includes(v)) return true;
      if (['false', '0', 'no', 'off', ''].includes(v)) return false;
    }
    if (typeof raw === 'number') return raw !== 0;
    return Boolean(raw);
  }

  if (field.type === 'select' || field.type === 'text' || field.type === 'password') {
    return raw == null ? '' : String(raw);
  }

  return raw;
};

export const getBundlesForCategory = (
  allSettings: AppSetting[],
  category: SettingCategory,
  defaults: string[] = []
): PluginSettingBundle[] => {
  const settingsByKey = new Map(allSettings.map((s) => [s.key, s]));
  const prefix = `${category}.`;
  const pluginConfigKeys = new Set<string>();

  for (const s of allSettings) {
    if (s.category !== category) continue;
    if (!s.key.startsWith(prefix)) continue;
    if (s.key.endsWith('.schema')) continue;
    const parts = s.key.split('.');
    if (parts.length !== 2) continue;
    pluginConfigKeys.add(s.key);
  }

  for (const plugin of defaults) {
    pluginConfigKeys.add(`${category}.${plugin}`);
  }

  const bundles: PluginSettingBundle[] = [];
  for (const configKey of Array.from(pluginConfigKeys).sort()) {
    const pluginKey = configKey.slice(prefix.length);
    const schemaKey = `${configKey}.schema`;
    const configSetting = settingsByKey.get(configKey) ?? null;
    const schemaSetting = settingsByKey.get(schemaKey) ?? null;
    const schemaRaw = schemaSetting?.typed_value ?? safeParseJson(schemaSetting?.value);
    const schema = normalizeSchema(schemaRaw, pluginKey);
    const baseDefault = buildDefaultValues(schema);
    const configValue = (configSetting?.typed_value as Record<string, unknown> | null) || safeParseJson(configSetting?.value);
    const mergedValue = {
      ...baseDefault,
      ...(configValue && typeof configValue === 'object' ? configValue as Record<string, unknown> : {}),
    };
    const normalizedValue: Record<string, unknown> = { ...mergedValue };
    for (const [fieldKey, field] of Object.entries(schema.fields)) {
      normalizedValue[fieldKey] = coerceFieldValue(field, mergedValue[fieldKey]);
    }

    bundles.push({
      pluginKey,
      title: schema.title || pluginKey.replace(/[_-]/g, ' ').replace(/\b\w/g, (m) => m.toUpperCase()),
      category,
      configKey,
      schemaKey,
      configSetting,
      schemaSetting,
      schema,
      value: normalizedValue,
    });
  }
  return bundles;
};

export const makePayloadFromBundle = (
  bundle: PluginSettingBundle,
  value: Record<string, unknown>
): AppSettingWriteData => {
  return {
    key: bundle.configKey,
    value: coerceValueToString(value, 'json'),
    value_type: 'json',
    category: bundle.category,
    label: bundle.title,
    description: bundle.schema.description || `${bundle.title} configuration`,
    is_public: false,
    is_editable: true,
  };
};

export const validateBundleValues = (
  schema: DynamicFormSchema,
  values: Record<string, unknown>
): string[] => {
  const errors: string[] = [];
  for (const [key, field] of Object.entries(schema.fields)) {
    const value = values[key];
    if (field.required) {
      if (field.type === 'toggle') continue;
      const str = String(value ?? '').trim();
      if (!str) {
        errors.push(`${field.label} is required.`);
      }
    }
    if (field.type === 'select' && field.options && field.options.length > 0) {
      const selected = String(value ?? '');
      if (selected && !field.options.some((opt) => opt.value === selected)) {
        errors.push(`${field.label} has an invalid value.`);
      }
    }
  }
  return errors;
};

export const asSettingWriteData = (
  current: AppSetting,
  patch: Partial<AppSettingWriteData>
): AppSettingWriteData => {
  return {
    key: patch.key ?? current.key,
    value: patch.value ?? current.value,
    value_type: normalizeValueType(patch.value_type ?? current.value_type),
    category: patch.category ?? current.category,
    label: patch.label ?? current.label,
    description: patch.description ?? current.description,
    is_public: typeof patch.is_public === 'boolean' ? patch.is_public : current.is_public,
    is_editable: typeof patch.is_editable === 'boolean' ? patch.is_editable : current.is_editable,
  };
};
