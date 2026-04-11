import apiClient from './client';

export interface AdminOrderListRow {
  id: string;
  order_number: string;
  status: string;
  payment_status: string;
  grand_total: string;
  currency: string;
  item_count: number;
  customer_name: string;
  customer_email: string;
  placed_at?: string | null;
  created_at: string;
  invoice_url?: string;
}

export interface AdminOrderDetail extends AdminOrderListRow {
  guest_email?: string;
  payment_method?: string;
  payment_reference?: string;
  shipping_address?: Record<string, string>;
  billing_address?: Record<string, string>;
  subtotal: string;
  discount_amount: string;
  shipping_cost: string;
  tax_amount: string;
  notes?: string;
  internal_notes?: string;
  tracking_number?: string;
  shipping_carrier?: string;
  shipment?: {
    id: string;
    provider: string;
    status: string;
    awb_code?: string;
    courier_name?: string;
    tracking_url?: string;
    label_url?: string;
    manifest_url?: string;
    invoice_url?: string;
    pickup_requested?: boolean;
    error_code?: string;
    error_message?: string;
    events?: Array<{
      id: string;
      source: string;
      provider_status: string;
      internal_status: string;
      event_payload?: Record<string, unknown>;
      created_at: string;
    }>;
  } | null;
  invoice_url?: string;
  items: Array<{
    id: string;
    sku: string;
    product_name: string;
    variant_name: string;
    quantity: number;
    unit_price: string;
    line_total: string;
    product_image?: string | null;
    product_id?: string | null;
    can_review?: boolean;
    has_reviewed?: boolean;
    my_review_id?: string | null;
    review_eligibility_reason?: string;
  }>;
  status_history: Array<{
    id: string;
    from_status: string;
    to_status: string;
    changed_by_email?: string | null;
    notes?: string;
    created_at: string;
  }>;
}

export interface CustomerOrderListRow {
  id: string;
  order_number: string;
  status: string;
  payment_status: string;
  grand_total: string;
  currency: string;
  item_count: number;
  customer_name: string;
  customer_email: string;
  placed_at?: string | null;
  created_at: string;
  invoice_url?: string;
}

export interface CustomerOrderDetail extends CustomerOrderListRow {
  guest_email?: string;
  payment_method?: string;
  payment_reference?: string;
  shipping_address?: Record<string, string>;
  billing_address?: Record<string, string>;
  subtotal: string;
  coupon_code?: string;
  discount_amount: string;
  shipping_cost: string;
  tax_amount: string;
  tracking_number?: string;
  shipping_carrier?: string;
  shipment?: {
    id: string;
    provider: string;
    status: string;
    awb_code?: string;
    courier_name?: string;
    tracking_url?: string;
    label_url?: string;
    manifest_url?: string;
    invoice_url?: string;
    pickup_requested?: boolean;
    error_code?: string;
    error_message?: string;
    events?: Array<{
      id: string;
      source: string;
      provider_status: string;
      internal_status: string;
      event_payload?: Record<string, unknown>;
      created_at: string;
    }>;
  } | null;
  invoice_url?: string;
  notes?: string;
  updated_at: string;
  items: Array<{
    id: string;
    sku: string;
    product_name: string;
    variant_name: string;
    quantity: number;
    unit_price: string;
    line_total: string;
    product_image?: string | null;
    product_id?: string | null;
    can_review?: boolean;
    has_reviewed?: boolean;
    my_review_id?: string | null;
    review_eligibility_reason?: string;
  }>;
  status_history: Array<{
    id: string;
    from_status: string;
    to_status: string;
    changed_by_email?: string | null;
    notes?: string;
    created_at: string;
  }>;
}

