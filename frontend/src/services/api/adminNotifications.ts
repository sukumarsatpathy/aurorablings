import apiClient from './client';

export interface NotificationDashboardStats {
  total_sent: number;
  total_failed: number;
  total_pending: number;
  success_rate: number;
  channel_breakdown: Array<{ channel: string; count: number }>;
  provider_breakdown: Array<{ provider: string; count: number }>;
  top_notification_types: Array<{ notification_type: string; count: number }>;
  daily_counts: Array<{ day: string; total: number; sent: number; failed: number }>;
  recent_failures: Array<{
    id: string;
    recipient: string;
    subject: string;
    provider: string;
    error_message: string;
    created_at: string;
  }>;
}

export interface NotificationLogListItem {
  id: string;
  created_at: string;
  channel: string;
  notification_type: string;
  recipient: string;
  subject: string;
  provider: string;
  status: string;
  attempts_count: number;
  error_message: string;
}

export interface NotificationLogDetail extends NotificationLogListItem {
  provider_message_id: string;
  template_name: string;
  rendered_context_json: Record<string, any>;
  rendered_html_snapshot: string;
  plain_text_snapshot: string;
  error_code: string;
  last_attempt_at: string | null;
  sent_at: string | null;
  created_by: string | null;
  related_object_type: string;
  related_object_id: string;
  notification: string | null;
  raw_response: Record<string, any>;
}

export interface NotificationProviderStatus {
  id: number;
  provider_type: string;
  is_active: boolean;
  last_tested_at: string | null;
  last_test_status: string;
  last_test_message: string;
}

export interface NotificationEmailPreviewTest {
  logo_url: string;
  is_public_host: boolean;
  reachable: boolean;
  http_status: number | null;
  content_type: string;
  error_message: string;
  advice: string;
}

const notificationsAdminService = {
  getDashboard: async (params?: { range?: string; date_from?: string; date_to?: string }) => {
    const response = await apiClient.get('/v1/admin/notifications/dashboard/', { params });
    return response.data;
  },

  getLogs: async (params?: {
    search?: string;
    status?: string;
    channel?: string;
    provider?: string;
    notification_type?: string;
    date_from?: string;
    date_to?: string;
    page?: number;
    page_size?: number;
  }) => {
    const response = await apiClient.get('/v1/admin/notifications/logs/', { params });
    return response.data;
  },

  getLogDetail: async (id: string) => {
    const response = await apiClient.get(`/v1/admin/notifications/logs/${id}/`);
    return response.data;
  },

  retryLog: async (id: string) => {
    const response = await apiClient.post(`/v1/admin/notifications/logs/${id}/retry/`);
    return response.data;
  },

  getProviderStatus: async () => {
    const response = await apiClient.get('/v1/admin/notifications/providers/status/');
    return response.data;
  },

  testProvider: async (id: number) => {
    const response = await apiClient.post(`/v1/admin/notifications/providers/${id}/test/`);
    return response.data;
  },

  testEmailPreviewUrl: async () => {
    const response = await apiClient.get('/v1/admin/notifications/email-preview/test/');
    return response.data;
  },

  getTemplateUsage: async () => {
    const response = await apiClient.get('/v1/admin/notifications/templates/usage/');
    return response.data;
  },
};

export default notificationsAdminService;
