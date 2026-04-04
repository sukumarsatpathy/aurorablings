export interface TrackingConfigShape {
  gtm_id?: string;
  meta_pixel_id?: string;
  ga4_id?: string;
  clarity_id?: string;
  enabled?: {
    gtm?: boolean;
    meta?: boolean;
    ga4?: boolean;
    clarity?: boolean;
  };
  last_updated?: string | null;
}

export function getTrackingConfig(): Promise<TrackingConfigShape>;
export function saveTrackingConfig(config: TrackingConfigShape): Promise<TrackingConfigShape>;
export function getGTMConfig(): Promise<{
  gtm_container_id: string;
  is_gtm_enabled: boolean;
  last_updated?: string | null;
}>;
export function getPublicGTMConfig(): Promise<{
  gtm_container_id: string;
  is_gtm_enabled: boolean;
  last_updated?: string | null;
}>;
export function saveGTMConfig(config: {
  gtm_container_id: string;
  is_gtm_enabled: boolean;
}): Promise<{
  gtm_container_id: string;
  is_gtm_enabled: boolean;
  last_updated?: string | null;
}>;

declare const trackingApi: {
  getTrackingConfig: typeof getTrackingConfig;
  saveTrackingConfig: typeof saveTrackingConfig;
  getGTMConfig: typeof getGTMConfig;
  getPublicGTMConfig: typeof getPublicGTMConfig;
  saveGTMConfig: typeof saveGTMConfig;
};

export default trackingApi;