const resolveInvoiceEndpoint = (orderId: string, invoiceUrl?: string): string => {
  const defaultEndpoint = `/v1/orders/${orderId}/invoice/`;

  const isInvoicePath = (path: string): boolean => {
    const clean = path.split('?')[0].replace(/\/+$/, '/');
    return /\/orders\/[0-9a-f-]+\/invoice\/$/i.test(clean);
  };

  const normalizeApiPath = (path: string): string => {
    const trimmed = path.trim();
    if (!trimmed) return defaultEndpoint;
    return trimmed.startsWith('/api/') ? trimmed.replace(/^\/api/, '') : trimmed;
  };

  if (!invoiceUrl || !invoiceUrl.trim()) {
    return defaultEndpoint;
  }

  if (invoiceUrl && invoiceUrl.trim()) {
    try {
      const url = new URL(invoiceUrl, window.location.origin);
      const normalized = normalizeApiPath(`${url.pathname}${url.search}`);
      return isInvoicePath(normalized) ? normalized : defaultEndpoint;
    } catch {
      const normalized = normalizeApiPath(invoiceUrl);
      return isInvoicePath(normalized) ? normalized : defaultEndpoint;
    }
  }
  return defaultEndpoint;
};

const resolveInvoiceFilename = (orderId: string, contentDisposition?: string): string => {
  if (contentDisposition) {
    const utf8Match = contentDisposition.match(/filename\*=UTF-8''([^;]+)/i);
    if (utf8Match?.[1]) return decodeURIComponent(utf8Match[1]);
    const basicMatch = contentDisposition.match(/filename="?([^"]+)"?/i);
    if (basicMatch?.[1]) return basicMatch[1];
  }
  return `invoice-${orderId}.pdf`;
};

