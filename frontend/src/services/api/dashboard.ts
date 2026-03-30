import apiClient from './client';

export type DashboardRange = 'today' | 'yesterday' | 'day_before_yesterday' | 'last_month' | 'custom';

export interface DashboardQuery {
  range?: DashboardRange;
  date_from?: string;
  date_to?: string;
  tz_offset?: number;
}

export interface DashboardResponse {
  range: {
    label: string;
    date_from: string;
    date_to: string;
  };
  summary: {
    total_revenue: string;
    total_orders: number;
    shipping_orders: number;
    coupon_uses: number;
    low_stock_count: number;
    contact_queries: number;
    unread_contact_queries: number;
  };
  charts: {
    revenue: Array<{ date: string; value: number }>;
    orders: Array<{ date: string; value: number }>;
    coupons: Array<{ date: string; value: number }>;
  };
  recent_orders: Array<{ id: string; order_number: string; status: string; grand_total: string; created_at: string; user__email: string | null }>;
  recent_stock: Array<{ id: string; variant__sku: string; variant__product__name: string; warehouse__code: string; available: number; updated_at: string }>;
  shipping_orders: Array<{ id: string; order_number: string; status: string; tracking_number: string; shipping_carrier: string; updated_at: string; user__email: string | null }>;
  coupon_usage: Array<{ id: string; coupon__code: string; discount_amount: string; used_at: string; user__email: string | null; order__order_number: string | null }>;
  recent_contact_queries: Array<{
    id: string;
    name: string;
    email: string;
    phone: string;
    subject: string;
    status: 'new' | 'read' | 'resolved';
    is_read: boolean;
    created_at: string;
  }>;
  referral: {
    revenue: string;
    user_earning: string;
    referrer_earning: string;
    top_referrers: Array<{ id: string; email: string; revenue: string; earning: string }>;
  };
}

const dashboardService = {
  getAdminDashboard: async (params?: DashboardQuery) => {
    const response = await apiClient.get('/v1/admin/dashboard/', { params });
    return response.data;
  },
};

export default dashboardService;
