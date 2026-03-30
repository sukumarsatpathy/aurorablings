import apiClient from './client';

export interface ContactQueryPayload {
  name: string;
  email: string;
  phone?: string;
  subject?: string;
  message: string;
  turnstile_token?: string;
}

const contactService = {
  submitQuery: async (payload: ContactQueryPayload) => {
    const response = await apiClient.post('/v1/notifications/contact-form/', payload);
    return response.data;
  },
};

export default contactService;
