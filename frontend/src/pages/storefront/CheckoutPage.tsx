import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { ShieldCheck, ArrowLeft, CreditCard, Truck, ClipboardList } from 'lucide-react';
import { Link, useNavigate } from 'react-router-dom';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Card } from '@/components/ui/Card';
import { useCurrency } from '@/hooks/useCurrency';
import cartService from '@/services/api/cart';
import ordersService from '@/services/api/orders';
import apiClient from '@/services/api/client';
import profileService, { type AddressData as ProfileAddressData } from '@/services/api/profile';
import { useAddressAutoFill } from '@/hooks/useAddressAutoFill';
import { useTurnstileConfig } from '@/hooks/useTurnstileConfig';
import { TurnstileWidget } from '@/components/security/TurnstileWidget';

interface CheckoutCartItem {
  id: string;
  variantId: string;
  productName: string;
  variantName: string;
  quantity: number;
  unitPrice: number;
  lineTotal: number;
  thumbnail: string;
}

interface AuthUserCache {
  first_name?: string;
  last_name?: string;
  email?: string;
  phone?: string;
}

type CheckoutPaymentMethod = 'cashfree' | 'razorpay' | 'stripe' | 'upi' | 'bank_transfer';

interface ProviderRow {
  name: string;
  display_name?: string;
}

interface PaymentOption {
  value: CheckoutPaymentMethod;
  label: string;
}

declare global {
  interface Window {
    Cashfree?: (config: { mode: 'sandbox' | 'production' }) => {
      checkout: (options: { paymentSessionId: string; redirectTarget?: '_self' | '_blank' }) => Promise<unknown> | unknown;
    };
  }
}

const FALLBACK_PAYMENT_OPTIONS: PaymentOption[] = [
  { value: 'cashfree', label: 'Online Payment' },
];

const FALLBACK_IMAGE = 'https://placehold.co/600x600/f3f4f6/517b4b?text=Product';

const loadCashfreeSdk = async (): Promise<void> => {
  if (typeof window === 'undefined') return;
  if (window.Cashfree) return;

  await new Promise<void>((resolve, reject) => {
    const existing = document.querySelector<HTMLScriptElement>('script[data-cashfree-sdk="true"]');
    if (existing) {
      existing.addEventListener('load', () => resolve(), { once: true });
      existing.addEventListener('error', () => reject(new Error('Failed to load Cashfree SDK.')), { once: true });
      return;
    }

    const script = document.createElement('script');
    script.src = 'https://sdk.cashfree.com/js/v3/cashfree.js';
    script.async = true;
    script.dataset.cashfreeSdk = 'true';
    script.onload = () => resolve();
    script.onerror = () => reject(new Error('Failed to load Cashfree SDK.'));
    document.head.appendChild(script);
  });
};

const openCashfreeCheckout = async (paymentSessionId: string): Promise<void> => {
  await loadCashfreeSdk();
  if (!window.Cashfree) {
    throw new Error('Cashfree SDK is unavailable.');
  }

  const envRaw = String(import.meta.env.VITE_CASHFREE_ENV || '').trim().toLowerCase();
  const mode: 'sandbox' | 'production' =
    envRaw === 'production'
      ? 'production'
      : 'sandbox';

  const cashfree = window.Cashfree({ mode });
  await cashfree.checkout({
    paymentSessionId,
    redirectTarget: '_self',
  });
};

const mapCheckoutItems = (payload: any): CheckoutCartItem[] => {
  const rows = payload?.data?.items;
  if (!Array.isArray(rows)) return [];

  return rows.map((row: any) => ({
    id: String(row?.id || ''),
    variantId: String(row?.variant_id || ''),
    productName: String(row?.product_name || 'Product'),
    variantName: String(row?.variant_name || 'Standard'),
    quantity: Math.max(1, Number(row?.quantity || 1)),
    unitPrice: Number(row?.unit_price || 0),
    lineTotal: Number(row?.line_total || 0),
    thumbnail: String(row?.thumbnail || FALLBACK_IMAGE),
  }));
};

const mapProfileAddressToCheckout = (address: ProfileAddressData | null | undefined) => {
  if (!address) return null;
  return {
    full_name: String(address.full_name || ''),
    line1: String(address.line1 || ''),
    line2: String(address.line2 || ''),
    city: String(address.city || ''),
    state: String(address.state || ''),
    pincode: String(address.postal_code || ''),
    country: String(address.country || 'India'),
    phone: String(address.phone || ''),
    area: '',
  };
};

const toOrderAddressPayload = (address: {
  full_name: string;
  line1: string;
  line2: string;
  city: string;
  state: string;
  pincode: string;
  country: string;
  phone: string;
  area?: string;
}) => ({
  full_name: address.full_name,
  line1: address.line1,
  line2: address.line2,
  city: address.city,
  state: address.state,
  pincode: address.pincode,
  country: address.country,
  phone: address.phone,
});

const pickAddress = (addresses: ProfileAddressData[], type: 'shipping' | 'billing') => {
  const sameType = addresses.filter((row) => row.address_type === type);
  const preferred =
    sameType.find((row) => row.is_default) ||
    sameType[0] ||
    addresses.find((row) => row.is_default) ||
    addresses[0];
  return preferred || null;
};

