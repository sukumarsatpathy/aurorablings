const SAFE_TEXT_REGEX = /[^a-zA-Z0-9_\-]/g;
const DIGITS_ONLY_REGEX = /[^0-9]/g;

const TRACKING_PATTERNS = {
  gtm: /^GTM-[A-Z0-9]+$/i,
  ga4: /^G-[A-Z0-9]+$/i,
  google_ads: /^AW-[0-9]+$/i,
  meta: /^[0-9]{5,20}$/,
  clarity: /^[a-zA-Z0-9][a-zA-Z0-9_-]{3,39}$/,
};

const FIELD_BY_PROVIDER = {
  gtm: 'gtm_id',
  ga4: 'ga4_id',
  google_ads: 'google_ads_id',
  meta: 'meta_pixel_id',
  clarity: 'clarity_id',
};

export const normalizeProvider = (provider) => String(provider || '').trim().toLowerCase();

export const GTM_REGEX = /^GTM-[A-Z0-9]+$/;

export const sanitizeGTMContainerId = (value) =>
  String(value ?? '')
    .trim()
    .toUpperCase()
    .replace(/[^A-Z0-9-]/g, '');

export const validateGTMContainerId = (value) => {
  const sanitized = sanitizeGTMContainerId(value);
  if (!sanitized) {
    return { isValid: false, sanitized, error: 'GTM Container ID is required when GTM is enabled.' };
  }
  if (!GTM_REGEX.test(sanitized)) {
    return { isValid: false, sanitized, error: 'Invalid GTM format. Expected: GTM-XXXX.' };
  }
  return { isValid: true, sanitized, error: '' };
};

export const sanitizeTrackingValue = (provider, value) => {
  const normalizedProvider = normalizeProvider(provider);
  const raw = String(value ?? '').trim();

  if (!raw) return '';

  if (normalizedProvider === 'meta') {
    return raw.replace(DIGITS_ONLY_REGEX, '');
  }

  return raw.replace(SAFE_TEXT_REGEX, '').toUpperCase();
};

export const validateTrackingValue = (provider, value) => {
  const normalizedProvider = normalizeProvider(provider);
  const sanitized = sanitizeTrackingValue(normalizedProvider, value);
  const pattern = TRACKING_PATTERNS[normalizedProvider];

  if (!pattern) {
    return { isValid: false, sanitized, error: 'Unsupported tracking provider.' };
  }

  if (!sanitized) {
    return { isValid: false, sanitized, error: 'Tracking ID is required when enabled.' };
  }

  if (!pattern.test(sanitized)) {
    const hints = {
      gtm: 'GTM ID must start with GTM- (example: GTM-ABC123).',
      ga4: 'GA4 ID must start with G- (example: G-ABC123XYZ).',
      google_ads: 'Google Ads ID must start with AW- (example: AW-1234567890).',
      meta: 'Meta Pixel ID must be numeric.',
      clarity: 'Clarity ID must contain letters/numbers and may include _ or -.',
    };
    return { isValid: false, sanitized, error: hints[normalizedProvider] || 'Invalid tracking ID format.' };
  }

  return { isValid: true, sanitized, error: '' };
};

export const sanitizeTrackingConfig = (config) => {
  const safeConfig = {
    gtm_id: sanitizeTrackingValue('gtm', config?.gtm_id),
    meta_pixel_id: sanitizeTrackingValue('meta', config?.meta_pixel_id),
    ga4_id: sanitizeTrackingValue('ga4', config?.ga4_id),
    google_ads_id: sanitizeTrackingValue('google_ads', config?.google_ads_id),
    clarity_id: sanitizeTrackingValue('clarity', config?.clarity_id),
    enabled: {
      gtm: Boolean(config?.enabled?.gtm),
      meta: Boolean(config?.enabled?.meta),
      ga4: Boolean(config?.enabled?.ga4),
      google_ads: Boolean(config?.enabled?.google_ads),
      clarity: Boolean(config?.enabled?.clarity),
    },
    last_updated: config?.last_updated || config?.updated_at || null,
  };

  return safeConfig;
};

export const validateTrackingConfig = (config) => {
  const sanitized = sanitizeTrackingConfig(config);
  const errors = {};

  Object.entries(sanitized.enabled).forEach(([provider, isEnabled]) => {
    if (!isEnabled) return;
    const field = FIELD_BY_PROVIDER[provider];
    const result = validateTrackingValue(provider, sanitized[field]);
    if (!result.isValid) {
      errors[field] = result.error;
    }
  });

  return {
    isValid: Object.keys(errors).length === 0,
    errors,
    sanitized,
  };
};
