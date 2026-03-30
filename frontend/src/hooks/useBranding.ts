import { useQuery } from '@tanstack/react-query';
import settingsService from '@/services/api/settings';

export interface BrandingConfig {
  siteTitle: string;
  tagline: string;
  tabTitle: string;
  brandName: string;
  logoUrl: string;
  faviconUrl: string;
  footerText: string;
}

const DEFAULT_BRANDING: BrandingConfig = {
  siteTitle: 'Aurora Blings',
  tagline: '',
  tabTitle: 'Aurora Blings',
  brandName: 'Aurora Blings',
  logoUrl: '',
  faviconUrl: '',
  footerText: '',
};

const toStringValue = (value: unknown): string => {
  if (value === null || value === undefined) return '';
  return String(value).trim();
};

const firstValue = (source: Record<string, unknown>, keys: string[]): string => {
  for (const key of keys) {
    const value = toStringValue(source[key]);
    if (value) return value;
  }
  return '';
};

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

const toAssetUrl = (raw: string): string => {
  if (!raw) return '';
  if (/^https?:\/\//i.test(raw)) return raw;
  const backendOrigin = getBackendOrigin();
  if (raw.startsWith('/')) return `${backendOrigin}${raw}`;
  return `${backendOrigin}/${raw}`;
};

const buildBranding = (settings: Record<string, unknown>): BrandingConfig => {
  const brandName = firstValue(settings, [
    'brand_name',
    'site_name',
    'site_title',
    'aurora_blings',
  ]) || DEFAULT_BRANDING.brandName;

  const siteTitle = firstValue(settings, ['site_title', 'brand_title', 'brand_name']) || brandName;
  const tagline = firstValue(settings, [
    'branding_tagline',
    'site_tagline',
    'tagline',
    'brand_tagline',
    'meta_tagline',
    'seo_tagline',
  ]) || DEFAULT_BRANDING.tagline;
  const normalizedSiteTitle = siteTitle || DEFAULT_BRANDING.siteTitle;
  const hasTaglineInTitle =
    tagline &&
    normalizedSiteTitle.toLowerCase().includes(tagline.toLowerCase());
  const tabTitle = tagline && !hasTaglineInTitle
    ? `${normalizedSiteTitle} | ${tagline}`
    : normalizedSiteTitle;

  const logoUrl = toAssetUrl(
    firstValue(settings, ['branding_logo_url', 'site_logo', 'brand_logo', 'logo', 'header_logo'])
  );
  const faviconUrl = toAssetUrl(
    firstValue(settings, [
      'branding_favicon_url',
      'site_favicon',
      'site_favicon_url',
      'favicon',
      'brand_favicon',
      'favicon_url',
      'site_icon',
      'brand_icon',
    ])
  );
  const footerText = firstValue(settings, ['footer_text', 'footer_copy', 'footer']);

  return {
    siteTitle: normalizedSiteTitle,
    tagline,
    tabTitle,
    brandName,
    logoUrl,
    faviconUrl,
    footerText,
  };
};

export const useBranding = (): BrandingConfig => {
  const { data } = useQuery({
    queryKey: ['public-branding-settings'],
    queryFn: async () => {
      const response = await settingsService.getPublic();
      if (response && typeof response === 'object') {
        const envelopeData = (response as any).data;
        if (envelopeData && typeof envelopeData === 'object' && !Array.isArray(envelopeData)) {
          return envelopeData as Record<string, unknown>;
        }
        return response as Record<string, unknown>;
      }
      return {} as Record<string, unknown>;
    },
    staleTime: 1000 * 60 * 5,
  });

  if (!data || typeof data !== 'object') {
    return DEFAULT_BRANDING;
  }

  return buildBranding(data);
};
