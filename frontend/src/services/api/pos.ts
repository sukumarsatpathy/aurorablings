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
  /** Present on the management endpoints; the counter never reads these. */
  created_at?: string;
  has_open_shift?: boolean;
  shift_count?: number;
  order_count?: number;
}

export interface PosTerminalWrite {
  code: string;
  name: string;
  location?: string;
  is_active?: boolean;
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

export interface ShiftSummary {
  shift_id: string;
  terminal: string;
  opened_at: string;
  closed_at: string | null;
  orders: number;
  by_tender: Record<string, { total: string; count?: number }>;
  cash_taken: string;
  cash_movements_net: string;
  opening_float: string;
  expected_cash: string;
  counted_cash: string | null;
  variance: string | null;
  manual_discounts: string;
  coupon_discounts: string;
  part_paid_open: number;
}

export interface CatalogueRow {
  variant_id: string;
  sku: string;
  /** The product's counter stock reference. Null until someone assigns one. */
  stock_id: number | null;
  product_name: string;
  variant_name: string;
  price: string;
  compare_at_price: string | null;
  stock: number;
  track_inventory: boolean;
  low_stock: boolean;
  /** Product's primary image, small derivative. Null when none is uploaded. */
  image: string | null;
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
  subtotal: string;
  /** Coupon discount. Separate from the manual one — they report differently. */
  discount_amount: string;
  manual_discount_amount: string;
  manual_discount_reason: string;
  tax_amount: string;
  shipping_cost: string;
  grand_total: string;
  contact_name: string;
  contact_phone: string;
  contact_email: string;
  /** The order's own lines — what "back to cart" refills from. */
  items: Array<{ variant_id: string; quantity: number }>;
  amount_paid: string;
  balance_due: string;
  tenders: Array<{ method: string; amount: string; status: string; at: string }>;
}

export interface CustomerLookup {
  found: boolean;
  conflict: boolean;
  reason: string;
  customer?: {
    id: string;
    name: string;
    email: string;
    phone: string;
    orders: number;
  };
}

const posService = {
  /** Phone is the identity at a counter, so this runs before anything else. */
  lookupCustomer: async (phone: string): Promise<CustomerLookup> => {
    const { data } = await apiClient.get('/v1/pos/customers/lookup/', { params: { phone } });
    return data;
  },

  // ── Terminals and shifts ────────────────────────────────
  terminals: async (): Promise<PosTerminal[]> => {
    const { data } = await apiClient.get('/v1/pos/terminals/');
    return data;
  },

  // ── Terminal management (Settings → POS Terminals, admin only) ──
  /** Includes deactivated terminals. The server serves those to admins only. */
  allTerminals: async (): Promise<PosTerminal[]> => {
    const { data } = await apiClient.get('/v1/pos/terminals/', {
      params: { include_inactive: true },
    });
    return data;
  },

  createTerminal: async (payload: PosTerminalWrite): Promise<PosTerminal> => {
    const { data } = await apiClient.post('/v1/pos/terminals/', payload);
    return data;
  },

  updateTerminal: async (id: string, payload: Partial<PosTerminalWrite>): Promise<PosTerminal> => {
    const { data } = await apiClient.patch(`/v1/pos/terminals/${id}/`, payload);
    return data;
  },

  deleteTerminal: async (id: string): Promise<void> => {
    await apiClient.delete(`/v1/pos/terminals/${id}/`);
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

  shiftSummary: async (shiftId: string): Promise<ShiftSummary> => {
    const { data } = await apiClient.get(`/v1/pos/shifts/${shiftId}/summary/`);
    return data;
  },

  closeShift: async (
    shiftId: string,
    countedCash: string,
    note = '',
    force = false,
  ): Promise<PosShift> => {
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

  /** Re-read price and stock for a restored cart. Never trust what the browser kept. */
  catalogueByIds: async (ids: string[]): Promise<CatalogueRow[]> => {
    if (!ids.length) return [];
    const { data } = await apiClient.get('/v1/pos/catalogue/', { params: { ids: ids.join(',') } });
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
    /** Whether a NEW account may be created. An existing one is linked regardless. */
    create_account?: boolean;
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
