import axios from 'axios';

const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api',
  headers: {
    'Content-Type': 'application/json',
  },
});

let isHandlingAuthExpiry = false;

const clearAuthStorage = () => {
  localStorage.removeItem('auth_token');
  localStorage.removeItem('refresh_token');
  localStorage.removeItem('auth_user');
  window.dispatchEvent(new CustomEvent('aurora:auth-changed'));
};

const redirectToLogin = () => {
  const currentPath = `${window.location.pathname}${window.location.search}`;
  const isAuthRoute = window.location.pathname === '/login' || window.location.pathname === '/register';

  if (isAuthRoute) return;

  window.location.replace(`/login?next=${encodeURIComponent(currentPath)}`);
};

/**
 * Session key for a guest's order token (issued when a guest places an order).
 * Lets a shopper with no login pay for, view and cancel that one order.
 */
export const GUEST_ORDER_TOKEN_KEY = 'aurora_guest_order_token';

apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('auth_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  } else {
    // Only when nobody is logged in: a signed-in customer never needs it, and
    // the server ignores it for them anyway.
    let guestToken: string | null = null;
    try {
      guestToken = sessionStorage.getItem(GUEST_ORDER_TOKEN_KEY);
    } catch {
      guestToken = null;
    }
    if (guestToken) config.headers['X-Guest-Order-Token'] = guestToken;
  }
  return config;
});

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error.response?.status;
    const token = localStorage.getItem('auth_token');

    if ((status === 401 || status === 403) && token && !isHandlingAuthExpiry) {
      isHandlingAuthExpiry = true;
      clearAuthStorage();
      redirectToLogin();
      window.setTimeout(() => {
        isHandlingAuthExpiry = false;
      }, 300);
    }
    return Promise.reject(error);
  }
);

export default apiClient;
