import apiClient from './client';

const CART_TOKEN_KEY = 'aurora_cart_token';

const isUUID = (value: string) =>
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(value);

const getGuestCartToken = (): string => {
  const existing = localStorage.getItem(CART_TOKEN_KEY);
  if (existing) return existing;
  const token = typeof crypto !== 'undefined' && 'randomUUID' in crypto
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(36).slice(2, 12)}`;
  localStorage.setItem(CART_TOKEN_KEY, token);
  return token;
};

const getCartHeaders = () => {
  const isAuthenticated = Boolean(localStorage.getItem('auth_token'));
  if (isAuthenticated) return {};
  return { 'X-Cart-Token': getGuestCartToken() };
};

const cartService = {
  getGuestCartToken,
  emitCartUpdated() {
    window.dispatchEvent(new CustomEvent('aurora:cart-updated'));
  },

  async getCart(couponCode?: string) {
    const response = await apiClient.get('/v1/cart/', {
      headers: getCartHeaders(),
      params: couponCode ? { coupon_code: couponCode } : undefined,
    });
    return response.data;
  },

  async clearCart() {
    const response = await apiClient.delete('/v1/cart/', {
      headers: getCartHeaders(),
    });
    return response.data;
  },

  async addItem(variantId: string, quantity: number) {
    const response = await apiClient.post(
      '/v1/cart/items/',
      { variant_id: variantId, quantity },
      { headers: getCartHeaders() }
    );
    return response.data;
  },

  async mergeGuestCart(sessionKey: string) {
    const response = await apiClient.post('/v1/cart/merge/', { session_key: sessionKey });
    return response.data;
  },

  async updateItem(itemId: string, quantity: number) {
    const response = await apiClient.patch(
      `/v1/cart/items/${itemId}/`,
      { quantity },
      { headers: getCartHeaders() }
    );
    return response.data;
  },

  async removeItem(itemId: string) {
    const response = await apiClient.delete(`/v1/cart/items/${itemId}/`, {
      headers: getCartHeaders(),
    });
    return response.data;
  },

  async syncLocalCartItems(items: Array<{ variantId: string; quantity: number }>) {
    try {
      await cartService.clearCart();
    } catch {
      // If cart wasn't present yet, continue and add current local items.
    }

    for (const item of items) {
      if (!isUUID(item.variantId)) continue;
      if (!Number.isFinite(item.quantity) || item.quantity < 1) continue;
      await cartService.addItem(item.variantId, item.quantity);
    }
  },

  async calculateSurcharge(payload: {
    shipping_address: { country: string; state: string; pincode: string };
    payment_method?: string;
  }) {
    const isAuthenticated = Boolean(localStorage.getItem('auth_token'));
    const body = {
      ...payload,
      ...(isAuthenticated ? {} : { session_key: getGuestCartToken() }),
    };

    const response = await apiClient.post('/v1/surcharge/calculate/', body, {
      headers: getCartHeaders(),
    });
    return response.data;
  },

  async applyCoupon(couponCode: string) {
    const response = await apiClient.post(
      '/v1/cart/apply-coupon/',
      { coupon_code: couponCode },
      { headers: getCartHeaders() }
    );
    return response.data;
  },
};

export default cartService;
