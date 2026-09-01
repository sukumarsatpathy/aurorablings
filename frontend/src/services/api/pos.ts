import apiClient from './client';

/**
 * Counter API.
 *
 * Note what none of these send: a price. The till posts variant ids and
 * quantities, and every figure comes back from the server. A counter tablet is
 * shared, unlocked, and handled by whoever is standing at the stall.
 */

export interface PosTerminal {
  id: string;
  code: string;
  name: string;
  location: string;
  is_active: boolean;
}

export interface PosShift {
  id: string;
  terminal: string;
  terminal_code: string;
  status: 'open' | 'closed';
  opened_at: string;
  opening_float: string;
  closed_at: string | null;
  counted_cash: string | null;
  expected_cash: string | null;
  variance: string | null;
  cash_taken: string;
  expected_cash_now: string;
  part_paid_orders: Array<{ id: string; order_number: string; grand_total: string }>;
}

export interface CatalogueRow {
  variant_id: string;
  sku: string;
  product_name: string;
  variant_name: string;
  price: string;
  compare_at_price: string | null;
  stock: number;
  track_inventory: boolean;
  low_stock: boolean;
}

export interface CartLine {
  variant_id: string;
  quantity: number;
}

export interface PosOrder {
  order_id: string;
  order_number: string;
  subtotal: string;
  discount_amount: string;
  grand_total: string;
  fulfilment_type: string;
}

export interface PaymentState {
  order_number: string;
  payment_status: string;
  grand_total: string;
  amount_paid: string;
  balance_due: string;
  tenders: Array<{ method: string; amount: string; status: string; at: string }>;
}

const posService = {
  // ── Terminals and shifts ────────────────────────────────
  terminals: async (): Promise<PosTerminal[]> => {
    const { data } = await apiClient.get('/v1/pos/terminals/');
    return data;
  },

  currentShift: async (terminalId?: string): Promise<PosShift | null> => {
    const { data } = await apiClient.get('/v1/pos/shifts/current/', {
      params: terminalId ? { terminal: terminalId } : undefined,
    });
    return data.shift;
  },

  openShift: async (terminal: string, openingFloat: string): Promise<PosShift> => {
    const { data } = await apiClient.post('/v1/pos/shifts/open/', {
      terminal,
      opening_float: openingFloat,
    });
    return data;
  },

  shiftSummary: async (shiftId: string) => {
    const { data } = await apiClient.get(`/v1/pos/shifts/${shiftId}/summary/`);
    return data;
  },

  closeShift: async (shiftId: string, countedCash: string, note = '', force = false) => {
    const { data } = await apiClient.post(`/v1/pos/shifts/${shiftId}/close/`, {
      counted_cash: countedCash,
      note,
      force,
    });
    return data;
  },

  // ── Selling ─────────────────────────────────────────────
  catalogue: async (q: string): Promise<CatalogueRow[]> => {
    const { data } = await apiClient.get('/v1/pos/catalogue/', { params: { q } });
    return data;
  },

  quote: async (items: CartLine[], couponCode = '') => {
    const { data } = await apiClient.post('/v1/pos/quote/', {
      items,
      coupon_code: couponCode,
    });
    return data;
  },

  createOrder: async (payload: {
    items: CartLine[];
    shift: string;
    coupon_code?: string;
    contact_name?: string;
    contact_phone?: string;
    contact_email?: string;
    fulfilment_type?: 'carry_away' | 'ship';
    shipping_address?: Record<string, unknown>;
  }): Promise<PosOrder> => {
    const { data } = await apiClient.post('/v1/pos/orders/', payload);
    return data;
  },

  applyDiscount: async (
    orderId: string,
    payload: {
      percent?: string;
      amount?: string;
      reason: string;
      approver_email?: string;
      approver_password?: string;
    },
  ) => {
    const { data } = await apiClient.post(`/v1/pos/orders/${orderId}/discount/`, payload);
    return data;
  },

  // ── Taking money ────────────────────────────────────────
  cashTender: async (
    shiftId: string,
    payload: { order: string; amount_applied: string; cash_received?: string },
  ) => {
    const { data } = await apiClient.post(`/v1/pos/shifts/${shiftId}/cash-tender/`, payload);
    return data;
  },

  upiCollection: async (orderId: string, shiftId: string, replaces?: string) => {
    const { data } = await apiClient.post(`/v1/pos/orders/${orderId}/upi/`, {
      shift: shiftId,
      replaces,
    });
    return data;
  },

  /** Polls our own backend — never Razorpay. Only a verified webhook turns this green. */
  paymentState: async (orderId: string): Promise<PaymentState> => {
    const { data } = await apiClient.get(`/v1/pos/orders/${orderId}/payment-state/`);
    return data;
  },

  partPaidOrders: async () => {
    const { data } = await apiClient.get('/v1/pos/orders/part-paid/');
    return data;
  },

  voidSale: async (orderId: string, reason: string) => {
    const { data } = await apiClient.post(`/v1/pos/orders/${orderId}/void/`, { reason });
    return data;
  },
};

export default posService;
