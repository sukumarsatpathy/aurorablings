import apiClient from './client';
import type { AppSettingWriteData } from '@/types/setting';

const settingsService = {
  getPublic: async () => {
    const response = await apiClient.get('/v1/features/public-settings/');
    return response.data;
  },

  getAll: async (params?: { category?: string }) => {
    const response = await apiClient.get('/v1/features/settings/', { params });
    return response.data;
  },

  create: async (data: AppSettingWriteData) => {
    const response = await apiClient.post('/v1/features/settings/', data);
    return response.data;
  },

  update: async (key: string, data: Partial<AppSettingWriteData>) => {
    const response = await apiClient.patch(`/v1/features/settings/${key}/`, data);
    return response.data;
  },

  delete: async (key: string) => {
    const response = await apiClient.delete(`/v1/features/settings/${key}/`);
    return response.data;
  },

  uploadAsset: async (file: File, key?: string) => {
    const formData = new FormData();
    formData.append('file', file);
    if (key) formData.append('key', key);

    const response = await apiClient.post('/v1/features/settings/upload/', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return response.data;
  },
};

export default settingsService;
