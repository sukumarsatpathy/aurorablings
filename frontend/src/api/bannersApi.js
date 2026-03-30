import apiClient from '../services/api/client';

export const bannersApi = {
  /**
   * Fetches active promotional banners for the storefront.
   * GET /api/v1/banners/active/
   */
  getActive: async () => {
    const response = await apiClient.get('/v1/banners/active/');
    return response.data;
  },

  /**
   * Fetches all banners (for admin).
   * GET /api/v1/banners/
   */
  getAll: async () => {
    const response = await apiClient.get('/v1/banners/');
    return response.data;
  },

  /**
   * Creates a new banner.
   * POST /api/v1/banners/
   */
  create: async (formData) => {
    const response = await apiClient.post('/v1/banners/', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return response.data;
  },

  /**
   * Updates an existing banner.
   * PATCH /api/v1/banners/{id}/
   */
  update: async (id, formData) => {
    const response = await apiClient.patch(`/v1/banners/${id}/`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return response.data;
  },

  /**
   * Deletes (soft-delete) a banner.
   * DELETE /api/v1/banners/{id}/
   */
  delete: async (id) => {
    const response = await apiClient.delete(`/v1/banners/${id}/`);
    return response.data;
  },

  /**
   * Reorders banners.
   * POST /api/v1/banners/reorder/
   */
  reorder: async (orderData) => {
    const response = await apiClient.post('/v1/banners/reorder/', orderData);
    return response.data;
  },
};
