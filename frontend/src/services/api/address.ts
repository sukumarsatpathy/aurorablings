import apiClient from './client';

export interface AddressLookupResult {
  city: string;
  state: string;
  area: string;
  areas: string[];
  pincode: string;
}

const EMPTY_RESULT: AddressLookupResult = {
  city: '',
  state: '',
  area: '',
  areas: [],
  pincode: '',
};

const normalizeResult = (payload: any): AddressLookupResult => {
  const data = payload?.data ?? payload ?? {};
  return {
    city: String(data?.city || ''),
    state: String(data?.state || ''),
    area: String(data?.area || ''),
    areas: Array.isArray(data?.areas) ? data.areas.map((row: any) => String(row || '')).filter(Boolean) : [],
    pincode: String(data?.pincode || ''),
  };
};

const addressService = {
  getFromPincode: async (pincode: string): Promise<AddressLookupResult> => {
    try {
      const response = await apiClient.get(`/address/pincode/${pincode}/`);
      return normalizeResult(response?.data);
    } catch {
      return EMPTY_RESULT;
    }
  },

  getFromCoordinates: async (lat: number, lng: number): Promise<AddressLookupResult> => {
    try {
      const response = await apiClient.post('/address/reverse/', { lat, lng });
      return normalizeResult(response?.data);
    } catch {
      return EMPTY_RESULT;
    }
  },
};

export default addressService;
