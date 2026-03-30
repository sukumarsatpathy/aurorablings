import apiClient from './client';

export interface NotifySubscriptionPayload {
  product_id: string;
  name?: string;
  email?: string;
  phone?: string;
}

export interface ContactQueryItem {
  id: string;
  name: string;
  email: string;
  phone: string;
  subject: string;
  message: string;
  status: 'new' | 'read' | 'resolved';
  is_read: boolean;
  source: string;
  created_at: string;
  updated_at: string;
  read_at: string | null;
}

const notifyService = {
  subscribe: async (payload: NotifySubscriptionPayload) => {
    const response = await apiClient.post('/v1/notify/', payload);
    return response.data;
  },

  listAdmin: async (params?: {
    search?: string;
    product_id?: string;
    is_notified?: 'true' | 'false';
    date_from?: string;
    date_to?: string;
  }) => {
    const response = await apiClient.get('/v1/notifications/admin/notify-subscriptions/', { params });
    return response.data;
  },

  markNotified: async (ids: string[]) => {
    const response = await apiClient.post('/v1/notifications/admin/notify-subscriptions/mark-notified/', { ids });
    return response.data;
  },

  markAllNotified: async (payload?: { product_id?: string }) => {
    const response = await apiClient.post('/v1/notifications/admin/notify-subscriptions/mark-all-notified/', payload || {});
    return response.data;
  },

  exportAdminCsv: async () => {
    const response = await apiClient.get('/v1/notifications/admin/notify-subscriptions/export/', {
      responseType: 'blob',
    });
    return response.data as Blob;
  },

  listContactQueries: async (params?: {
    search?: string;
    status?: 'new' | 'read' | 'resolved';
    is_read?: 'true' | 'false';
    date_from?: string;
    date_to?: string;
  }) => {
    const response = await apiClient.get('/v1/notifications/admin/contact-queries/', { params });
    return response.data as { data?: ContactQueryItem[] };
  },

  markContactQueriesRead: async (ids: string[]) => {
    const response = await apiClient.post('/v1/notifications/admin/contact-queries/mark-read/', { ids });
    return response.data;
  },
};

export default notifyService;
