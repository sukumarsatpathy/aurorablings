import apiClient from './client';

export interface ReturnItemRow {
  id: string;
  order_item: string;
  variant: string | null;
  quantity: number;
  reason_code: string;
  reason_detail?: string;
  condition?: string;
  unit_price: string;
  refund_amount: string;
  stock_reintegrated: boolean;
}

export interface ExchangeItemRow {
  id: string;
  order_item: string;
  original_variant: string | null;
  replacement_variant: string | null;
  quantity: number;
  reason_code: string;
  reason_detail?: string;
  condition?: string;
  price_difference: string;
  stock_reintegrated: boolean;
}

export interface ReturnRequestRow {
  id: string;
  return_number: string;
  order: string;
  order_number?: string;
  status: string;
  customer_name?: string;
  customer_email?: string;
  notes?: string;
  staff_notes?: string;
  rejection_reason?: string;
  created_at: string;
  items: ReturnItemRow[];
}

export interface ExchangeRequestRow {
  id: string;
  exchange_number: string;
  order: string;
  order_number?: string;
  status: string;
  customer_name?: string;
  customer_email?: string;
  notes?: string;
  staff_notes?: string;
  rejection_reason?: string;
  created_at: string;
  items: ExchangeItemRow[];
}

const returnsService = {
  listAdminReturns: async (params?: { status?: string; order_id?: string; refund_ready?: boolean }) => {
    const response = await apiClient.get('/v1/returns/admin/', { params });
    return response.data;
  },

  getAdminReturn: async (id: string) => {
    const response = await apiClient.get(`/v1/returns/admin/${id}/`);
    return response.data;
  },

  createAdminReturn: async (payload: {
    order_id: string;
    user_id?: string | null;
    notes?: string;
    pickup_address?: Record<string, string>;
    items: Array<{
      order_item_id: string;
      quantity: number;
      reason_code: string;
      reason_detail?: string;
      warehouse_id?: string | null;
    }>;
  }) => {
    const response = await apiClient.post('/v1/returns/admin/', payload);
    return response.data;
  },

  updateAdminReturn: async (id: string, payload: Partial<{
    notes: string;
    staff_notes: string;
    pickup_address: Record<string, string>;
    return_tracking_no: string;
    return_carrier: string;
  }>) => {
    const response = await apiClient.patch(`/v1/returns/admin/${id}/`, payload);
    return response.data;
  },

  deleteAdminReturn: async (id: string) => {
    const response = await apiClient.delete(`/v1/returns/admin/${id}/`);
    return response.data;
  },

  approveReturn: async (id: string, notes = '') => {
    const response = await apiClient.post(`/v1/returns/admin/${id}/approve/`, { notes });
    return response.data;
  },

  rejectReturn: async (id: string, reason: string) => {
    const response = await apiClient.post(`/v1/returns/admin/${id}/reject/`, { reason });
    return response.data;
  },

  listAdminExchanges: async (params?: { status?: string; order_id?: string }) => {
    const response = await apiClient.get('/v1/returns/exchanges/admin/', { params });
    return response.data;
  },

  getAdminExchange: async (id: string) => {
    const response = await apiClient.get(`/v1/returns/exchanges/admin/${id}/`);
    return response.data;
  },

  createAdminExchange: async (payload: {
    order_id: string;
    user_id?: string | null;
    notes?: string;
    shipping_address?: Record<string, string>;
    items: Array<{
      order_item_id: string;
      replacement_variant_id: string;
      quantity: number;
      reason_code: string;
      reason_detail?: string;
    }>;
  }) => {
    const response = await apiClient.post('/v1/returns/exchanges/admin/', payload);
    return response.data;
  },

  updateAdminExchange: async (id: string, payload: Partial<{
    notes: string;
    staff_notes: string;
    shipping_address: Record<string, string>;
    return_tracking_no: string;
    return_carrier: string;
    exchange_tracking_no: string;
    exchange_carrier: string;
  }>) => {
    const response = await apiClient.patch(`/v1/returns/exchanges/admin/${id}/`, payload);
    return response.data;
  },

  deleteAdminExchange: async (id: string) => {
    const response = await apiClient.delete(`/v1/returns/exchanges/admin/${id}/`);
    return response.data;
  },

  approveExchange: async (id: string, notes = '') => {
    const response = await apiClient.post(`/v1/returns/exchanges/admin/${id}/approve/`, { notes });
    return response.data;
  },

  rejectExchange: async (id: string, reason: string) => {
    const response = await apiClient.post(`/v1/returns/exchanges/admin/${id}/reject/`, { reason });
    return response.data;
  },
};

export default returnsService;
