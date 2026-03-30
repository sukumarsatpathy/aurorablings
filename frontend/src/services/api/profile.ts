import apiClient from './client';

export interface ProfileData {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  full_name: string;
  phone: string;
  role: 'admin' | 'staff' | 'customer' | string;
  is_email_verified: boolean;
  date_joined: string;
}

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

const profileService = {
  getProfile: async () => {
    const response = await apiClient.get('/v1/auth/profile/');
    return response.data;
  },

  updateProfile: async (data: Partial<Pick<ProfileData, 'first_name' | 'last_name' | 'phone'>>) => {
    const response = await apiClient.patch('/v1/auth/profile/', data);
    return response.data;
  },

  getAddresses: async () => {
    const response = await apiClient.get('/v1/auth/addresses/');
    return response.data;
  },

  createAddress: async (data: AddressData) => {
    const response = await apiClient.post('/v1/auth/addresses/', data);
    return response.data;
  },

  updateAddress: async (id: string, data: Partial<AddressData>) => {
    const response = await apiClient.patch(`/v1/auth/addresses/${id}/`, data);
    return response.data;
  },

  deleteAddress: async (id: string) => {
    const response = await apiClient.delete(`/v1/auth/addresses/${id}/`);
    return response.data;
  },

  logout: async (refreshToken: string) => {
    const response = await apiClient.post('/v1/auth/logout/', { refresh: refreshToken });
    return response.data;
  },

  changePassword: async (data: { current_password: string; new_password: string }) => {
    const response = await apiClient.post('/v1/auth/password/change/', data);
    return response.data;
  },
};

export default profileService;
