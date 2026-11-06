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
  /** Staff-confirmed Paytm UPI payments, to tick off against the Paytm app at close. */
  paytm_upi?: Array<{ order_number: string; amount: string; reference: string; at: string; by: string }>;
  /** Money spent during the shift. Cash ones are already inside cash_movements_net. */
  expenses?: ExpenseTotals & { items: ShiftExpenseRow[] };
}

export interface ExpenseTotals {
  cash: string;
  upi: string;
  total: string;
  count: number;
}

export interface ShiftExpenseRow {
  id: string;
  payment_mode: 'cash' | 'upi';
  amount: string;
  remarks: string;
  upi_reference: string;
  has_bill: boolean;
  voided: boolean;
  at: string;
  by: string;
}

export interface PosExpense {
  id: string;
  payment_mode: 'cash' | 'upi';
  amount: string;
  remarks: string;
  bill_image: string | null;
  upi_reference: string;
  shift: string | null;
  terminal: string;
  created_by: string;
  created_at: string;
  is_voided: boolean;
  voided_at: string | null;
  voided_by: string;
  void_reason: string;
  /** Present when the expense is on a shift: the drawer after it. */
  expected_cash_now?: string;
}

/** A barcode-less piece photographed at the counter. Never a catalogue product. */
export interface QuickItem {
  id: string;
  name: string;
  price: string;
  quantity: number;
  image: string | null;
  is_active: boolean;
  created_by: string;
  created_at: string;
}

/** Cart key for a quick item, so it can never collide with a variant id. */
export const QUICK_PREFIX = 'quick:';

/** A quick item shaped like a catalogue row, so the grid and cart treat it the same. */
export function quickItemToRow(item: QuickItem): CatalogueRow {
  return {
    variant_id: `${QUICK_PREFIX}${item.id}`,
    quick_item_id: item.id,
    sku: 'No barcode',
    barcode: null,
    stock_id: null,
    product_name: item.name,
    variant_name: '',
    price: item.price,
    compare_at_price: null,
    stock: item.quantity,
    track_inventory: true,
    low_stock: item.quantity <= 1,
    image: item.image,
  };
}

export interface CatalogueRow {
  variant_id: string;
  sku: string;
  /** The number on the variant's printed label. */
  barcode?: string | null;
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
  /** Set when this row is a quick item (no barcode); variant_id is then a cart key only. */
  quick_item_id?: string;
}

/** One sale line: a catalogue variant or a quick item, never a price. */
export interface CartLine {
  variant_id?: string;
  quick_item_id?: string;
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
  /** Quick-item lines on the order (absent from older servers). */
  quick_items?: Array<{ quick_item_id: string; quantity: number }>;
  amount_paid: string;
  balance_due: string;
  /** Handed over at the counter, or sent by courier. */
  fulfilment_type?: 'carry_away' | 'ship';
  shipping_address?: Record<string, unknown>;
  /** Which rail the counter is using for UPI. 'paytm' = staff confirm with the UPI reference. */
  upi_provider?: 'paytm' | 'razorpay';
  tenders: Array<{
    method: string;
    provider?: string;
    amount: string;
    status: string;
    /** Paytm UPI reference typed by staff, for matching at close. */
    reference?: string;
    at: string;
  }>;
}

/**
 * What the counter gets back when it asks for UPI.
 *
 *  - 'qr' / 'link' — Razorpay dynamic QR, settled by webhook (legacy rail).
 *  - 'upi_intent'  — QR for the shop's Paytm merchant UPI with the balance
 *                    pre-filled; staff confirm once the Soundbox announces it.
 *  - 'device'      — no merchant UPI ID configured: customer scans the Paytm
 *                    standee; staff confirm the same way.
 */
export interface UpiCollection {
  kind: 'qr' | 'link' | 'upi_intent' | 'device';
  provider?: 'paytm' | 'razorpay';
  transaction_id: string;
  qr_id: string;
  image_url?: string;
  payment_url?: string;
  upi_uri?: string;
  payee?: string;
  vpa?: string;
  amount: string;
  note?: string;
  close_by?: number | null;
  requires_confirmation?: boolean;
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
    /** ISO yyyy-mm-dd, or null. Returned so staff don't re-ask a regular. */
    date_of_birth: string | null;
    anniversary_date: string | null;
  };
}

