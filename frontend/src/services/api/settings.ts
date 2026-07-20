import apiClient from './client';
import type { AppSettingWriteData } from '@/types/setting';
import { toUploadProgress, type UploadProgressHandler } from './uploadProgress';
import { getBootSettings } from '../boot';

const settingsService = {
  getPublic: async () => {
    // Fast path: settings were server-injected into index.html (window.__BOOT__)
    // so storefront boot (useBranding/useCurrency) needs no API round trip.
    // Same envelope shape as the API: callers read `response.data`.
    const bootSettings = getBootSettings();
    if (bootSettings) {
      return { data: bootSettings };
    }
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

  uploadAsset: async (file: File, key?: string, onProgress?: UploadProgressHandler) => {
    const formData = new FormData();
    formData.append('file', file);
    if (key) formData.append('key', key);

    const response = await apiClient.post('/v1/features/settings/upload/', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: toUploadProgress(onProgress),
    });
    return response.data;
  },
};

export default settingsService;
