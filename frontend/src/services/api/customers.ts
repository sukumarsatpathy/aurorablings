import apiClient from './client';
import type { CustomerCreateData, CustomerUpdateData } from '@/types/customer';

const customerService = {
  getAll: async (params?: { search?: string; role?: string }) => {
    const response = await apiClient.get('/v1/auth/admin/customers/', { params });
    // Assuming the backend returns the expected envelope { data: [...], ... }
    return response.data;
  },

  getById: async (id: string) => {
    const response = await apiClient.get(`/v1/auth/admin/customers/${id}/`);
    return response.data;
  },

  create: async (data: CustomerCreateData) => {
    const response = await apiClient.post('/v1/auth/admin/customers/', data);
    return response.data;
  },

  update: async (id: string, data: CustomerUpdateData) => {
    const response = await apiClient.patch(`/v1/auth/admin/customers/${id}/`, data);
    return response.data;
  },

  delete: async (id: string) => {
    const response = await apiClient.delete(`/v1/auth/admin/customers/${id}/`);
    return response.data;
  },

  sendWelcomeEmail: async (id: string) => {
    const response = await apiClient.post(`/v1/auth/admin/customers/${id}/send-welcome-email/`);
    return response.data;
  },

  unblockCustomer: async (id: string) => {
    const response = await apiClient.post(`/v1/auth/admin/customers/${id}/unblock/`);
    return response.data;
  },
};

export default customerService;
