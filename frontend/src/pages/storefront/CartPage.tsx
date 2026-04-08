import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight, Minus, Plus, ShoppingBag, Trash2 } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { useCurrency } from '@/hooks/useCurrency';
import { gsap, shouldAnimate } from '@/animations/gsapConfig';
import { useSectionTransition } from '@/animations/useSectionTransition';
import { useStagger } from '@/animations/useStagger';
import cartService, { type CartCouponSummary } from '@/services/api/cart';
import { useAddressAutoFill } from '@/hooks/useAddressAutoFill';
import { AvailableCouponsPanel } from '@/components/storefront/coupons/AvailableCouponsPanel';

interface CartItem {
  id: string;
  variantId: string;
  productSlug: string;
  name: string;
  price: number;
  image: string;
  variant: string;
  quantity: number;
}

const FALLBACK_IMAGE = 'https://placehold.co/600x600/f3f4f6/517b4b?text=Product';

const mapCartItems = (payload: any): CartItem[] => {
  const items = payload?.data?.items;
  if (!Array.isArray(items)) return [];

  return items.map((item: any) => ({
    id: String(item?.id || ''),
    variantId: String(item?.variant_id || ''),
    productSlug: String(item?.product_slug || ''),
    name: String(item?.product_name || 'Product'),
    price: Number(item?.unit_price || 0),
    image: String(item?.thumbnail || FALLBACK_IMAGE),
    variant: String(item?.variant_name || 'Standard'),
    quantity: Math.max(1, Number(item?.quantity || 1)),
  }));
};