const posService = {
  /** Phone is the identity at a counter, so this runs before anything else. */
  lookupCustomer: async (phone: string): Promise<CustomerLookup> => {
    const { data } = await apiClient.get('/v1/pos/customers/lookup/', { params: { phone } });
    return data;
  },

  /**
   * Set an existing customer's occasion dates from the counter.
   *
   * Only for someone who already has an account. For a new customer the dates
   * go on the sale instead — there is nothing to attach them to until the
   * money lands and the account is created.
   */
  setCustomerOccasions: async (
    userId: string,
    payload: { date_of_birth?: string | null; anniversary_date?: string | null },
  ): Promise<{ id: string; date_of_birth: string | null; anniversary_date: string | null }> => {
    const { data } = await apiClient.patch(`/v1/pos/customers/${userId}/occasions/`, payload);
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

  /**
   * One scanned code → one sellable variant (label barcode, then exact SKU,
   * then a stock ID that names a single-variant product). Rejects with the
   * server's 404/409 when nothing — or more than one thing — matches.
   */
  scan: async (code: string): Promise<CatalogueRow> => {
    const { data } = await apiClient.get('/v1/pos/scan/', { params: { code } });
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
    /**
     * Optional occasion dates taken at the counter. They ride on the order and
     * are copied onto the customer once the sale is linked to one — which is
     * only after settlement, since a new account does not exist before then.
     */
    date_of_birth?: string | null;
    anniversary_date?: string | null;
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

  upiCollection: async (orderId: string, shiftId: string, replaces?: string): Promise<UpiCollection> => {
    const { data } = await apiClient.post(`/v1/pos/orders/${orderId}/upi/`, {
      shift: shiftId,
      replaces,
    });
    return data;
  },

  /**
   * Staff confirming a UPI payment received on the shop's Paytm account.
   * No amount is sent — the server credits the outstanding balance.
   */
  upiTender: async (shiftId: string, payload: { order: string; reference: string }) => {
    const { data } = await apiClient.post(`/v1/pos/shifts/${shiftId}/upi-tender/`, payload);
    return data as {
      tender_id: string;
      amount_applied: string;
      reference: string;
      order_payment_status: string;
      balance_due: string;
    };
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
    return data as {
      order_number: string;
      status: string;
      payment_status: string;
      /** UPI received on Paytm for this sale that must be refunded from the Paytm app. */
      paytm_upi_to_refund?: string;
    };
  },
};

export interface ExpenseFilters {
  shift?: string;
  mode?: 'cash' | 'upi';
  from?: string;
  to?: string;
  limit?: number;
}

/** Quick items and expenses. Uploads are multipart; everything else is as above. */
export const quickItemService = {
  search: async (q: string): Promise<QuickItem[]> => {
    const { data } = await apiClient.get('/v1/pos/quick-items/', { params: { q } });
    return data;
  },

  /** Re-read price and count for a restored cart. */
  byIds: async (ids: string[]): Promise<QuickItem[]> => {
    if (!ids.length) return [];
    const { data } = await apiClient.get('/v1/pos/quick-items/', { params: { ids: ids.join(',') } });
    return data;
  },

  create: async (payload: { name: string; price: string; quantity: number; image?: Blob | null }): Promise<QuickItem> => {
    const form = new FormData();
    form.append('name', payload.name);
    form.append('price', payload.price);
    form.append('quantity', String(payload.quantity));
    if (payload.image) form.append('image', payload.image, 'photo.jpg');
    const { data } = await apiClient.post('/v1/pos/quick-items/', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return data;
  },
};

export const expenseService = {
  list: async (filters: ExpenseFilters = {}): Promise<{ totals: ExpenseTotals; results: PosExpense[] }> => {
    const { data } = await apiClient.get('/v1/pos/expenses/', { params: filters });
    return data;
  },

  create: async (payload: {
    payment_mode: 'cash' | 'upi';
    amount: string;
    remarks: string;
    upi_reference?: string;
    shift?: string;
    bill_image?: Blob | null;
  }): Promise<PosExpense> => {
    const form = new FormData();
    form.append('payment_mode', payload.payment_mode);
    form.append('amount', payload.amount);
    form.append('remarks', payload.remarks);
    if (payload.upi_reference) form.append('upi_reference', payload.upi_reference);
    if (payload.shift) form.append('shift', payload.shift);
    if (payload.bill_image) form.append('bill_image', payload.bill_image, 'bill.jpg');
    const { data } = await apiClient.post('/v1/pos/expenses/', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return data;
  },

  void: async (id: string, reason: string): Promise<PosExpense> => {
    const { data } = await apiClient.post(`/v1/pos/expenses/${id}/void/`, { reason });
    return data;
  },
};

export default posService;
