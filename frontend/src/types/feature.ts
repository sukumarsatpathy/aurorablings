export type FeatureTier = 'free' | 'basic' | 'premium' | 'enterprise';
export type FeatureCategory =
  | 'payment'
  | 'notification'
  | 'shipping'
  | 'catalog'
  | 'order'
  | 'analytics'
  | 'marketing'
  | 'security'
  | 'general';

export interface FeatureFlag {
  is_enabled: boolean;
  rollout_percentage: number;
  enabled_at: string | null;
  disabled_at: string | null;
  notes: string;
}

export interface Feature {
  id: string;
  code: string;
  name: string;
  description: string;
  category: FeatureCategory;
  tier: FeatureTier;
  requires_config: boolean;
  config_schema: Record<string, unknown>;
  is_available: boolean;
  flag?: FeatureFlag;
  is_enabled: boolean;
  created_at: string;
  updated_at: string;
}

export interface FeatureWriteData {
  code: string;
  name: string;
  description?: string;
  category: FeatureCategory;
  tier: FeatureTier;
  requires_config: boolean;
  config_schema: Record<string, unknown>;
  is_available: boolean;
}