export const CheckoutPage: React.FC = () => {
  const { formatCurrency } = useCurrency();
  const [cartLoading, setCartLoading] = useState(true);
  const [cartError, setCartError] = useState('');
  const [items, setItems] = useState<CheckoutCartItem[]>([]);

  const [shippingAddress, setShippingAddress] = useState({
    full_name: '',
    line1: '',
    line2: '',
    city: '',
    state: '',
    pincode: '',
    country: 'India',
    phone: '',
    area: '',
  });

  const [billingSameAsShipping, setBillingSameAsShipping] = useState(true);
  const [billingAddress, setBillingAddress] = useState({
    full_name: '',
    line1: '',
    line2: '',
    city: '',
    state: '',
    pincode: '',
    country: 'India',
    phone: '',
    area: '',
  });
  const [shippingFieldsLocked, setShippingFieldsLocked] = useState(false);
  const [billingFieldsLocked, setBillingFieldsLocked] = useState(false);

  const [paymentMethod, setPaymentMethod] = useState<CheckoutPaymentMethod>(FALLBACK_PAYMENT_OPTIONS[0].value);
  const [paymentOptions, setPaymentOptions] = useState<PaymentOption[]>(FALLBACK_PAYMENT_OPTIONS);
  const [shippingCharge, setShippingCharge] = useState(0);
  const [taxAmount, setTaxAmount] = useState(0);
  const [shippingLoading, setShippingLoading] = useState(false);
  const [shippingError, setShippingError] = useState('');

  const [authLoading, setAuthLoading] = useState(false);
  const [authError, setAuthError] = useState('');
  const [authMode, setAuthMode] = useState<'login' | 'create'>('login');
  const [loginForm, setLoginForm] = useState({ email: '', password: '' });
  const [registerForm, setRegisterForm] = useState({
    first_name: '',
    last_name: '',
    email: '',
    phone: '',
    password: '',
  });
  const [loginTurnstileToken, setLoginTurnstileToken] = useState('');
  const [registerTurnstileToken, setRegisterTurnstileToken] = useState('');
  const [loginTurnstileResetKey, setLoginTurnstileResetKey] = useState(0);
  const [registerTurnstileResetKey, setRegisterTurnstileResetKey] = useState(0);
  const { turnstileEnabled, turnstileSiteKey } = useTurnstileConfig();

  const [placingOrder, setPlacingOrder] = useState(false);
  const [orderError, setOrderError] = useState('');
  const [orderNotes, setOrderNotes] = useState('');
  const [contactEmail, setContactEmail] = useState('');
  const navigate = useNavigate();

  const isAuthenticated = Boolean(localStorage.getItem('auth_token'));

  useEffect(() => {
    if (authMode === 'login') {
      setLoginTurnstileToken('');
      setLoginTurnstileResetKey((prev) => prev + 1);
    } else {
      setRegisterTurnstileToken('');
      setRegisterTurnstileResetKey((prev) => prev + 1);
    }
  }, [authMode]);

  const loadCart = async () => {
    try {
      setCartLoading(true);
      setCartError('');
      const response = await cartService.getCart();
      setItems(mapCheckoutItems(response));
    } catch {
      setItems([]);
      setCartError('Unable to load cart for checkout.');
    } finally {
      setCartLoading(false);
    }
  };

  const loadPaymentMethods = async () => {
    const providerToMethod: Record<string, CheckoutPaymentMethod> = {
      cashfree: 'cashfree',
      razorpay: 'razorpay',
    };

    try {
      const response = await apiClient.get('/v1/payments/providers/');
      const rows = Array.isArray(response?.data?.data) ? (response.data.data as ProviderRow[]) : [];
      const dynamic: PaymentOption[] = [];

      for (const row of rows) {
        const provider = String(row?.name || '').toLowerCase().trim();
        const method = providerToMethod[provider];
        if (!method) continue;
        if (dynamic.some((item) => item.value === method)) continue;
        dynamic.push({
          value: method,
          label: String(row?.display_name || provider).trim() || provider,
        });
      }

      const finalOptions = (dynamic.length ? dynamic : FALLBACK_PAYMENT_OPTIONS)
        .filter((item, index, arr) => arr.findIndex((x) => x.value === item.value) === index);
      setPaymentOptions(finalOptions);
      if (!finalOptions.some((option) => option.value === paymentMethod)) {
        setPaymentMethod(finalOptions[0].value);
      }
    } catch {
      setPaymentOptions(FALLBACK_PAYMENT_OPTIONS);
      if (!FALLBACK_PAYMENT_OPTIONS.some((option) => option.value === paymentMethod)) {
        setPaymentMethod(FALLBACK_PAYMENT_OPTIONS[0].value);
      }
    }
  };

  const hydrateProfile = async () => {
    try {
      const raw = localStorage.getItem('auth_user');
      if (raw) {
        const cached = JSON.parse(raw) as AuthUserCache;
        const full = `${cached.first_name || ''} ${cached.last_name || ''}`.trim();
        setShippingAddress((prev) => ({
          ...prev,
          full_name: prev.full_name || full,
          phone: prev.phone || String(cached.phone || ''),
        }));
        setContactEmail((prev) => prev || String(cached.email || ''));
        setLoginForm((prev) => ({ ...prev, email: prev.email || String(cached.email || '') }));
      }
    } catch {
      // ignore malformed local cache
    }

    // Read current auth state at call-time to avoid stale closure values
    // right after login/create-account on this same page.
    if (!localStorage.getItem('auth_token')) return;

    try {
      const response = await apiClient.get('/v1/auth/profile/');
      const data = response?.data?.data || {};
      const full = `${data.first_name || ''} ${data.last_name || ''}`.trim();
      setShippingAddress((prev) => ({
        ...prev,
        full_name: prev.full_name || full,
        phone: prev.phone || String(data.phone || ''),
      }));
      setContactEmail((prev) => prev || String(data.email || ''));
      localStorage.setItem('auth_user', JSON.stringify(data));
    } catch {
      // ignore profile fetch issues
    }

    try {
      const response = await profileService.getAddresses();
      const addresses = Array.isArray(response?.data) ? (response.data as ProfileAddressData[]) : [];
      if (addresses.length === 0) return;

      const shipping = mapProfileAddressToCheckout(pickAddress(addresses, 'shipping'));
      const billing = mapProfileAddressToCheckout(pickAddress(addresses, 'billing'));

      if (shipping) {
        setShippingAddress((prev) => ({
          ...prev,
          full_name: prev.full_name || shipping.full_name,
          line1: prev.line1 || shipping.line1,
          line2: prev.line2 || shipping.line2,
          city: prev.city || shipping.city,
          state: prev.state || shipping.state,
          pincode: prev.pincode || shipping.pincode,
          country: prev.country || shipping.country,
          phone: prev.phone || shipping.phone,
        }));
      }

      if (billing) {
        const hasDifferentBilling =
          !!shipping &&
          (
            billing.line1 !== shipping.line1 ||
            billing.pincode !== shipping.pincode ||
            billing.city !== shipping.city ||
            billing.state !== shipping.state
          );
        if (hasDifferentBilling) setBillingSameAsShipping(false);

        setBillingAddress((prev) => ({
          ...prev,
          full_name: prev.full_name || billing.full_name,
          line1: prev.line1 || billing.line1,
          line2: prev.line2 || billing.line2,
          city: prev.city || billing.city,
          state: prev.state || billing.state,
          pincode: prev.pincode || billing.pincode,
          country: prev.country || billing.country,
          phone: prev.phone || billing.phone,
        }));
      } else if (shipping) {
        setBillingAddress((prev) => ({
          ...prev,
          full_name: prev.full_name || shipping.full_name,
          line1: prev.line1 || shipping.line1,
          line2: prev.line2 || shipping.line2,
          city: prev.city || shipping.city,
          state: prev.state || shipping.state,
          pincode: prev.pincode || shipping.pincode,
          country: prev.country || shipping.country,
          phone: prev.phone || shipping.phone,
        }));
      }
    } catch {
      // ignore saved address fetch issues
    }
  };

  useEffect(() => {
    void loadCart();
    void hydrateProfile();
    void loadPaymentMethods();
  }, []);

  useEffect(() => {
    const onCartUpdated = () => {
      void loadCart();
    };

    window.addEventListener('aurora:cart-updated', onCartUpdated as EventListener);
    return () => {
      window.removeEventListener('aurora:cart-updated', onCartUpdated as EventListener);
    };
  }, []);

  const handleShippingAutoResolved = useCallback((payload: { city: string; state: string; area: string; areas: string[]; pincode: string }, source: 'pincode' | 'gps') => {
    setShippingAddress((prev) => ({
      ...prev,
      city: payload.city || prev.city,
      state: payload.state || prev.state,
      area: payload.area || prev.area,
      pincode: source === 'gps' && prev.pincode ? prev.pincode : (payload.pincode || prev.pincode),
      line2: prev.line2 || payload.area || prev.line2,
    }));
    if (payload.city || payload.state) {
      setShippingFieldsLocked(true);
    }
  }, []);

  const handleBillingAutoResolved = useCallback((payload: { city: string; state: string; area: string; areas: string[]; pincode: string }, source: 'pincode' | 'gps') => {
    setBillingAddress((prev) => ({
      ...prev,
      city: payload.city || prev.city,
      state: payload.state || prev.state,
      area: payload.area || prev.area,
      pincode: source === 'gps' && prev.pincode ? prev.pincode : (payload.pincode || prev.pincode),
      line2: prev.line2 || payload.area || prev.line2,
    }));
    if (payload.city || payload.state) {
      setBillingFieldsLocked(true);
    }
  }, []);

  const shippingAutoFill = useAddressAutoFill({
    pincode: shippingAddress.pincode,
    onResolved: handleShippingAutoResolved,
  });

  const billingAutoFill = useAddressAutoFill({
    pincode: billingAddress.pincode,
    onResolved: handleBillingAutoResolved,
    enabled: !billingSameAsShipping,
  });

  const subtotal = useMemo(() => items.reduce((sum, item) => sum + item.lineTotal, 0), [items]);
  const total = useMemo(() => Math.max(0, subtotal + shippingCharge + taxAmount), [subtotal, shippingCharge, taxAmount]);
  const showPaymentMethodSelection = paymentOptions.length > 1;

  useEffect(() => {
    let cancelled = false;

    const timer = window.setTimeout(async () => {
      if (!items.length) {
        setShippingCharge(0);
        setTaxAmount(0);
        setShippingError('');
        return;
      }

      try {
        setShippingLoading(true);
        setShippingError('');
        const response = await cartService.calculateSurcharge({
          shipping_address: {
            country: shippingAddress.country || 'India',
            state: shippingAddress.state,
            pincode: shippingAddress.pincode,
          },
          payment_method: paymentMethod,
        });
        if (cancelled) return;
        const data = response?.data || {};
        setShippingCharge(Number(data.shipping_total || 0));
        setTaxAmount(Number(data.tax_total || 0));
      } catch {
        if (cancelled) return;
        setShippingCharge(0);
        setTaxAmount(0);
        setShippingError('Unable to fetch live shipping/tax for current address.');
      } finally {
        if (!cancelled) setShippingLoading(false);
      }
    }, 350);

    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [items, paymentMethod, shippingAddress.country, shippingAddress.state, shippingAddress.pincode]);

  const handleLogin = async () => {
    try {
      setAuthLoading(true);
      setAuthError('');
      if (turnstileEnabled && !loginTurnstileToken) {
        setAuthError('Please complete CAPTCHA verification.');
        return;
      }

      const response = await apiClient.post('/v1/auth/login/', {
        email: loginForm.email,
        password: loginForm.password,
        turnstile_token: loginTurnstileToken,
      });
      const payload = response?.data?.data || {};
      const access = String(payload.access || '');
      const refresh = String(payload.refresh || '');
      const user = payload.user;

      if (!access) {
        setAuthError('Login failed. Missing access token.');
        return;
      }

      const existingGuestSession = cartService.getGuestCartToken();

      localStorage.setItem('auth_token', access);
      if (refresh) localStorage.setItem('refresh_token', refresh);
      if (user) localStorage.setItem('auth_user', JSON.stringify(user));
      window.dispatchEvent(new CustomEvent('aurora:auth-changed'));

      try {
        await cartService.mergeGuestCart(existingGuestSession);
      } catch {
        // do not block checkout auth on merge issue
      }

      window.dispatchEvent(new CustomEvent('aurora:cart-updated'));
      await hydrateProfile();
      await loadCart();
      setLoginForm((prev) => ({ ...prev, password: '' }));
      setLoginTurnstileToken('');
      setLoginTurnstileResetKey((prev) => prev + 1);
    } catch (error: any) {
      setAuthError(error?.response?.data?.message || 'Unable to login. Please try again.');
      setLoginTurnstileToken('');
      setLoginTurnstileResetKey((prev) => prev + 1);
    } finally {
      setAuthLoading(false);
    }
  };

  const handleCreateAccount = async () => {
    try {
      setAuthLoading(true);
      setAuthError('');
      if (turnstileEnabled && !registerTurnstileToken) {
        setAuthError('Please complete CAPTCHA verification.');
        return;
      }

      await apiClient.post('/v1/auth/register/', {
        email: registerForm.email,
        password: registerForm.password,
        first_name: registerForm.first_name,
        last_name: registerForm.last_name,
        phone: registerForm.phone,
        turnstile_token: registerTurnstileToken,
      });

      if (turnstileEnabled) {
        setAuthError('Account created successfully. Please complete CAPTCHA and login to continue checkout.');
        setAuthMode('login');
        setLoginForm((prev) => ({ ...prev, email: registerForm.email, password: '' }));
        setRegisterTurnstileToken('');
        setRegisterTurnstileResetKey((prev) => prev + 1);
        return;
      }

      await apiClient.post('/v1/auth/login/', {
        email: registerForm.email,
        password: registerForm.password,
        turnstile_token: registerTurnstileToken,
      }).then(async (response) => {
        const payload = response?.data?.data || {};
        const access = String(payload.access || '');
        const refresh = String(payload.refresh || '');
        const user = payload.user;

        if (!access) {
          setAuthError('Account created, but auto-login failed. Please login manually.');
          setAuthMode('login');
          return;
        }

        const existingGuestSession = cartService.getGuestCartToken();

        localStorage.setItem('auth_token', access);
        if (refresh) localStorage.setItem('refresh_token', refresh);
        if (user) localStorage.setItem('auth_user', JSON.stringify(user));
        window.dispatchEvent(new CustomEvent('aurora:auth-changed'));

        try {
          await cartService.mergeGuestCart(existingGuestSession);
        } catch {
          // do not block checkout auth on merge issue
        }

        window.dispatchEvent(new CustomEvent('aurora:cart-updated'));
        await hydrateProfile();
        await loadCart();
        setRegisterTurnstileToken('');
        setRegisterTurnstileResetKey((prev) => prev + 1);
      });
    } catch (error: any) {
      setAuthError(error?.response?.data?.message || 'Unable to create account.');
      setRegisterTurnstileToken('');
      setRegisterTurnstileResetKey((prev) => prev + 1);
    } finally {
      setAuthLoading(false);
    }
  };

  const placeOrder = async () => {
    if (!isAuthenticated) {
      setOrderError('Please login or create an account to complete your order.');
      return;
    }

    if (!items.length) {
      setOrderError('Your cart is empty.');
      return;
    }

    const normalizedEmail = contactEmail.trim();
    const normalizedPhone = String(shippingAddress.phone || '').replace(/\D/g, '');
    const normalizedPincode = String(shippingAddress.pincode || '').replace(/\D/g, '');

    const missingFields: string[] = [];
    if (!shippingAddress.full_name.trim()) missingFields.push('Full Name');
    if (!normalizedEmail) missingFields.push('Email');
    if (!normalizedPhone) missingFields.push('Phone');
    if (!shippingAddress.line1.trim()) missingFields.push('Address Line 1');
    if (!shippingAddress.city.trim()) missingFields.push('City');
    if (!shippingAddress.state.trim()) missingFields.push('State');
    if (!normalizedPincode) missingFields.push('ZIP / Pincode');

    if (missingFields.length > 0) {
      setOrderError(`Please complete shipping details: ${missingFields.join(', ')}`);
      return;
    }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(normalizedEmail)) {
      setOrderError('Please enter a valid email address.');
      return;
    }
    if (normalizedPincode.length !== 6) {
      setOrderError('Please enter a valid 6-digit pincode.');
      return;
    }
    if (normalizedPhone.length < 10) {
      setOrderError('Please enter a valid phone number.');
      return;
    }

    try {
      setPlacingOrder(true);
      setOrderError('');

      const response = await ordersService.placeOrder({
        shipping_address: toOrderAddressPayload(shippingAddress),
        billing_address: toOrderAddressPayload(billingSameAsShipping ? shippingAddress : billingAddress),
        payment_method: paymentMethod,
        shipping_cost: shippingCharge,
        notes: orderNotes.trim(),
        guest_email: normalizedEmail,
      });

      const placedOrder = response?.data || null;
      if (placedOrder) {
        sessionStorage.setItem('aurora_last_order', JSON.stringify(placedOrder));
      } else {
        sessionStorage.removeItem('aurora_last_order');
      }
      if (placedOrder?.id) {
        const providerByMethod: Partial<Record<CheckoutPaymentMethod, string>> = {
          cashfree: 'cashfree',
          razorpay: 'razorpay',
        };
        const provider = providerByMethod[paymentMethod];

        if (!provider) {
          setOrderError('Order placed, but selected payment provider is unavailable.');
          return;
        }

        try {
          const returnUrl = `${window.location.origin}/order/thank-you?order_id=${encodeURIComponent(String(placedOrder.id))}`;
          const paymentResponse = await apiClient.post('/v1/payments/initiate/', {
            order_id: placedOrder.id,
            provider,
            return_url: returnUrl,
          });
          const txn = paymentResponse?.data?.data || null;
          const paymentTarget = String(txn?.payment_url || '').trim();

          if (provider === 'cashfree') {
            if (!paymentTarget) {
              throw new Error('Payment session could not be created.');
            }

            // Cashfree returns a payment_session_id, not a hosted URL.
            if (/^https?:\/\//i.test(paymentTarget)) {
              window.location.href = paymentTarget;
              return;
            }
            await openCashfreeCheckout(paymentTarget);
            return;
          }

          if (/^https?:\/\//i.test(paymentTarget)) {
            window.location.href = paymentTarget;
            return;
          }

          setOrderError('Order placed, but payment session could not be started. Please retry payment from your order details.');
          return;
        } catch (paymentError: any) {
          const serverMessage = paymentError?.response?.data?.message;
          setOrderError(serverMessage || 'Order placed, but payment session could not be started.');
          return;
        }
      }

      window.dispatchEvent(new CustomEvent('aurora:cart-updated'));
      await loadCart();
      navigate('/order/thank-you', { state: { order: placedOrder } });
    } catch (error: any) {
      setOrderError(error?.response?.data?.message || 'Unable to place order right now.');
    } finally {
      setPlacingOrder(false);
    }
  };

  return (
    <div className="pt-32 pb-24">
      <div className="container mx-auto px-4 max-w-6xl">
        <div className="flex items-center gap-4 mb-10">
          <Link to="/cart" className="text-muted-foreground hover:text-primary transition-colors">
            <ArrowLeft size={20} />
          </Link>
          <h1 className="text-4xl font-bold tracking-tight italic">Secure Checkout</h1>
        </div>

        {cartError ? <p className="mb-4 text-sm text-red-600">{cartError}</p> : null}

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-12">
          <div className="lg:col-span-7 space-y-8">
            {!isAuthenticated ? (
              <section className="space-y-5 rounded-2xl border bg-white p-6">
                <h2 className="text-xl font-bold">Login or Create Account</h2>
                <p className="text-sm text-muted-foreground">You need an account to complete your order.</p>

                <div className="inline-flex rounded-xl border overflow-hidden">
                  <button
                    type="button"
                    onClick={() => setAuthMode('login')}
                    className={`px-4 py-2 text-sm font-semibold ${authMode === 'login' ? 'bg-primary text-primary-foreground' : 'bg-white'}`}
                  >
                    Login
                  </button>
                  <button
                    type="button"
                    onClick={() => setAuthMode('create')}
                    className={`px-4 py-2 text-sm font-semibold ${authMode === 'create' ? 'bg-primary text-primary-foreground' : 'bg-white'}`}
                  >
                    Create Account
                  </button>
                </div>

                {authMode === 'login' ? (
                  <div className="grid grid-cols-1 gap-3">
                    <Input
                      type="email"
                      placeholder="Email"
                      value={loginForm.email}
                      onChange={(e) => setLoginForm((prev) => ({ ...prev, email: e.target.value }))}
                    />
                    <Input
                      type="password"
                      placeholder="Password"
                      value={loginForm.password}
                      onChange={(e) => setLoginForm((prev) => ({ ...prev, password: e.target.value }))}
                    />
                    <TurnstileWidget
                      enabled={turnstileEnabled}
                      siteKey={turnstileSiteKey}
                      resetKey={loginTurnstileResetKey}
                      onTokenChange={setLoginTurnstileToken}
                    />
                    <Button type="button" disabled={authLoading} onClick={() => void handleLogin()} className="rounded-xl">
                      {authLoading ? 'Signing in...' : 'Login to Continue'}
                    </Button>
                  </div>
                ) : (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    <Input
                      type="text"
                      placeholder="First Name"
                      value={registerForm.first_name}
                      onChange={(e) => setRegisterForm((prev) => ({ ...prev, first_name: e.target.value }))}
                    />
                    <Input
                      type="text"
                      placeholder="Last Name"
                      value={registerForm.last_name}
                      onChange={(e) => setRegisterForm((prev) => ({ ...prev, last_name: e.target.value }))}
                    />
                    <Input
                      type="email"
                      placeholder="Email"
                      value={registerForm.email}
                      onChange={(e) => setRegisterForm((prev) => ({ ...prev, email: e.target.value }))}
                    />
                    <Input
                      type="text"
                      placeholder="Phone"
                      value={registerForm.phone}
                      onChange={(e) => setRegisterForm((prev) => ({ ...prev, phone: e.target.value }))}
                    />
                    <div className="md:col-span-2">
                      <Input
                        type="password"
                        placeholder="Password"
                        value={registerForm.password}
                        onChange={(e) => setRegisterForm((prev) => ({ ...prev, password: e.target.value }))}
                      />
                    </div>
                    <div className="md:col-span-2">
                      <TurnstileWidget
                        enabled={turnstileEnabled}
                        siteKey={turnstileSiteKey}
                        resetKey={registerTurnstileResetKey}
                        onTokenChange={setRegisterTurnstileToken}
                      />
                    </div>
                    <div className="md:col-span-2">
                      <Button type="button" disabled={authLoading} onClick={() => void handleCreateAccount()} className="rounded-xl w-full">
                        {authLoading ? 'Creating account...' : 'Create Account & Continue'}
                      </Button>
                    </div>
                  </div>
                )}

                {authError ? <p className="text-sm text-red-600">{authError}</p> : null}
              </section>
            ) : null}

            <section className="space-y-6">
              <div className="flex items-center gap-3 text-primary">
                <h2 className="text-xl font-bold flex items-center gap-2">
                  <Truck size={20} /> Shipping Information
                </h2>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="md:col-span-2 space-y-2">
                  <label className="text-xs font-bold uppercase tracking-widest text-muted-foreground ml-1">Full Name</label>
                  <Input
                    placeholder="Your name"
                    className="rounded-xl shadow-none"
                    value={shippingAddress.full_name}
                    onChange={(e) => setShippingAddress((prev) => ({ ...prev, full_name: e.target.value }))}
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-xs font-bold uppercase tracking-widest text-muted-foreground ml-1">Email</label>
                  <Input
                    type="email"
                    placeholder="you@example.com"
                    className="rounded-xl shadow-none"
                    value={contactEmail}
                    onChange={(e) => setContactEmail(e.target.value)}
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-xs font-bold uppercase tracking-widest text-muted-foreground ml-1">Phone</label>
                  <Input
                    placeholder="9876543210"
                    className="rounded-xl shadow-none"
                    value={shippingAddress.phone}
                    onChange={(e) => setShippingAddress((prev) => ({ ...prev, phone: e.target.value }))}
                  />
                </div>
                <div className="md:col-span-2 space-y-2">
                  <label className="text-xs font-bold uppercase tracking-widest text-muted-foreground ml-1">Address Line 1</label>
                  <Input
                    placeholder="123 Aurora St."
                    className="rounded-xl shadow-none"
                    value={shippingAddress.line1}
                    onChange={(e) => setShippingAddress((prev) => ({ ...prev, line1: e.target.value }))}
                  />
                </div>
                <div className="md:col-span-2 space-y-2">
                  <label className="text-xs font-bold uppercase tracking-widest text-muted-foreground ml-1">Address Line 2</label>
                  <Input
                    placeholder="Apartment, suite, landmark"
                    className="rounded-xl shadow-none"
                    value={shippingAddress.line2}
                    onChange={(e) => setShippingAddress((prev) => ({ ...prev, line2: e.target.value }))}
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-xs font-bold uppercase tracking-widest text-muted-foreground ml-1">ZIP / Pincode</label>
                  <Input
                    placeholder="560001"
                    className="rounded-xl shadow-none"
                    value={shippingAddress.pincode}
                    onChange={(e) =>
                      setShippingAddress((prev) => ({ ...prev, pincode: e.target.value.replace(/\D/g, '').slice(0, 6) }))
                    }
                  />
                  {shippingAutoFill.isLoading ? <p className="text-xs text-muted-foreground">Detecting location...</p> : null}
                  {shippingAutoFill.locationLabel ? <p className="text-xs text-emerald-700">{shippingAutoFill.locationLabel}</p> : null}
                  {shippingAutoFill.error ? <p className="text-xs text-amber-700">{shippingAutoFill.error}</p> : null}
                  <button
                    type="button"
                    onClick={() => void shippingAutoFill.detectFromGps()}
                    className="text-xs text-primary underline underline-offset-4 disabled:text-muted-foreground"
                    disabled={shippingAutoFill.isGpsLoading}
                  >
                    {shippingAutoFill.isGpsLoading ? 'Detecting from GPS...' : 'Use current location'}
                  </button>
                </div>
                {shippingAutoFill.result.areas.length > 1 ? (
                  <div className="space-y-2">
                    <label className="text-xs font-bold uppercase tracking-widest text-muted-foreground ml-1">Area / Post Office</label>
                    <select
                      value={shippingAddress.area}
                      onChange={(e) =>
                        setShippingAddress((prev) => ({
                          ...prev,
                          area: e.target.value,
                          line2: prev.line2 || e.target.value,
                        }))
                      }
                      className="flex h-11 w-full rounded-xl border border-input bg-transparent px-4 py-2 text-sm"
                    >
                      <option value="">Select area</option>
                      {shippingAutoFill.result.areas.map((area) => (
                        <option key={area} value={area}>{area}</option>
                      ))}
                    </select>
                  </div>
                ) : null}
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <label className="text-xs font-bold uppercase tracking-widest text-muted-foreground ml-1">City</label>
                    {shippingFieldsLocked ? (
                      <button type="button" className="text-[11px] text-primary underline" onClick={() => setShippingFieldsLocked(false)}>
                        Edit manually
                      </button>
                    ) : null}
                  </div>
                  <Input
                    placeholder="City"
                    className="rounded-xl shadow-none"
                    value={shippingAddress.city}
                    disabled={shippingFieldsLocked}
                    onChange={(e) => setShippingAddress((prev) => ({ ...prev, city: e.target.value }))}
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-xs font-bold uppercase tracking-widest text-muted-foreground ml-1">State</label>
                  <Input
                    placeholder="State / Province"
                    className="rounded-xl shadow-none"
                    value={shippingAddress.state}
                    disabled={shippingFieldsLocked}
                    onChange={(e) => setShippingAddress((prev) => ({ ...prev, state: e.target.value }))}
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-xs font-bold uppercase tracking-widest text-muted-foreground ml-1">Country</label>
                  <Input
                    placeholder="India"
                    className="rounded-xl shadow-none"
                    value={shippingAddress.country}
                    onChange={(e) => setShippingAddress((prev) => ({ ...prev, country: e.target.value }))}
                  />
                </div>
              </div>
            </section>

            <section className="space-y-4 pt-4 border-t">
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-bold">Billing Address</h3>
                <label className="inline-flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={billingSameAsShipping}
                    onChange={(e) => setBillingSameAsShipping(e.target.checked)}
                  />
                  Same as shipping
                </label>
              </div>

              {!billingSameAsShipping ? (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  <Input placeholder="Full Name" value={billingAddress.full_name} onChange={(e) => setBillingAddress((p) => ({ ...p, full_name: e.target.value }))} />
                  <Input placeholder="Phone" value={billingAddress.phone} onChange={(e) => setBillingAddress((p) => ({ ...p, phone: e.target.value }))} />
                  <div className="md:col-span-2"><Input placeholder="Address Line 1" value={billingAddress.line1} onChange={(e) => setBillingAddress((p) => ({ ...p, line1: e.target.value }))} /></div>
                  <div className="md:col-span-2"><Input placeholder="Address Line 2" value={billingAddress.line2} onChange={(e) => setBillingAddress((p) => ({ ...p, line2: e.target.value }))} /></div>
                  <div className="md:col-span-2 space-y-2">
                    <Input
                      placeholder="Pincode"
                      value={billingAddress.pincode}
                      onChange={(e) =>
                        setBillingAddress((p) => ({ ...p, pincode: e.target.value.replace(/\D/g, '').slice(0, 6) }))
                      }
                    />
                    {billingAutoFill.isLoading ? <p className="text-xs text-muted-foreground">Detecting location...</p> : null}
                    {billingAutoFill.locationLabel ? <p className="text-xs text-emerald-700">{billingAutoFill.locationLabel}</p> : null}
                    {billingAutoFill.error ? <p className="text-xs text-amber-700">{billingAutoFill.error}</p> : null}
                  </div>
                  {billingAutoFill.result.areas.length > 1 ? (
                    <select
                      value={billingAddress.area}
                      onChange={(e) =>
                        setBillingAddress((p) => ({
                          ...p,
                          area: e.target.value,
                          line2: p.line2 || e.target.value,
                        }))
                      }
                      className="md:col-span-2 flex h-11 w-full rounded-xl border border-input bg-transparent px-4 py-2 text-sm"
                    >
                      <option value="">Select area</option>
                      {billingAutoFill.result.areas.map((area) => (
                        <option key={area} value={area}>{area}</option>
                      ))}
                    </select>
                  ) : null}
                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="text-xs text-muted-foreground">City</span>
                      {billingFieldsLocked ? (
                        <button type="button" className="text-[11px] text-primary underline" onClick={() => setBillingFieldsLocked(false)}>
                          Edit manually
                        </button>
                      ) : null}
                    </div>
                    <Input
                      placeholder="City"
                      value={billingAddress.city}
                      disabled={billingFieldsLocked}
                      onChange={(e) => setBillingAddress((p) => ({ ...p, city: e.target.value }))}
                    />
                  </div>
                  <Input
                    placeholder="State"
                    value={billingAddress.state}
                    disabled={billingFieldsLocked}
                    onChange={(e) => setBillingAddress((p) => ({ ...p, state: e.target.value }))}
                  />
                </div>
              ) : null}
            </section>

            {showPaymentMethodSelection ? (
              <section className="space-y-5 pt-6 border-t">
                <div className="flex items-center gap-3 text-muted-foreground">
                  <div className="w-8 h-8 rounded-full bg-muted flex items-center justify-center font-bold text-sm">2</div>
                  <h2 className="text-xl font-bold flex items-center gap-2">
                    <CreditCard size={20} /> Payment Method
                  </h2>
                </div>

                <div className="grid gap-3">
                  {paymentOptions.map((option) => (
                    <label key={option.value} className="inline-flex items-center justify-between rounded-xl border p-3">
                      <span className="font-medium">{option.label}</span>
                      <input
                        type="radio"
                        checked={paymentMethod === option.value}
                        onChange={() => setPaymentMethod(option.value)}
                      />
                    </label>
                  ))}
                </div>

                <div className="p-4 border rounded-xl bg-muted/30 text-sm text-muted-foreground flex gap-2">
                  <ShieldCheck size={18} className="shrink-0 mt-0.5" />
                  <p>Payment integration remains secure and will follow selected gateway flow after order placement.</p>
                </div>
              </section>
            ) : null}

            <section className="space-y-3 pt-6 border-t">
              <h3 className="text-lg font-bold">Order Notes (Optional)</h3>
              <textarea
                value={orderNotes}
                onChange={(e) => setOrderNotes(e.target.value)}
                placeholder="Any delivery instruction or note for this order"
                rows={3}
                maxLength={500}
                className="w-full rounded-xl border border-input bg-transparent px-4 py-3 text-sm outline-none focus:ring-2 focus:ring-primary/25"
              />
              <p className="text-xs text-muted-foreground">{orderNotes.length}/500</p>
            </section>
          </div>

          <div className="lg:col-span-5">
            <Card className="p-8 sticky top-32 space-y-6 bg-muted/30 border-none shadow-none">
              <h2 className="text-xl font-bold tracking-tight italic flex items-center gap-2 border-b pb-4">
                <ClipboardList size={20} /> Review Order
              </h2>

              {cartLoading ? (
                <p className="text-sm text-muted-foreground">Loading cart...</p>
              ) : items.length === 0 ? (
                <p className="text-sm text-muted-foreground">Your cart is empty. Add products to continue checkout.</p>
              ) : (
                <div className="space-y-4 max-h-[320px] overflow-auto pr-1">
                  {items.map((item) => (
                    <div key={item.id} className="flex gap-4">
                      <div className="w-16 h-20 rounded-lg overflow-hidden bg-muted border">
                        <img src={item.thumbnail || FALLBACK_IMAGE} alt={item.productName} className="w-full h-full object-cover" />
                      </div>
                      <div className="flex-1 space-y-1">
                        <p className="text-sm font-bold truncate">{item.productName}</p>
                        <p className="text-xs text-muted-foreground truncate">{item.variantName}</p>
                        <p className="text-xs text-muted-foreground">Qty: {item.quantity} • {formatCurrency(item.lineTotal)}</p>
                      </div>
                    </div>
                  ))}
                </div>
              )}

              <div className="pt-4 border-t space-y-4">
                <div className="flex justify-between text-sm">
                  <span className="text-muted-foreground">Subtotal</span>
                  <span className="font-medium">{formatCurrency(subtotal)}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-muted-foreground">Shipping (Live)</span>
                  <span className="font-medium">
                    {shippingLoading ? 'Calculating...' : shippingCharge === 0 ? 'Free' : formatCurrency(shippingCharge)}
                  </span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-muted-foreground">Estimated Tax (Live)</span>
                  <span className="font-medium">{formatCurrency(taxAmount)}</span>
                </div>
                {shippingError ? <p className="text-xs text-amber-700">{shippingError}</p> : null}
                <div className="pt-4 border-t flex justify-between items-center text-lg font-bold">
                  <span>Total Amount</span>
                  <span className="text-2xl text-primary">{formatCurrency(total)}</span>
                </div>
              </div>

              {orderError ? <p className="text-sm text-red-600">{orderError}</p> : null}

              <Button
                size="lg"
                className="w-full rounded-xl h-14 text-lg"
                disabled={!isAuthenticated || placingOrder || cartLoading || items.length === 0}
                onClick={() => void placeOrder()}
              >
                {placingOrder ? 'Placing Order...' : isAuthenticated ? 'Complete Purchase' : 'Login to Complete Order'}
              </Button>

              <p className="text-[10px] text-center text-muted-foreground leading-relaxed">
                By completing your purchase you agree to our Terms of Service and Refund Policy.
              </p>
            </Card>
          </div>
        </div>
      </div>
    </div>
  );
};