export const CartPage: React.FC = () => {
  const [items, setItems] = useState<CartItem[]>([]);
  const [cartLoading, setCartLoading] = useState(true);
  const [couponOpen, setCouponOpen] = useState(false);
  const [couponCode, setCouponCode] = useState('');
  const [appliedCouponCode, setAppliedCouponCode] = useState('');
  const [discountAmount, setDiscountAmount] = useState(0);
  const [couponError, setCouponError] = useState('');
  const [couponApplyLoading, setCouponApplyLoading] = useState(false);
  const [couponListOpen, setCouponListOpen] = useState(false);
  const [couponListLoading, setCouponListLoading] = useState(false);
  const [couponListError, setCouponListError] = useState('');
  const [availableCoupons, setAvailableCoupons] = useState<CartCouponSummary[]>([]);
  const [applyingCouponCode, setApplyingCouponCode] = useState('');
  const [shippingAddress, setShippingAddress] = useState({
    country: 'India',
    state: 'Odisha',
    pincode: '',
    city: '',
    area: '',
  });
  const [stateLocked, setStateLocked] = useState(false);
  const [shippingCharge, setShippingCharge] = useState(0);
  const [taxAmount, setTaxAmount] = useState(0);
  const [shippingLoading, setShippingLoading] = useState(false);
  const [shippingError, setShippingError] = useState('');
  const rootRef = useRef<HTMLDivElement>(null);
  const listRef = useRef<HTMLDivElement>(null);
  const rowRefs = useRef<Record<string, HTMLTableRowElement | null>>({});
  const { formatCurrency } = useCurrency();

  const handleAutoResolved = useCallback((payload: { city: string; state: string; area: string; areas: string[]; pincode: string }, source: 'pincode' | 'gps') => {
    setShippingAddress((prev) => ({
      ...prev,
      city: payload.city || prev.city,
      state: payload.state || prev.state,
      area: payload.area || prev.area,
      pincode: source === 'gps' && prev.pincode ? prev.pincode : (payload.pincode || prev.pincode),
    }));
    if (payload.state) {
      setStateLocked(true);
    }
  }, []);

  const autoFill = useAddressAutoFill({
    pincode: shippingAddress.pincode,
    onResolved: handleAutoResolved,
  });
  const showAutoDetectError =
    Boolean(autoFill.error) &&
    !(shippingAddress.state.trim() || shippingAddress.city.trim());

  useSectionTransition(rootRef);
  useStagger(listRef, { itemSelector: '[data-cart-item]', stagger: 0.06, y: 12, duration: 0.45 });

  const syncCartPricing = (payload: any) => {
    const data = payload?.data || {};
    const nextCode = String(data?.coupon_code || '').trim();
    setAppliedCouponCode(nextCode);
    setCouponCode((prev) => prev || nextCode);
    setDiscountAmount(Number(data?.discount || 0));
  };

  const loadCart = async () => {
    try {
      const response = await cartService.getCart();
      setItems(mapCartItems(response));
      syncCartPricing(response);
    } catch {
      setItems([]);
      setAppliedCouponCode('');
      setDiscountAmount(0);
    } finally {
      setCartLoading(false);
    }
  };

  const loadCoupons = async () => {
    try {
      setCouponListLoading(true);
      setCouponListError('');
      const response = await cartService.listCoupons();
      setAvailableCoupons(Array.isArray(response?.data?.coupons) ? response.data.coupons : []);
    } catch (error: any) {
      setAvailableCoupons([]);
      setCouponListError(error?.response?.data?.message || 'Unable to load coupons right now.');
    } finally {
      setCouponListLoading(false);
    }
  };

  useEffect(() => {
    loadCart();
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

  const subtotal = useMemo(() => items.reduce((acc, item) => acc + item.price * item.quantity, 0), [items]);
  const total = Math.max(0, subtotal + shippingCharge + taxAmount - discountAmount);

  useEffect(() => {
    if (!couponListOpen) return;
    void loadCoupons();
  }, [couponListOpen, items.length, subtotal, appliedCouponCode]);

  useEffect(() => {
    let isCancelled = false;
    const timer = window.setTimeout(async () => {
      if (items.length === 0) {
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
          payment_method: 'cod',
        });
        const data = response?.data || {};
        if (!isCancelled) {
          setShippingCharge(Number(data.shipping_total || 0));
          setTaxAmount(Number(data.tax_total || 0));
        }
      } catch {
        if (!isCancelled) {
          setShippingCharge(0);
          setTaxAmount(0);
          setShippingError('Live shipping unavailable for current address/cart.');
        }
      } finally {
        if (!isCancelled) setShippingLoading(false);
      }
    }, 350);

    return () => {
      isCancelled = true;
      window.clearTimeout(timer);
    };
  }, [items, shippingAddress.country, shippingAddress.state, shippingAddress.pincode]);

  const applyCoupon = async (codeOverride?: string) => {
    const normalized = (codeOverride || couponCode).trim().toUpperCase();
    if (!normalized) {
      setCouponError('Enter a coupon code.');
      return;
    }

    try {
      setCouponApplyLoading(true);
      setApplyingCouponCode(codeOverride ? normalized : '');
      setCouponError('');
      const response = await cartService.applyCoupon(normalized);
      setItems(mapCartItems(response));
      syncCartPricing(response);
      setCouponCode(normalized);
      if (couponListOpen) {
        void loadCoupons();
      }
    } catch (error: any) {
      setCouponError(error?.response?.data?.message || 'Invalid coupon code');
    } finally {
      setCouponApplyLoading(false);
      setApplyingCouponCode('');
    }
  };

  const clearCoupon = async () => {
    try {
      setCouponApplyLoading(true);
      setCouponError('');
      const response = await cartService.removeCoupon();
      setItems(mapCartItems(response));
      syncCartPricing(response);
      setCouponCode('');
      if (couponListOpen) {
        void loadCoupons();
      }
    } catch (error: any) {
      setCouponError(error?.response?.data?.message || 'Unable to remove coupon.');
    } finally {
      setCouponApplyLoading(false);
    }
  };

  const updateQuantity = async (id: string, delta: number) => {
    const current = items.find((item) => item.id === id);
    if (!current) return;

    const nextQuantity = Math.max(1, current.quantity + delta);

    try {
      const response = await cartService.updateItem(id, nextQuantity);
      setItems(mapCartItems(response));
      window.dispatchEvent(new CustomEvent('aurora:cart-updated'));
    } catch {
      // keep previous state
    }

    const row = rowRefs.current[id];
    if (row && shouldAnimate()) {
      gsap.fromTo(row, { scale: 1 }, { scale: 1.01, duration: 0.12, yoyo: true, repeat: 1, ease: 'power1.out' });
    }
  };

  const removeItem = async (id: string) => {
    const finalize = async () => {
      try {
        const response = await cartService.removeItem(id);
        setItems(mapCartItems(response));
        window.dispatchEvent(new CustomEvent('aurora:cart-updated'));
      } catch {
        // keep previous state
      }
    };

    const row = rowRefs.current[id];
    if (row && shouldAnimate()) {
      gsap.to(row, {
        autoAlpha: 0,
        y: -8,
        duration: 0.24,
        ease: 'power2.inOut',
        onComplete: () => {
          void finalize();
        },
      });
      return;
    }

    await finalize();
  };

  if (cartLoading) {
    return (
      <div className="pt-36 pb-28 text-center">
        <div className="container mx-auto px-4 space-y-5">
          <h1 className="text-2xl font-bold">Loading cart...</h1>
        </div>
      </div>
    );
  }

  if (items.length === 0) {
    return (
      <div className="pt-36 pb-28 text-center">
        <div className="container mx-auto px-4 space-y-5">
          <div className="w-20 h-20 rounded-full bg-muted mx-auto flex items-center justify-center text-muted-foreground">
            <ShoppingBag size={32} />
          </div>
          <h1 className="text-3xl font-bold">Your Cart Is Empty</h1>
          <p className="text-muted-foreground max-w-sm mx-auto">
            Looks like you have not added anything yet.
          </p>
          <Link to="/products/">
            <Button size="lg" className="rounded-xl px-10">Continue Shopping</Button>
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div ref={rootRef} className="pt-32 pb-24 bg-transparent">
      <div className="container mx-auto px-4">
        <div className="mb-8">
          <h1 className="text-4xl font-bold tracking-tight text-foreground">Cart</h1>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          <aside className="lg:col-span-4">
            <div className="rounded-3xl border border-border bg-white/85 backdrop-blur-sm p-5 md:p-6 space-y-5">
              <h2 className="text-xl font-bold text-foreground">Summary</h2>

              <div className="space-y-3">
                <div>
                  <label className="mb-1.5 block text-sm font-medium text-foreground">Country</label>
                  <input
                    type="text"
                    value={shippingAddress.country}
                    onChange={(event) => setShippingAddress((prev) => ({ ...prev, country: event.target.value }))}
                    className="w-full h-11 rounded-xl border border-border bg-white px-3 text-sm"
                  />
                </div>
                <div>
                  <label className="mb-1.5 block text-sm font-medium text-foreground">State / Province</label>
                  <input
                    type="text"
                    value={shippingAddress.state}
                    onChange={(event) => setShippingAddress((prev) => ({ ...prev, state: event.target.value }))}
                    placeholder="Karnataka"
                    className="w-full h-11 rounded-xl border border-border bg-white px-3 text-sm"
                    disabled={stateLocked}
                  />
                  {stateLocked ? (
                    <button
                      type="button"
                      onClick={() => setStateLocked(false)}
                      className="mt-1 text-[11px] text-primary underline"
                    >
                      Edit manually
                    </button>
                  ) : null}
                </div>
                <div>
                  <label className="mb-1.5 block text-sm font-medium text-foreground">Zip / Postal Code</label>
                  <input
                    type="text"
                    value={shippingAddress.pincode}
                    onChange={(event) =>
                      setShippingAddress((prev) => ({ ...prev, pincode: event.target.value.replace(/\D/g, '').slice(0, 6) }))
                    }
                    placeholder="560001"
                    className="w-full h-11 rounded-xl border border-border bg-white px-3 text-sm"
                  />
                  {autoFill.isLoading ? <p className="mt-1 text-xs text-muted-foreground">Detecting location...</p> : null}
                  {autoFill.locationLabel ? <p className="mt-1 text-xs text-emerald-700">{autoFill.locationLabel}</p> : null}
                  {showAutoDetectError ? <p className="mt-1 text-xs text-amber-700">{autoFill.error}</p> : null}
                  <button
                    type="button"
                    onClick={() => void autoFill.detectFromGps()}
                    className="mt-1 text-xs text-primary underline underline-offset-4 disabled:text-muted-foreground"
                    disabled={autoFill.isGpsLoading}
                  >
                    {autoFill.isGpsLoading ? 'Detecting from GPS...' : 'Use current location'}
                  </button>
                </div>
              </div>

              <div className="rounded-2xl border border-border/80 bg-white p-4 space-y-2.5">
                <div className="flex items-center justify-between text-sm">
                  <span className="text-muted-foreground">Sub-Total</span>
                  <span className="font-semibold text-foreground">{formatCurrency(subtotal)}</span>
                </div>
                <div className="flex items-center justify-between text-sm">
                  <span className="text-muted-foreground">Delivery Charges (Live)</span>
                  <span className="font-semibold text-foreground">
                    {shippingLoading ? 'Calculating...' : shippingCharge === 0 ? 'Free' : formatCurrency(shippingCharge)}
                  </span>
                </div>
                <div className="flex items-center justify-between text-sm">
                  <span className="text-muted-foreground">Estimated Tax (Live)</span>
                  <span className="font-semibold text-foreground">{formatCurrency(taxAmount)}</span>
                </div>
                <div className="flex items-center justify-between text-sm">
                  <span className="text-muted-foreground">Coupon Discount</span>
                  <button
                    type="button"
                    onClick={() => setCouponOpen((prev) => !prev)}
                    className="font-semibold text-primary hover:underline"
                  >
                    {appliedCouponCode ? `${appliedCouponCode} Applied` : 'Apply Coupon'}
                  </button>
                </div>
                {couponOpen ? (
                  <div className="rounded-xl border border-border bg-white p-2.5 space-y-2.5">
                    <div className="flex items-center gap-2">
                      <input
                        type="text"
                        value={couponCode}
                        onChange={(event) => setCouponCode(event.target.value)}
                        placeholder="Enter coupon code"
                        className={`h-9 flex-1 rounded-lg border px-3 text-sm ${couponError ? 'border-red-500 focus:ring-2 focus:ring-red-200' : 'border-border'}`}
                      />
                      <Button
                        type="button"
                        onClick={() => void applyCoupon()}
                        disabled={couponApplyLoading}
                        className="h-9 rounded-lg px-3 text-xs"
                      >
                        {couponApplyLoading ? 'Applying...' : 'Apply'}
                      </Button>
                      {appliedCouponCode ? (
                        <Button type="button" variant="outline" onClick={() => void clearCoupon()} className="h-9 rounded-lg px-3 text-xs">
                          Reset
                        </Button>
                      ) : null}
                    </div>
                    {couponListOpen ? (
                      <button
                        type="button"
                        onClick={() => setCouponListOpen(false)}
                        className="text-xs font-semibold text-primary hover:underline"
                      >
                        Hide available coupons
                      </button>
                    ) : (
                      <button
                        type="button"
                        onClick={() => {
                          setCouponListOpen(true);
                          void loadCoupons();
                        }}
                        className="text-xs font-semibold text-primary hover:underline"
                      >
                        View all available coupons
                      </button>
                    )}
                    {couponListOpen ? (
                      <>
                        <AvailableCouponsPanel
                          coupons={availableCoupons}
                          loading={couponListLoading}
                          applyingCode={applyingCouponCode}
                          onApply={(code) => {
                            void applyCoupon(code);
                          }}
                        />
                        {couponListError ? <p className="text-xs text-red-600">{couponListError}</p> : null}
                      </>
                    ) : null}
                    {couponError ? <p className="mt-1.5 text-xs text-red-600">{couponError}</p> : null}
                  </div>
                ) : null}
                {shippingError ? <p className="text-xs text-amber-700">{shippingError}</p> : null}
                <div className="mt-2 border-t border-border pt-2.5 flex items-center justify-between">
                  <span className="font-semibold text-foreground">Total Amount</span>
                  <span className="text-xl font-bold text-primary">{formatCurrency(total)}</span>
                </div>
              </div>
            </div>
          </aside>

          <section className="lg:col-span-8">
            <div ref={listRef} className="rounded-3xl border border-border bg-white/85 backdrop-blur-sm overflow-hidden">
              <div className="md:hidden divide-y divide-border/70">
                {items.map((item) => (
                  <article
                    key={item.id}
                    data-cart-item
                    className="p-4"
                  >
                    <div className="flex gap-3">
                      <Link
                        to={item.productSlug ? `/product/${item.productSlug}` : '/products/'}
                        className="shrink-0"
                      >
                        <img
                          src={item.image}
                          alt={item.name}
                          className="h-24 w-20 rounded-2xl border border-border object-cover"
                        />
                      </Link>

                      <div className="min-w-0 flex-1">
                        <Link
                          to={item.productSlug ? `/product/${item.productSlug}` : '/products/'}
                          className="block"
                        >
                          <p className="line-clamp-2 text-sm font-semibold text-foreground">{item.name}</p>
                          <p className="mt-1 text-xs text-muted-foreground">{item.variant}</p>
                        </Link>

                        <div className="mt-3 flex items-center justify-between gap-3">
                          <div>
                            <p className="text-sm font-semibold text-foreground">{formatCurrency(item.price)}</p>
                            <p className="mt-0.5 text-xs text-muted-foreground">
                              Total: {formatCurrency(item.price * item.quantity)}
                            </p>
                          </div>

                          <div className="inline-flex items-center rounded-xl border border-border bg-white overflow-hidden">
                            <button
                              type="button"
                              onClick={() => void updateQuantity(item.id, -1)}
                              className="px-3 py-2 hover:bg-muted"
                              aria-label={`Decrease quantity of ${item.name}`}
                            >
                              <Minus size={14} />
                            </button>
                            <span className="w-10 text-center text-sm font-semibold">{item.quantity}</span>
                            <button
                              type="button"
                              onClick={() => void updateQuantity(item.id, 1)}
                              className="px-3 py-2 hover:bg-muted"
                              aria-label={`Increase quantity of ${item.name}`}
                            >
                              <Plus size={14} />
                            </button>
                          </div>
                        </div>

                        <div className="mt-3 flex items-center justify-between">
                          <span className="text-xs text-muted-foreground">Qty: {item.quantity}</span>
                          <button
                            type="button"
                            onClick={() => void removeItem(item.id)}
                            className="inline-flex items-center gap-1 text-sm font-medium text-muted-foreground transition-colors hover:text-red-600"
                          >
                            <Trash2 size={16} />
                            Remove
                          </button>
                        </div>
                      </div>
                    </div>
                  </article>
                ))}
              </div>

              <div className="hidden md:block overflow-x-auto">
                <table className="w-full min-w-[760px]">
                  <thead>
                    <tr className="border-b border-border bg-white/90">
                      <th className="px-4 py-3 text-left text-sm font-semibold text-foreground">Product</th>
                      <th className="px-4 py-3 text-left text-sm font-semibold text-foreground">Price</th>
                      <th className="px-4 py-3 text-left text-sm font-semibold text-foreground">Quantity</th>
                      <th className="px-4 py-3 text-left text-sm font-semibold text-foreground">Total</th>
                      <th className="px-4 py-3 text-left text-sm font-semibold text-foreground">Remove</th>
                    </tr>
                  </thead>
                  <tbody>
                    {items.map((item) => (
                      <tr
                        key={item.id}
                        ref={(node) => {
                          rowRefs.current[item.id] = node;
                        }}
                        className="border-b border-border/70 last:border-b-0"
                        data-cart-item
                      >
                        <td className="px-4 py-3">
                          <Link to={item.productSlug ? `/product/${item.productSlug}` : '/products/'} className="flex items-center gap-3">
                            <img src={item.image} alt={item.name} className="h-16 w-16 rounded-xl border border-border object-cover" />
                            <div>
                              <p className="font-medium text-foreground">{item.name}</p>
                              <p className="text-xs text-muted-foreground">{item.variant}</p>
                            </div>
                          </Link>
                        </td>
                        <td className="px-4 py-3 text-sm font-medium text-foreground">{formatCurrency(item.price)}</td>
                        <td className="px-4 py-3">
                          <div className="inline-flex items-center rounded-xl border border-border bg-white overflow-hidden">
                            <button type="button" onClick={() => void updateQuantity(item.id, -1)} className="px-2.5 py-2 hover:bg-muted">
                              <Minus size={14} />
                            </button>
                            <span className="w-9 text-center text-sm font-semibold">{item.quantity}</span>
                            <button type="button" onClick={() => void updateQuantity(item.id, 1)} className="px-2.5 py-2 hover:bg-muted">
                              <Plus size={14} />
                            </button>
                          </div>
                        </td>
                        <td className="px-4 py-3 text-sm font-semibold text-foreground">{formatCurrency(item.price * item.quantity)}</td>
                        <td className="px-4 py-3">
                          <button type="button" onClick={() => void removeItem(item.id)} className="inline-flex items-center text-muted-foreground hover:text-red-600 transition-colors">
                            <Trash2 size={18} />
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            <div className="mt-5 hidden md:block">
              <Link to="/checkout">
                <Button className="h-11 rounded-xl px-6 bg-primary text-primary-foreground hover:bg-primary/90">
                  Check Out <ArrowRight size={16} />
                </Button>
              </Link>
            </div>
          </section>
        </div>
      </div>

      <div className="fixed inset-x-0 bottom-0 z-30 border-t border-border bg-white/95 px-4 py-3 shadow-[0_-10px_30px_rgba(15,23,42,0.08)] backdrop-blur md:hidden">
        <div className="mx-auto flex max-w-3xl items-center justify-between gap-3">
          <div className="min-w-0">
            <p className="text-xs text-muted-foreground">{items.length} item{items.length === 1 ? '' : 's'}</p>
            <p className="truncate text-base font-bold text-foreground">{formatCurrency(total)}</p>
          </div>
          <Link to="/checkout" className="shrink-0">
            <Button className="h-11 rounded-xl px-5 bg-primary text-primary-foreground hover:bg-primary/90">
              Check Out <ArrowRight size={16} />
            </Button>
          </Link>
        </div>
      </div>
    </div>
  );
};
