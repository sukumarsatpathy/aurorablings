import apiClient from './client';

export interface RazorpayOrderPayload {
  order_id: string;
  amount: number;
  currency?: string;
}

export interface RazorpayOrderResponse {
  transaction_id: string;
  razorpay_order_id: string;
  amount: string | number;
  currency: string;
  key_id: string;
}

export interface RazorpayVerifyPayload {
  razorpay_order_id: string;
  razorpay_payment_id: string;
  razorpay_signature: string;
}

const paymentsService = {
  async createRazorpayOrder(payload: RazorpayOrderPayload) {
    const response = await apiClient.post('/v1/payments/create-order/', payload);
    return response.data;
  },

  async verifyRazorpayPayment(payload: RazorpayVerifyPayload) {
    const response = await apiClient.post('/v1/payments/verify/', payload);
    return response.data;
  },

  async initiatePayment(payload: {
    order_id: string;
    provider: string;
    return_url?: string;
  }) {
    const response = await apiClient.post('/v1/payments/initiate/', payload);
    return response.data;
  },
};

export default paymentsService;
