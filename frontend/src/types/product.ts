export interface ProductVariant {
  id: string;
  sku: string;
  name: string;
  price: string;
  compare_at_price: string | null;
  offer_price: string | null;
  offer_starts_at: string | null;
  offer_ends_at: string | null;
  offer_label: string;
  offer_is_active: boolean;
  has_active_offer: boolean;
  effective_price: string;
  display_compare_at_price: string | null;
  stock_quantity: number;
  is_active: boolean;
  is_default: boolean;
  discount_percentage: number | null;
  is_in_stock: boolean;
  is_low_stock: boolean;
}

export interface DealProduct {
  id: string;
  name: string;
  slug: string;
  short_description: string;
  category_name: string;
  brand_name: string | null;
  is_featured: boolean;
  rating: string;
  primary_image: string | null;
  hover_image: string | null;
  price_range: {
    min: string | null;
    max: string | null;
  };
  default_variant: {
    id: string;
    sku: string;
    price: string;
    stock_quantity: number;
  } | null;
  variants: ProductVariant[];
  total_stock: number;
}
