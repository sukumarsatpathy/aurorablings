import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { ChevronRight, Minus, Plus, ShoppingCart, Star } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { Input } from '@/components/ui/Input';
import catalogService, { type CatalogProductDetail } from '@/services/api/catalog';
import notifyService, { type NotifySubscriptionPayload } from '@/services/api/notify';
import cartService from '@/services/api/cart';
import { useCurrency } from '@/hooks/useCurrency';
import { ProductReviewsSection } from '@/components/storefront/reviews/ProductReviewsSection';
import { useStagger } from '@/animations/useStagger';
import { applySeo, stripHtml, truncateText } from '@/lib/seo';

const getBackendOrigin = (): string => {
  const baseURL = import.meta.env.VITE_API_BASE_URL as string | undefined;
  const explicitBackendOrigin = import.meta.env.VITE_BACKEND_ORIGIN as string | undefined;

  if (explicitBackendOrigin) {
    try {
      return new URL(explicitBackendOrigin).origin;
    } catch {
      // ignore invalid env and continue fallback
    }
  }

  try {
    if (baseURL) {
      const parsed = new URL(baseURL, window.location.origin);
      if (/^https?:$/i.test(parsed.protocol) && parsed.origin !== window.location.origin) {
        return parsed.origin;
      }
    }
  } catch {
    // ignore and fallback
  }

  if (['localhost', '127.0.0.1'].includes(window.location.hostname)) {
    return `${window.location.protocol}//${window.location.hostname}:8000`;
  }

  return window.location.origin;
};

const normalizeAssetUrl = (raw?: string | null): string => {
  const value = String(raw || '').trim();
  if (!value) return '';
  const backendOrigin = getBackendOrigin();

  if (value.startsWith('/')) {
    return `${backendOrigin}${value}`;
  }

  try {
    const parsed = new URL(value);
    if (['backend', 'backend-1', 'web', 'api'].includes(parsed.hostname)) {
      parsed.protocol = window.location.protocol;
      parsed.hostname = window.location.hostname;
      if (!parsed.port) parsed.port = '8000';
      return parsed.toString();
    }
    return value;
  } catch {
    return value;
  }
};

const extractProduct = (payload: any): CatalogProductDetail | null => {
  if (!payload) return null;
  if (payload?.data && typeof payload.data === 'object') return payload.data as CatalogProductDetail;
  if (typeof payload === 'object' && payload.id) return payload as CatalogProductDetail;
  return null;
};