const ordersService = {
  placeOrder: async (payload: {
    shipping_address: Record<string, string>;
    billing_address?: Record<string, string>;
    payment_method: 'cod' | 'cashfree' | 'razorpay' | 'phonepe' | 'stripe' | 'upi' | 'bank_transfer';
    shipping_cost: number;
    coupon_code?: string;
    notes?: string;
    guest_email?: string;
    session_key?: string;
    warehouse_id?: string | null;
    create_account?: boolean;
    save_address?: boolean;
    account?: {
      email: string;
      password: string;
      first_name: string;
      last_name: string;
      phone?: string;
    };
  }) => {
    const response = await apiClient.post('/v1/orders/create/', payload);
    return response.data;
  },

  listMyOrders: async (params?: { status?: string }) => {
    const response = await apiClient.get('/v1/orders/', { params });
    return response.data;
  },

  getMyOrder: async (id: string) => {
    const response = await apiClient.get(`/v1/orders/${id}/`);
    return response.data;
  },

  cancelMyOrder: async (id: string, reason?: string) => {
    const response = await apiClient.post(`/v1/orders/${id}/cancel/`, {
      reason: reason || 'Order cancelled by customer.',
    });
    return response.data;
  },

  listAdminOrders: async (params?: {
    status?: string;
    payment_status?: string;
    user_id?: string;
    search?: string;
  }) => {
    const response = await apiClient.get('/v1/orders/admin/', { params });
    return response.data;
  },

  getAdminOrder: async (id: string) => {
    const response = await apiClient.get(`/v1/orders/admin/${id}/`);
    return response.data;
  },

  createAdminOrder: async (payload: {
    user_id?: string;
    guest_email?: string;
    status?: string;
    payment_status?: string;
    payment_method?: string;
    shipping_address?: Record<string, string>;
    billing_address?: Record<string, string>;
    subtotal?: number;
    discount_amount?: number;
    shipping_cost?: number;
    tax_amount?: number;
    grand_total?: number;
    currency?: string;
    notes?: string;
    internal_notes?: string;
    coupon_code?: string;
    warehouse_id?: string | null;
    items?: Array<{ variant_id: string; quantity: number }>;
  }) => {
    const response = await apiClient.post('/v1/orders/admin/', payload);
    return response.data;
  },

  calculateAdminOrder: async (payload: {
    user_id?: string | null;
    payment_method?: string;
    shipping_address?: Record<string, string>;
    coupon_code?: string;
    items: Array<{ variant_id: string; quantity: number }>;
  }) => {
    const response = await apiClient.post('/v1/orders/admin/calculate/', payload);
    return response.data;
  },

  updateAdminOrder: async (
    id: string,
    payload: Partial<{
      status: string;
      payment_status: string;
      payment_method: string;
      shipping_address: Record<string, string>;
      billing_address: Record<string, string>;
      subtotal: number;
      discount_amount: number;
      shipping_cost: number;
      tax_amount: number;
      grand_total: number;
      currency: string;
      notes: string;
      internal_notes: string;
      tracking_number: string;
      shipping_carrier: string;
    }>
  ) => {
    const response = await apiClient.patch(`/v1/orders/admin/${id}/`, payload);
    return response.data;
  },

  deleteAdminOrder: async (id: string) => {
    const response = await apiClient.delete(`/v1/orders/admin/${id}/`);
    return response.data;
  },

  transitionOrder: async (id: string, payload: { new_status: string; notes?: string }) => {
    const response = await apiClient.post(`/v1/orders/admin/${id}/transition/`, payload);
    return response.data;
  },

  markAdminOrderPaid: async (
    id: string,
    payload?: Partial<{
      payment_reference: string;
      payment_method: string;
    }>
  ) => {
    const response = await apiClient.post(`/v1/orders/admin/${id}/pay/`, payload || {});
    return response.data;
  },

  getInvoiceDownloadUrl: (orderId: string) => `/v1/orders/${orderId}/invoice/`,

  downloadInvoice: async (orderId: string, invoiceUrl?: string) => {
    const canonicalEndpoint = `/v1/orders/${orderId}/invoice/`;
    const endpoint = resolveInvoiceEndpoint(orderId, invoiceUrl);
    const fetchPdf = async (url: string) => {
      const response = await apiClient.get(url, { responseType: 'blob' });
      const contentType = String(response.headers?.['content-type'] || '').toLowerCase();
      if (contentType.includes('application/json') || contentType.includes('text/html')) {
        throw new Error('Invalid invoice response content type.');
      }
      return response;
    };

    let response;
    try {
      response = await fetchPdf(endpoint);
    } catch (error) {
      if (endpoint === canonicalEndpoint) throw error;
      response = await fetchPdf(canonicalEndpoint);
    }

    const blob = response.data as Blob;
    const filename = resolveInvoiceFilename(orderId, response.headers?.['content-disposition'] as string | undefined);
    const href = window.URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = href;
    anchor.download = filename;
    document.body.appendChild(anchor);
    anchor.click();
    document.body.removeChild(anchor);
    window.URL.revokeObjectURL(href);
  },

  regenerateInvoice: async (orderId: string) => {
    const response = await apiClient.post(`/v1/orders/admin/${orderId}/invoice/regenerate/`);
    return response.data;
  },

  downloadShippingLabel: async (orderId: string) => {
    const response = await apiClient.get(`/v1/orders/admin/${orderId}/shipping-label/`, {
      responseType: 'blob',
    });

    const blob = response.data as Blob;
    const contentDisposition = String(response.headers?.['content-disposition'] || '');
    const basicMatch = contentDisposition.match(/filename="?([^"]+)"?/i);
    const filename = basicMatch?.[1] || `shipping-label-${orderId}.pdf`;

    const href = window.URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = href;
    anchor.download = filename;
    document.body.appendChild(anchor);
    anchor.click();
    document.body.removeChild(anchor);
    window.URL.revokeObjectURL(href);
  },

  printShippingLabel: async (orderId: string) => {
    const response = await apiClient.get(`/v1/orders/admin/${orderId}/shipping-label/?format=html`, {
      responseType: 'text',
    });
    const html = String(response.data || '').trim();
    if (!html) throw new Error('Shipping label preview is empty.');

    const printWindow = window.open('', '_blank', 'noopener,noreferrer');
    if (!printWindow) throw new Error('Unable to open print window. Please allow pop-ups.');

    printWindow.document.open();
    printWindow.document.write(html);
    printWindow.document.close();
    printWindow.focus();
    window.setTimeout(() => {
      printWindow.print();
    }, 250);
  },

  sendOrderConfirmationEmail: async (orderId: string) => {
    const response = await apiClient.post(`/v1/orders/admin/${orderId}/send-confirmation-email/`);
    return response.data;
  },
};

export default ordersService;
