export interface TrackingConfigShape {
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

export interface TrackingLoaderResult {
  loaded: string[];
  skipped: string[];
}

export function init(config: TrackingConfigShape): TrackingLoaderResult;
export function testTracking(provider: string): unknown;
export function initGTMConfig(config: { gtm_container_id?: string; is_gtm_enabled?: boolean }): { loaded: boolean };
export function testGTMEvent(): unknown;
export function loadGTM(gtmId: string): boolean;
export function loadMetaPixel(pixelId: string): boolean;
export function loadGA4(gaId: string): boolean;
export function loadGoogleAds(adsId: string): boolean;
export function loadClarity(clarityId: string): boolean;

declare const trackingLoader: {
  init: typeof init;
  testTracking: typeof testTracking;
  initGTMConfig: typeof initGTMConfig;
  testGTMEvent: typeof testGTMEvent;
  loadGTM: typeof loadGTM;
  loadMetaPixel: typeof loadMetaPixel;
  loadGA4: typeof loadGA4;
  loadGoogleAds: typeof loadGoogleAds;
  loadClarity: typeof loadClarity;
};

export default trackingLoader;