export const ProductDetailPage: React.FC = () => {
  const bulletIconUrl = 'https://cdn-icons-png.flaticon.com/128/10186/10186826.png';
  const navigate = useNavigate();
  const { id } = useParams<{ id: string }>();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string>('');
  const [product, setProduct] = useState<CatalogProductDetail | null>(null);
  const [activeImage, setActiveImage] = useState(0);
  const [quantity, setQuantity] = useState(1);
  const [selectedVariantId, setSelectedVariantId] = useState<string>('');
  const [notifyName, setNotifyName] = useState('');
  const [notifyEmail, setNotifyEmail] = useState('');
  const [notifyPhone, setNotifyPhone] = useState('');
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [notifySubmitted, setNotifySubmitted] = useState(false);
  const [notifyLoading, setNotifyLoading] = useState(false);
  const [notifyError, setNotifyError] = useState('');
  const [cartMessage, setCartMessage] = useState('');
  const detailsSectionRef = useRef<HTMLElement>(null);
  const { formatCurrency } = useCurrency();

  useStagger(detailsSectionRef, {
    itemSelector: '[data-stagger-item]',
    y: 22,
    stagger: 0.12,
    duration: 0.65,
    start: 'top 85%',
    once: true,
  });

  useEffect(() => {
    const productKey = String(id || '').trim();
    if (!productKey) {
      setLoading(false);
      setError('Invalid product identifier.');
      return;
    }

    const load = async () => {
      try {
        setLoading(true);
        setError('');

        let resolved: CatalogProductDetail | null = null;
        try {
          const bySlug = await catalogService.getProductBySlug(productKey);
          resolved = extractProduct(bySlug);
        } catch {
          const byId = await catalogService.getProduct(productKey);
          resolved = extractProduct(byId);
        }

        if (!resolved) {
          throw new Error('Product not found.');
        }
        setProduct(resolved);
      } catch (err: any) {
        setError(err?.message || 'Failed to load product.');
      } finally {
        setLoading(false);
      }
    };

    load();
  }, [id]);

  const images = useMemo(() => {
    const media = (product?.media || []).map((m) => normalizeAssetUrl(m.image)).filter(Boolean);
    if (media.length > 0) return media;
    return ['https://placehold.co/1000x1000/f3f4f6/517b4b?text=Product'];
  }, [product]);

  const activeVariants = useMemo(() => {
    return (product?.variants || []).filter((variant) => variant.is_active !== false);
  }, [product?.variants]);

  const defaultVariant = useMemo(() => {
    if (!activeVariants.length) return null;
    return activeVariants.find((variant) => variant.is_default) || activeVariants[0];
  }, [activeVariants]);

  useEffect(() => {
    if (!defaultVariant) return;
    setSelectedVariantId(defaultVariant.id);
  }, [defaultVariant?.id]);

  const selectedVariant = useMemo(() => {
    if (!activeVariants.length) return null;
    return activeVariants.find((variant) => variant.id === selectedVariantId) || defaultVariant;
  }, [activeVariants, selectedVariantId, defaultVariant]);

  const isInStock = Boolean((selectedVariant as any)?.is_in_stock || (selectedVariant?.stock_quantity || 0) > 0);

  const selectedPrice = Number((selectedVariant as any)?.effective_price || selectedVariant?.price || 0);
  const originalPrice = Number((selectedVariant as any)?.display_compare_at_price || (selectedVariant as any)?.compare_at_price || 0);
  const discountPercent = originalPrice > selectedPrice ? Math.round(((originalPrice - selectedPrice) / originalPrice) * 100) : 0;
  const ratingValue = Number((product as any)?.avg_rating || product?.rating || 0);
  const ratingCount = Number((product as any)?.review_count || 0);

  const featureRows = useMemo(() => {
    const rows = (product?.info_items || []).slice(0, 4).map((item) => `${item.title} : ${item.value}`);
    if (rows.length > 0) return rows;
    return [
      'Closure : Hook & Loop',
      'Sole : Polyvinyl Chloride',
      'Width : Medium',
      'Outer Material : Premium Quality',
    ];
  }, [product?.info_items]);

  const sizeOptions = useMemo(() => {
    const variants = activeVariants;
    const preferredKeys = ['size', 'weight', 'volume', 'pack'];
    const found: Array<{ id: string; label: string }> = [];

    for (const variant of variants) {
      const attrValues = (variant.attribute_values || []) as Array<{ attribute_name: string; value: string }>;
      const picked = attrValues.find((a) =>
        preferredKeys.some((key) => (a.attribute_name || '').toLowerCase().includes(key))
      );
      if (picked?.value) {
        found.push({ id: variant.id, label: picked.value });
      } else if (variant.name && variant.name !== variant.sku) {
        found.push({ id: variant.id, label: variant.name });
      }
    }

    const dedup = new Map<string, { id: string; label: string }>();
    for (const entry of found) {
      if (!dedup.has(entry.label)) dedup.set(entry.label, entry);
    }
    return Array.from(dedup.values());
  }, [activeVariants]);

  const notifyStorageKey = useMemo(
    () => (product?.id ? `notify_success:${product.id}` : ''),
    [product?.id]
  );

  useEffect(() => {
    setIsLoggedIn(Boolean(localStorage.getItem('auth_token')));
  }, []);

  useEffect(() => {
    if (!notifyStorageKey) return;
    const persisted = localStorage.getItem(notifyStorageKey) === '1';
    setNotifySubmitted(persisted);
    setNotifyError('');
  }, [notifyStorageKey]);

  useEffect(() => {
    try {
      const raw = localStorage.getItem('auth_user');
      if (!raw) return;
      const parsed = JSON.parse(raw || '{}');
      if (parsed?.first_name || parsed?.last_name) {
        const full = `${parsed.first_name || ''} ${parsed.last_name || ''}`.trim();
        setNotifyName(full);
      }
      if (parsed?.email) setNotifyEmail(String(parsed.email));
      if (parsed?.phone) setNotifyPhone(String(parsed.phone));
    } catch {
      // ignore malformed local user cache
    }
  }, []);

  useEffect(() => {
    if (!product) return;

    const title = product.name ? `${product.name} | Aurora Blings` : 'Aurora Blings';
    const descriptionSource =
      product.short_description ||
      stripHtml(product.description || '') ||
      'Premium quality product.';
    const primaryMedia = (product.media || []).find((item) => item.is_primary) || product.media?.[0];
    const primaryImage = normalizeAssetUrl(primaryMedia?.image) || images[0];
    const shareUrl = `${window.location.origin}/product/${product.slug || product.id}`;

    applySeo({
      title,
      description: truncateText(descriptionSource, 180),
      image: primaryImage,
      imageAlt: primaryMedia?.alt_text || product.name,
      url: shareUrl,
      type: 'product',
      siteName: 'Aurora Blings',
    });
  }, [images, product]);

  const successMessage = 'You’ll be notified when this product is back in stock';

  const markNotifySuccess = () => {
    setNotifySubmitted(true);
    setNotifyError('');
    if (notifyStorageKey) {
      localStorage.setItem(notifyStorageKey, '1');
    }
  };

  const handleNotifyMe = async () => {
    if (!product?.id) return;
    try {
      setNotifyLoading(true);
      setNotifyError('');
      const payload: NotifySubscriptionPayload = { product_id: product.id };
      if (!isLoggedIn) {
        payload.name = notifyName;
        payload.email = notifyEmail;
        payload.phone = notifyPhone;
      }
      await notifyService.subscribe(payload);
      markNotifySuccess();
    } catch (err: any) {
      if (err?.response?.status === 409) {
        markNotifySuccess();
        return;
      }
      setNotifyError(err?.response?.data?.message || 'Failed to submit notify request. Please try again.');
    } finally {
      setNotifyLoading(false);
    }
  };

  const handleAddToCart = async () => {
    if (!product || !selectedVariant || !isInStock) return;
    try {
      await cartService.addItem(selectedVariant.id, quantity);
      cartService.emitCartUpdated();
      setCartMessage('Added to cart');
      navigate('/cart');
    } catch (err: any) {
      setCartMessage(err?.response?.data?.message || 'Unable to add item to cart right now.');
    }
  };

  if (loading) {
    return (
      <div className="pt-28 pb-24">
        <div className="container mx-auto px-4">
          <div className="h-[560px] rounded-3xl bg-gray-50 animate-pulse" />
        </div>
      </div>
    );
  }

  if (error || !product) {
    return (
      <div className="pt-28 pb-24">
        <div className="container mx-auto px-4">
          <div className="rounded-2xl border border-border bg-white/75 backdrop-blur-sm p-8 text-center text-muted-foreground">
            {error || 'Product not available.'}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-transparent pb-32 pt-24 md:pb-24 md:pt-28">
      <div className="container mx-auto px-4">
        <div className="mb-10">
          <div className="inline-flex max-w-full items-center gap-2 rounded-full border border-border/70 bg-white/70 backdrop-blur-sm px-4 py-2">
            <Link to="/" className="text-[10px] uppercase tracking-[0.18em] font-semibold text-muted-foreground hover:text-primary transition-colors">
              Home
            </Link>
            <span className="h-1 w-1 rounded-full bg-border" />
            <Link
              to={`/products/${product.category?.slug || product.category?.name ? `?category=${encodeURIComponent(String(product.category?.slug || product.category?.name || '').trim())}` : ''}`}
              className="text-[10px] uppercase tracking-[0.18em] font-semibold text-muted-foreground hover:text-primary transition-colors"
            >
              {product.category?.name || 'Shop'}
            </Link>
            <ChevronRight size={11} className="text-muted-foreground/70" />
            <span className="max-w-[38vw] truncate rounded-full bg-primary/10 px-2.5 py-1 text-[10px] uppercase tracking-[0.16em] font-bold text-foreground">
              {product.name}
            </span>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-10">
          <div className="lg:col-span-7 flex flex-col md:flex-row-reverse gap-4">
            <div className="flex-1 rounded-2xl overflow-hidden border border-border bg-muted/20 aspect-square">
              <img src={images[activeImage]} alt={product.name} className="w-full h-full object-contain" />
            </div>
            <div className="flex md:flex-col gap-3">
              {images.map((img, idx) => (
                <button
                  key={`${img}-${idx}`}
                  type="button"
                  onClick={() => setActiveImage(idx)}
                  className={`w-20 h-20 md:w-24 md:h-24 rounded-xl overflow-hidden border-2 ${activeImage === idx ? 'border-primary' : 'border-transparent opacity-60 hover:opacity-100'}`}
                >
                  <img src={img} alt="" className="w-full h-full object-cover" />
                </button>
              ))}
            </div>
          </div>

          <div className="lg:col-span-5 space-y-6">
            <div className="space-y-3">
              <div className="flex items-center gap-3">
                <Badge variant="surface" className="rounded-full">{product.category?.name || 'Category'}</Badge>
              </div>
              <h1 className="text-3xl md:text-4xl font-bold tracking-tight text-black">{product.name}</h1>
              <div className="flex items-center gap-2">
                {Array.from({ length: 5 }).map((_, idx) => {
                  const filled = idx < Math.round(ratingValue);
                  return (
                    <Star
                      key={idx}
                      size={14}
                      className={filled ? 'text-[#ff7f7f]' : 'text-muted-foreground/40'}
                      fill={filled ? 'currentColor' : 'none'}
                    />
                  );
                })}
                <span className="text-black/50">|</span>
                <span className="text-sm text-primary">{ratingCount} Ratings</span>
              </div>
              <p className="text-black leading-relaxed">{product.short_description || 'Premium quality product.'}</p>
              <div className="space-y-1">
                <div className="flex items-end gap-2">
                  <span className="text-4xl font-bold text-black">{formatCurrency(selectedPrice)}</span>
                  {discountPercent > 0 ? <span className="text-3xl font-bold text-primary">-{discountPercent}%</span> : null}
                </div>
                {originalPrice > selectedPrice ? (
                  <p className="text-xl text-black">
                    M.R.P. : <span className="line-through text-black">{formatCurrency(originalPrice)}</span>
                  </p>
                ) : null}
                <div className="pt-1">
                  <span className={`inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs font-semibold border ${
                    isInStock
                      ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                      : 'bg-red-50 text-red-700 border-red-200'
                  }`}>
                    <span className={`h-2.5 w-2.5 rounded-full ${
                      isInStock
                        ? 'bg-emerald-500 animate-pulse'
                        : 'bg-red-500'
                    }`} />
                    {isInStock ? 'In Stock' : 'Out of Stock'}
                  </span>
                </div>
              </div>
              <ul className="space-y-2 text-sm text-black pt-2">
                {featureRows.map((line, idx) => (
                  <li key={`${line}-${idx}`} className="flex items-start gap-2">
                    <img src={bulletIconUrl} alt="" className="h-4 w-4 mt-0.5 shrink-0" />
                    <span>{line}</span>
                  </li>
                ))}
              </ul>
            </div>

            {sizeOptions.length > 0 ? (
              <div className="space-y-3">
                <h4 className="text-xl font-bold uppercase tracking-wider text-black">Sizes</h4>
                <div className="flex flex-wrap gap-2">
                  {sizeOptions.map((option) => (
                    <button
                      key={option.id}
                      type="button"
                      onClick={() => setSelectedVariantId(option.id)}
                      className={`h-11 px-6 rounded-xl border text-lg transition-colors ${
                        selectedVariantId === option.id
                          ? 'bg-[#6c7fd8] text-white border-[#6c7fd8]'
                          : 'bg-white/70 backdrop-blur-sm text-[#4e5d78] border-border hover:border-[#6c7fd8]/50'
                      }`}
                    >
                      {option.label}
                    </button>
                  ))}
                </div>
              </div>
            ) : null}

            <div className="space-y-3 pt-2">
              <div className="flex items-center gap-3">
                <div className="flex items-center border border-border rounded-xl h-11 bg-white/70 backdrop-blur-sm">
                  <button type="button" onClick={() => setQuantity((q) => Math.max(1, q - 1))} className="px-3 h-full border-r hover:text-primary">
                    <Minus size={16} />
                  </button>
                  <span className="w-10 text-center font-bold">{quantity}</span>
                  <button type="button" onClick={() => setQuantity((q) => q + 1)} className="px-3 h-full border-l hover:text-primary">
                    <Plus size={16} />
                  </button>
                </div>
                <Button
                  type="button"
                  onClick={() => void handleAddToCart()}
                  disabled={!isInStock}
                  className="h-11 flex-1 rounded-xl px-6 bg-primary text-primary-foreground hover:bg-primary/90 disabled:bg-muted disabled:text-muted-foreground md:flex-none"
                >
                  <span className="inline-flex items-center gap-2">
                    <ShoppingCart size={18} />
                    <span>{isInStock ? 'Add to Cart' : 'Out of Stock'}</span>
                  </span>
                </Button>
              </div>
              {cartMessage ? <p className="text-xs font-medium text-emerald-700">{cartMessage}</p> : null}
              {!isInStock ? (
                <div className="rounded-2xl border border-border bg-muted/20 p-4 space-y-3">
                  <h5 className="text-sm font-semibold text-black">Notify Me When Available</h5>
                  {notifySubmitted ? (
                    <Badge variant="surface" className="w-full rounded-xl px-3 py-2 text-xs text-emerald-800 whitespace-normal">
                      {successMessage}
                    </Badge>
                  ) : !isLoggedIn ? (
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
                      <Input
                        type="text"
                        placeholder="Name"
                        value={notifyName}
                        onChange={(e) => setNotifyName(e.target.value)}
                      />
                      <Input
                        type="email"
                        placeholder="Email"
                        value={notifyEmail}
                        onChange={(e) => setNotifyEmail(e.target.value)}
                      />
                      <Input
                        type="tel"
                        placeholder="Phone"
                        value={notifyPhone}
                        onChange={(e) => setNotifyPhone(e.target.value)}
                      />
                    </div>
                  ) : null}
                  {notifyError ? <p className="text-xs text-red-600">{notifyError}</p> : null}
                  {!notifySubmitted ? (
                    <Button
                      type="button"
                      onClick={handleNotifyMe}
                      disabled={notifyLoading}
                      className="h-10 rounded-xl border border-amber-300 bg-amber-50 text-amber-700 hover:bg-amber-100"
                    >
                      {notifyLoading ? 'Submitting...' : 'Notify Me'}
                    </Button>
                  ) : null}
                  <Badge variant="surface" className="w-full rounded-xl px-3 py-2 text-[11px] leading-relaxed text-left whitespace-normal">
                    <span>
                      🔒 We respect your privacy. Your information is securely stored and used only for stock notifications — never shared with third parties.{' '}
                      <Link to="/privacy" className="font-semibold text-primary hover:underline">
                        [Privacy Policy]
                      </Link>
                    </span>
                  </Badge>
                </div>
              ) : null}
            </div>
          </div>
        </div>

        <section ref={detailsSectionRef} className="mt-14 space-y-4">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <div data-stagger-item className="border border-border rounded-2xl bg-white/75 backdrop-blur-sm p-6 md:p-8">
            <div className="space-y-3">
              <h4 className="text-base font-bold">Description</h4>
              <div
                className="prose prose-sm max-w-none text-foreground"
                dangerouslySetInnerHTML={{ __html: product.description || '<p>No description available.</p>' }}
              />
            </div>
            </div>

            <div data-stagger-item className="border border-border rounded-2xl bg-white/75 backdrop-blur-sm p-6 md:p-8">
            <div className="space-y-3">
              <h4 className="text-base font-bold">Additional Information</h4>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-x-8 gap-y-3">
                {(product.info_items || []).length > 0 ? (
                  (product.info_items || []).map((item) => (
                    <div key={item.id} className="flex items-start justify-between gap-3 border-b border-border/60 pb-2">
                      <span className="font-semibold text-foreground">{item.title}</span>
                      <span className="text-muted-foreground text-right">{item.value}</span>
                    </div>
                  ))
                ) : (
                  <p className="text-muted-foreground">No additional information available.</p>
                )}
              </div>
            </div>
            </div>
          </div>

          <div data-stagger-item className="border border-border rounded-2xl bg-white/75 backdrop-blur-sm p-6 md:p-8">
            <ProductReviewsSection productId={product.id} />
          </div>
        </section>
      </div>

      <div className="fixed inset-x-0 bottom-0 z-40 border-t border-border/70 bg-white/95 px-4 py-3 shadow-[0_-8px_24px_rgba(15,23,42,0.08)] backdrop-blur-sm md:hidden">
        <div className="mx-auto flex max-w-6xl items-center gap-3">
          <div className="min-w-0 flex-1">
            <p className="text-[10px] font-bold uppercase tracking-[0.24em] text-muted-foreground">Price</p>
            <p className="truncate text-lg font-bold text-foreground">{formatCurrency(selectedPrice)}</p>
          </div>
          <Button
            type="button"
            onClick={() => void handleAddToCart()}
            disabled={!isInStock}
            className="h-11 min-w-[170px] rounded-xl bg-primary px-6 text-primary-foreground hover:bg-primary/90 disabled:bg-muted disabled:text-muted-foreground"
          >
            <span className="inline-flex items-center gap-2">
              <ShoppingCart size={18} />
              <span>{isInStock ? 'Add to Bag' : 'Out of Stock'}</span>
            </span>
          </Button>
        </div>
      </div>
    </div>
  );
};
