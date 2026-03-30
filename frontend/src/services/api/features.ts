import apiClient from './client';
import type { FeatureWriteData } from '@/types/feature';

const featureService = {
  getAll: async (params?: { category?: string }) => {
    const response = await apiClient.get('/v1/features/', { params });
    return response.data;
  },

  create: async (data: FeatureWriteData) => {
    const response = await apiClient.post('/v1/features/', data);
    return response.data;
  },

  update: async (code: string, data: Partial<FeatureWriteData>) => {
    const response = await apiClient.patch(`/v1/features/${code}/`, data);
    return response.data;
  },

  delete: async (code: string) => {
    const response = await apiClient.delete(`/v1/features/${code}/`);
    return response.data;
  },

  enable: async (code: string, notes = '') => {
    const response = await apiClient.post(`/v1/features/${code}/enable/`, { notes });
    return response.data;
  },

  disable: async (code: string, notes = '') => {
    const response = await apiClient.post(`/v1/features/${code}/disable/`, { notes });
    return response.data;
  },

  setRollout: async (code: string, percentage: number) => {
    const response = await apiClient.post(`/v1/features/${code}/rollout/`, { percentage });
    return response.data;
  },
};

export default featureService;
