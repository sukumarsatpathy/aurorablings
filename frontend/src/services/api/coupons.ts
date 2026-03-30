import apiClient from './client';
import type { CouponWriteData } from '@/types/coupon';

const couponService = {
  getAll: async (params?: { search?: string; is_active?: boolean }) => {
    const response = await apiClient.get('/v1/pricing/coupons/', { params });
    return response.data;
  },

  create: async (data: CouponWriteData) => {
    const response = await apiClient.post('/v1/pricing/coupons/', data);
    return response.data;
  },

  update: async (id: string, data: Partial<CouponWriteData>) => {
    const response = await apiClient.patch(`/v1/pricing/coupons/${id}/`, data);
    return response.data;
  },

  delete: async (id: string) => {
    const response = await apiClient.delete(`/v1/pricing/coupons/${id}/`);
    return response.data;
  },
};

export default couponService;
