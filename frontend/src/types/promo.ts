export type PromoBannerPosition =
  | 'top-left'
  | 'top-right'
  | 'bottom-left'
  | 'bottom-right'
  | 'dual-banner-left'
  | 'dual-banner-right';

export interface PromoBanner {
  id: string;
  position?: PromoBannerPosition | string;
  title?: string;
  subtitle?: string;
  badge_bold?: string;
  badge_text?: string;
  cta_label?: string;
  cta_url?: string;
  image?: string | null;
  bg_color?: string;
  shape_color?: string;
  is_active?: boolean;
}
