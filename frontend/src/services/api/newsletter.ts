import apiClient from './client';

export interface NewsletterSubscriptionPayload {
  email: string;
  source?: string;
}

export interface NewsletterSubscriberItem {
  id: number;
  email: string;
  source: string;
  is_active: boolean;
  is_confirmed: boolean;
  status: string;
  subscribed_at: string;
  confirmed_at: string | null;
  unsubscribed_at: string | null;
  confirmation_email_sent_at: string | null;
  welcome_email_sent_at: string | null;
  updated_at: string;
}

const newsletterService = {
  subscribe: async (payload: NewsletterSubscriptionPayload) => {
    const response = await apiClient.post('/v1/notifications/newsletter/', payload);
    return response.data;
  },

  listSubscribers: async (params?: {
    search?: string;
    status?: 'confirmed' | 'pending' | 'unsubscribed';
    source?: string;
    date_from?: string;
    date_to?: string;
    page?: number;
    page_size?: number;
  }) => {
    const response = await apiClient.get('/v1/admin/notifications/newsletter/subscribers/', { params });
    return response.data as {
      data?: {
        items?: NewsletterSubscriberItem[];
        pagination?: {
          page: number;
          page_size: number;
          total: number;
          total_pages: number;
        };
        summary?: {
          total: number;
          confirmed: number;
          pending: number;
          unsubscribed: number;
        };
      };
    };
  },

  exportSubscribers: async (
    format: 'pdf' | 'excel' | 'legacy',
    params?: {
      search?: string;
      status?: 'confirmed' | 'pending' | 'unsubscribed';
      source?: string;
      date_from?: string;
      date_to?: string;
    },
  ) => {
    const response = await apiClient.get('/v1/admin/notifications/newsletter/subscribers/export/', {
      params: {
        ...params,
        format,
      },
      responseType: 'blob',
    });
    return response.data as Blob;
  },
};

export default newsletterService;
