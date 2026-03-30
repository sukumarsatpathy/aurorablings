import apiClient from './client';

export interface AddressData {
  id?: string;
  address_type: 'shipping' | 'billing';
  is_default: boolean;
  full_name: string;
  line1: string;
  line2?: string;
  city: string;
  state: string;
  postal_code: string;
  country: string;
  phone: string;
}

const customerAddressService = {
  getAll: async (userId: string) => {
    const response = await apiClient.get(`/v1/auth/admin/customers/${userId}/addresses/`);
    return response.data;
  },

  create: async (userId: string, data: AddressData) => {
    const response = await apiClient.post(`/v1/auth/admin/customers/${userId}/addresses/`, data);
    return response.data;
  },

  update: async (userId: string, addressId: string, data: Partial<AddressData>) => {
    const response = await apiClient.patch(`/v1/auth/admin/customers/${userId}/addresses/${addressId}/`, data);
    return response.data;
  },

  delete: async (userId: string, addressId: string) => {
    const response = await apiClient.delete(`/v1/auth/admin/customers/${userId}/addresses/${addressId}/`);
    return response.data;
  },
};

export default customerAddressService;
