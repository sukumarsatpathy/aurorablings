import apiClient from './client';

export interface ActivityUserInfo {
  id: string;
  email: string;
  full_name: string;
  role: string;
}

export interface ActivityLogItem {
  id: string;
  user: ActivityUserInfo | null;
  actor_type: string;
  action: string;
  entity_type: string;
  entity_id: string | null;
  description: string;
  metadata: Record<string, unknown>;
  ip_address: string | null;
  request_id: string | null;
  path: string | null;
  method: string | null;
  created_at: string;
}

export interface ActivityLogQuery {
  page?: number;
  search?: string;
  user?: string;
  actor_type?: string;
  action?: string;
  entity_type?: string;
  date_from?: string;
  date_to?: string;
  ordering?: string;
}

const auditLogsService = {
  list: async (params?: ActivityLogQuery) => {
    const response = await apiClient.get('/v1/audit/logs/', { params });
    return response.data;
  },
};

export default auditLogsService;
