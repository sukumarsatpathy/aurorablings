export type CouponType = 'percentage' | 'fixed';

export interface Coupon {
  id: string;
  code: string;
  type: CouponType;
  value: string;
  max_discount: string | null;
  min_order_value: string;
  usage_limit: number | null;
  per_user_limit: number | null;
  start_date: string;
  end_date: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface CouponWriteData {
  code: string;
  type: CouponType;
  value: number;
  max_discount?: number | null;
  min_order_value?: number;
  usage_limit?: number | null;
  per_user_limit?: number | null;
  start_date: string;
  end_date: string;
  is_active: boolean;
}
