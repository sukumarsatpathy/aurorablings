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
  image_small?: string | null;
  image_medium?: string | null;
  image_large?: string | null;
  bg_color?: string;
  shape_color?: string;
  title_color?: string;
  subtitle_color?: string;
  badge_color?: string;
  cta_text_color?: string;
  cta_border_color?: string;
  title_x?: number;
  title_y?: number;
  subtitle_x?: number;
  subtitle_y?: number;
  cta_x?: number;
  cta_y?: number;
  badge_bold_x?: number;
  badge_bold_y?: number;
  badge_text_x?: number;
  badge_text_y?: number;
  is_active?: boolean;
}
