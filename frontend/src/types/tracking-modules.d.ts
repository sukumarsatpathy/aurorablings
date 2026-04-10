declare module './pages/admin/TrackingSettings' {
  import type { ComponentType } from 'react';
  const TrackingSettings: ComponentType;
  export default TrackingSettings;
}

declare module './services/trackingLoader' {
  interface TrackingConfigShape {
    gtm_id?: string;
    meta_pixel_id?: string;
    ga4_id?: string;
    google_ads_id?: string;
    clarity_id?: string;
    enabled?: {
      gtm?: boolean;
      meta?: boolean;
      ga4?: boolean;
      google_ads?: boolean;
      clarity?: boolean;
    };
    last_updated?: string | null;
  }

  interface TrackingLoaderResult {
    loaded: string[];
    skipped: string[];
  }

  const trackingLoader: {
    init: (config: TrackingConfigShape) => TrackingLoaderResult;
    testTracking: (provider: string) => unknown;
    loadGTM: (gtmId: string) => boolean;
    loadMetaPixel: (pixelId: string) => boolean;
    loadGA4: (gaId: string) => boolean;
    loadGoogleAds: (adsId: string) => boolean;
    loadClarity: (clarityId: string) => boolean;
  };

  export const init: (config: TrackingConfigShape) => TrackingLoaderResult;
  export const testTracking: (provider: string) => unknown;
  export const loadGTM: (gtmId: string) => boolean;
  export const loadMetaPixel: (pixelId: string) => boolean;
  export const loadGA4: (gaId: string) => boolean;
  export const loadGoogleAds: (adsId: string) => boolean;
  export const loadClarity: (clarityId: string) => boolean;
  export default trackingLoader;
}

declare module './services/trackingApi' {
  interface TrackingConfigShape {
    gtm_id?: string;
    meta_pixel_id?: string;
    ga4_id?: string;
    google_ads_id?: string;
    clarity_id?: string;
    enabled?: {
      gtm?: boolean;
      meta?: boolean;
      ga4?: boolean;
      google_ads?: boolean;
      clarity?: boolean;
    };
    last_updated?: string | null;
  }

  const trackingApi: {
    getTrackingConfig: () => Promise<TrackingConfigShape>;
    saveTrackingConfig: (config: TrackingConfigShape) => Promise<TrackingConfigShape>;
  };

  export const getTrackingConfig: () => Promise<TrackingConfigShape>;
  export const saveTrackingConfig: (config: TrackingConfigShape) => Promise<TrackingConfigShape>;
  export default trackingApi;
}
