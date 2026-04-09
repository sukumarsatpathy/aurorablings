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

export interface AdminPaymentTransaction {
  id: string;
  order: string;
  provider: string;
  provider_ref: string;
  razorpay_order_id?: string;
  razorpay_payment_id?: string;
  status: string;
  total_amount: string | number;
  refunded_amount: string | number;
  amount: string | number;
  currency: string;
  retry_count?: number;
  created_at: string;
  updated_at: string;
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

  async listAdminTransactions(orderId: string) {
    const response = await apiClient.get('/v1/payments/admin/transactions/', {
      params: { order_id: orderId },
    });
    return response.data as { data?: AdminPaymentTransaction[]; message?: string };
  },

  async reconcileAdminOrder(orderId: string) {
    const response = await apiClient.post('/v1/payments/admin/reconcile/', {
      order_id: orderId,
    });
    return response.data as {
      data?: {
        order_id: string;
        order_status: string;
        payment_status: string;
        transaction?: AdminPaymentTransaction | null;
      };
      message?: string;
    };
  },
};

export default paymentsService;
