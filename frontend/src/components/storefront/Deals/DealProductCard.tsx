import React, { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { ShoppingCart, Eye, Heart, Star, Minus, Plus } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { Modal, ModalContent, ModalHeader, ModalTitle } from '@/components/ui/Modal';
import { Input } from '@/components/ui/Input';
import { RatingStars } from './RatingStars';
import type { DealProduct } from '@/types/product';
import { useCurrency } from '@/hooks/useCurrency';
import catalogService, { type CatalogProductDetail } from '@/services/api/catalog';
import notifyService from '@/services/api/notify';
import cartService from '@/services/api/cart';

interface DealProductCardProps {
  product: DealProduct;
}

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

const extractProduct = (payload: unknown): CatalogProductDetail | null => {
  if (!payload || typeof payload !== 'object') return null;
  const root = payload as Record<string, unknown>;
  if (root.data && typeof root.data === 'object') return root.data as CatalogProductDetail;
  if (root.id) return root as unknown as CatalogProductDetail;
  return null;
};

export const DealProductCard: React.FC<DealProductCardProps> = ({ product }) => {
  const [isHovered, setIsHovered] = useState(false);
  const [quickViewOpen, setQuickViewOpen] = useState(false);
  const [quickViewLoading, setQuickViewLoading] = useState(false);
  const [quickViewError, setQuickViewError] = useState('');
  const [quickViewProduct, setQuickViewProduct] = useState<CatalogProductDetail | null>(null);
  const [selectedQuickVariantId, setSelectedQuickVariantId] = useState('');
  const [quickQuantity, setQuickQuantity] = useState(1);
  const [quickAddSuccess, setQuickAddSuccess] = useState('');
  const [quickAddError, setQuickAddError] = useState('');
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [notifyName, setNotifyName] = useState('');
  const [notifyEmail, setNotifyEmail] = useState('');
  const [notifyPhone, setNotifyPhone] = useState('');
  const [notifySubmitted, setNotifySubmitted] = useState(false);
  const [notifyLoading, setNotifyLoading] = useState(false);
  const [notifyError, setNotifyError] = useState('');
  const [cardAddSuccess, setCardAddSuccess] = useState('');
  const [cardAddError, setCardAddError] = useState('');
  const { formatCurrency } = useCurrency();

  const firstVariant = product.variants?.[0];
  const price = Number(firstVariant?.effective_price || product.default_variant?.price || '0');
  const originalPrice = Number(firstVariant?.display_compare_at_price || firstVariant?.compare_at_price || 0);
  const packLabel = firstVariant?.sku?.trim() || product.default_variant?.sku || 'N/A';
  const ratingValue = parseFloat(product.rating || '0');

  const defaultQuickVariant = useMemo(() => {
    const variants = quickViewProduct?.variants || [];
    if (variants.length === 0) return null;
    return variants.find((variant) => variant.is_default) || variants[0];
  }, [quickViewProduct]);

  const quickVariant = useMemo(() => {
    const variants = quickViewProduct?.variants || [];
    if (variants.length === 0) return null;
    if (selectedQuickVariantId) {
      const selected = variants.find((variant) => variant.id === selectedQuickVariantId);
      if (selected) return selected;
    }
    return defaultQuickVariant;
  }, [quickViewProduct, selectedQuickVariantId, defaultQuickVariant]);

  const quickPrice = Number(quickVariant?.effective_price || quickVariant?.price || price);
  const quickOriginalPrice = Number(
    quickVariant?.display_compare_at_price || quickVariant?.compare_at_price || originalPrice || 0
  );
  const quickInStock = Number(quickVariant?.stock_quantity || product.total_stock || 0) > 0;
  const quickRating = Number(quickViewProduct?.avg_rating || quickViewProduct?.rating || ratingValue || 0);
  const quickReviewCount = Number(quickViewProduct?.review_count || 0);

  const quickImages = useMemo(() => {
    const fromMedia = (quickViewProduct?.media || []).map((media) => normalizeAssetUrl(media.image)).filter(Boolean);
    if (fromMedia.length > 0) return fromMedia;
    return [normalizeAssetUrl(product.primary_image)].filter(Boolean);
  }, [quickViewProduct, product.primary_image]);

  const quickHighlights = useMemo(() => {
    const attrs = quickVariant?.attribute_values || [];
    return attrs.slice(0, 4).map((item) => `${item.attribute_name}: ${item.value}`);
  }, [quickVariant]);

  const variantOptions = useMemo(() => {
    const variants = quickViewProduct?.variants || [];
    const preferredKeys = ['size', 'weight', 'volume', 'pack'];
    return variants.map((variant) => {
      const picked = (variant.attribute_values || []).find((item) =>
        preferredKeys.some((key) => (item.attribute_name || '').toLowerCase().includes(key))
      );
      return {
        id: variant.id,
        label: picked?.value || variant.name || variant.sku,
      };
    });
  }, [quickViewProduct]);

  const notifyStorageKey = useMemo(
    () => (quickViewProduct?.id ? `notify_success:${quickViewProduct.id}` : ''),
    [quickViewProduct?.id]
  );

  const markNotifySuccess = () => {
    setNotifySubmitted(true);
    setNotifyError('');
    if (notifyStorageKey) localStorage.setItem(notifyStorageKey, '1');
  };

  const openQuickView = async () => {
    setQuickViewOpen(true);
    setQuickAddSuccess('');
    setQuickAddError('');
    setQuickQuantity(1);
    if (quickViewProduct || quickViewLoading) return;
    setQuickViewError('');
    setQuickViewLoading(true);
    try {
      const response = await catalogService.getProductBySlug(product.slug);
      const extracted = extractProduct(response);
      if (!extracted) {
        setQuickViewError('Unable to load product details right now.');
        return;
      }
      setQuickViewProduct(extracted);
      const nextDefault = extracted.variants?.find((variant) => variant.is_default) || extracted.variants?.[0];
      setSelectedQuickVariantId(nextDefault?.id || '');
    } catch {
      setQuickViewError('Unable to load product details right now.');
    } finally {
      setQuickViewLoading(false);
    }
  };

  const handleQuickAddToCart = async () => {
    if (!quickViewProduct || !quickVariant || !quickInStock) return;
    try {
      setQuickAddError('');
      await cartService.addItem(quickVariant.id, quickQuantity);
      cartService.emitCartUpdated();
      setQuickAddSuccess('Added to cart');
    } catch {
      setQuickAddSuccess('');
      setQuickAddError('Unable to add this item right now.');
    }
  };

  const handleCardAddToCart = async () => {
    const selected = product.variants?.[0];
    if (!selected) {
      setCardAddSuccess('');
      setCardAddError('Unable to add this item right now.');
      return;
    }
    const inStock = Number(selected.stock_quantity || product.total_stock || 0) > 0;
    if (!inStock) {
      setCardAddSuccess('');
      setCardAddError('');
      return;
    }

    const resolveVariantId = async (): Promise<string> => {
      if (selected.id && selected.id !== product.id) return selected.id;

      const fromQuick = quickViewProduct?.variants?.find((variant) => variant.is_default) || quickViewProduct?.variants?.[0];
      if (fromQuick?.id) return fromQuick.id;

      try {
        const bySlug = await catalogService.getProductBySlug(product.slug);
        const extractedBySlug = extractProduct(bySlug);
        const slugVariant = extractedBySlug?.variants?.find((variant) => variant.is_default) || extractedBySlug?.variants?.[0];
        if (slugVariant?.id) return slugVariant.id;
      } catch {
        // fallback below
      }

      try {
        const byId = await catalogService.getProduct(product.id);
        const extractedById = extractProduct(byId);
        const idVariant = extractedById?.variants?.find((variant) => variant.is_default) || extractedById?.variants?.[0];
        if (idVariant?.id) return idVariant.id;
      } catch {
        // final fallback below
      }

      return '';
    };

    try {
      setCardAddError('');
      const variantId = await resolveVariantId();
      if (!variantId) {
        setCardAddSuccess('');
        setCardAddError('Unable to add this item right now.');
        return;
      }

      await cartService.addItem(variantId, 1);
      cartService.emitCartUpdated();
      setCardAddSuccess('Added');
      setCardAddError('');
      window.setTimeout(() => setCardAddSuccess(''), 1200);
    } catch {
      setCardAddSuccess('');
      setCardAddError('Unable to add this item right now.');
    }
  };

  const handleQuickNotify = async () => {
    if (!quickViewProduct?.id) return;
    try {
      setNotifyLoading(true);
      setNotifyError('');
      const payload: Record<string, string> = { product_id: quickViewProduct.id };
      if (!isLoggedIn) {
        payload.name = notifyName;
        payload.email = notifyEmail;
        payload.phone = notifyPhone;
      }
      await notifyService.subscribe(payload as { product_id: string; name?: string; email?: string; phone?: string });
      markNotifySuccess();
    } catch (err: unknown) {
      const status = (err as { response?: { status?: number } })?.response?.status;
      const message = (err as { response?: { data?: { message?: string } } })?.response?.data?.message;
      if (status === 409) {
        markNotifySuccess();
        return;
      }
      setNotifyError(message || 'Failed to submit notify request. Please try again.');
    } finally {
      setNotifyLoading(false);
    }
  };

  useEffect(() => {
    if (quickViewOpen) {
      document.body.classList.add('quick-view-open');
    } else {
      document.body.classList.remove('quick-view-open');
    }
    return () => {
      document.body.classList.remove('quick-view-open');
    };
  }, [quickViewOpen]);

  useEffect(() => {
    setIsLoggedIn(Boolean(localStorage.getItem('auth_token')));
    try {
      const raw = localStorage.getItem('auth_user');
      if (!raw) return;
      const parsed = JSON.parse(raw || '{}') as { first_name?: string; last_name?: string; email?: string; phone?: string };
      if (parsed.first_name || parsed.last_name) {
        const full = `${parsed.first_name || ''} ${parsed.last_name || ''}`.trim();
        setNotifyName(full);
      }
      if (parsed.email) setNotifyEmail(parsed.email);
      if (parsed.phone) setNotifyPhone(parsed.phone);
    } catch {
      // ignore malformed local user cache
    }
  }, []);

  useEffect(() => {
    if (!notifyStorageKey) return;
    setNotifySubmitted(localStorage.getItem(notifyStorageKey) === '1');
    setNotifyError('');
  }, [notifyStorageKey]);

  return (
    <>
      <div
        className="group bg-white rounded-[2rem] p-4 transition-all duration-300 border border-gray-100 flex flex-col h-full"
        onMouseEnter={() => setIsHovered(true)}
        onMouseLeave={() => setIsHovered(false)}
      >
        <div className="relative aspect-[1/1] mb-6 rounded-[1.5rem] overflow-hidden bg-[#eceff1] p-3">
          <Link to={`/product/${product.slug}`} className="block h-full w-full rounded-[1.2rem] overflow-hidden">
            <img
              src={product.primary_image || '/placeholder-product.png'}
              alt={product.name}
              className="absolute inset-0 h-full w-full object-contain rounded-[1.2rem] transition-opacity duration-300 opacity-100"
              onError={(event) => {
                (event.target as HTMLImageElement).src = `https://placehold.co/600x600/f3f4f6/517b4b?text=${encodeURIComponent(product.name)}`;
              }}
            />
            {product.hover_image && (
              <img
                src={product.hover_image}
                alt={`${product.name} hover`}
                className={`absolute inset-0 h-full w-full object-contain rounded-[1.2rem] transition-opacity duration-300 ${
                  isHovered ? 'opacity-100' : 'opacity-0'
                }`}
                onError={(event) => {
                  (event.target as HTMLImageElement).src = `https://placehold.co/600x600/f3f4f6/c8a97e?text=${encodeURIComponent(product.name)}`;
                }}
              />
            )}
          </Link>

          <div className={`absolute right-4 bottom-4 flex flex-col gap-2 transition-opacity duration-300 ${isHovered ? 'opacity-100' : 'opacity-0'}`}>
            <Button size="icon" variant="ghost" className="w-10 h-10 rounded-full bg-white text-[#517b4b] shadow-sm hover:bg-[#517b4b] hover:text-white transition-all ring-1 ring-black/5">
              <Heart size={18} fill="transparent" />
            </Button>
            <Button size="icon" variant="ghost" onClick={openQuickView} className="w-10 h-10 rounded-full bg-white text-[#517b4b] shadow-sm hover:bg-[#517b4b] hover:text-white transition-all ring-1 ring-black/5">
              <Eye size={18} />
            </Button>
            <Button
              size="icon"
              variant="ghost"
              onClick={() => void handleCardAddToCart()}
              className="w-10 h-10 rounded-full bg-white text-[#517b4b] shadow-sm hover:bg-[#517b4b] hover:text-white transition-all ring-1 ring-black/5"
            >
              <ShoppingCart size={18} />
            </Button>
          </div>
        </div>

        <div className="px-1 flex flex-col flex-grow">
          <div className="flex justify-end items-start mb-2">
            {ratingValue > 0 && <RatingStars rating={ratingValue} />}
          </div>

          <Link to={`/product/${product.slug}`} className="block mb-3">
            <h3 className="text-sm font-semibold text-gray-900 line-clamp-2 leading-snug hover:text-[#517b4b] transition-colors">
              {product.name}
            </h3>
          </Link>

          <div className="mt-auto pt-2 flex flex-col gap-1">
            <div className="flex items-baseline justify-between gap-3">
              <div className="flex items-baseline gap-2">
                <span className="text-base font-bold text-[#517b4b]">{formatCurrency(price)}</span>
                {originalPrice > price ? (
                  <span className="text-xs text-gray-400 line-through">{formatCurrency(originalPrice)}</span>
                ) : null}
              </div>
              <span className="text-sm text-gray-500">{packLabel}</span>
            </div>
            {cardAddSuccess ? <span className="text-[11px] font-medium text-emerald-700">{cardAddSuccess}</span> : null}
            {cardAddError ? <span className="text-[11px] font-medium text-red-600">{cardAddError}</span> : null}
          </div>
        </div>
      </div>

      <Modal open={quickViewOpen} onOpenChange={setQuickViewOpen}>
        <ModalContent className="max-w-4xl p-0 overflow-hidden border border-border/60 bg-white">
          <ModalHeader className="px-6 py-4 border-b border-border/60">
            <ModalTitle className="text-xl font-bold text-[#1f2937]">Quick View</ModalTitle>
          </ModalHeader>
          {quickViewLoading ? (
            <div className="p-6 grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="h-80 rounded-2xl bg-gray-100 animate-pulse" />
              <div className="space-y-3">
                <div className="h-6 w-2/3 rounded bg-gray-100 animate-pulse" />
                <div className="h-4 w-1/3 rounded bg-gray-100 animate-pulse" />
                <div className="h-4 w-full rounded bg-gray-100 animate-pulse" />
                <div className="h-4 w-5/6 rounded bg-gray-100 animate-pulse" />
              </div>
            </div>
          ) : quickViewError ? (
            <div className="p-6 text-sm text-destructive">{quickViewError}</div>
          ) : (
            <div className="p-6 grid grid-cols-1 md:grid-cols-2 gap-6">
              <div>
                <div className="h-80 rounded-2xl bg-[#f7f8f8] border border-border/50 overflow-hidden">
                  <img
                    src={quickImages[0] || `https://placehold.co/900x900/f3f4f6/517b4b?text=${encodeURIComponent(product.name)}`}
                    alt={quickViewProduct?.name || product.name}
                    className="h-full w-full object-contain"
                  />
                </div>
              </div>
              <div className="space-y-4">
                <p className="text-xs uppercase tracking-[0.18em] text-primary font-semibold">
                  {quickViewProduct?.category?.name || product.category_name}
                </p>
                <h3 className="text-2xl font-bold text-black leading-tight">{quickViewProduct?.name || product.name}</h3>
                {quickRating > 0 ? (
                  <div className="flex items-center gap-2 text-sm">
                    <Star size={14} className="fill-primary text-primary" />
                    <span className="font-medium text-primary">{quickRating.toFixed(1)}</span>
                    <span className="text-muted-foreground">({quickReviewCount} reviews)</span>
                  </div>
                ) : null}
                <p className="text-sm text-muted-foreground line-clamp-3">
                  {quickViewProduct?.short_description || product.short_description || 'Premium curated product.'}
                </p>
                <div className="flex items-end gap-2">
                  <span className="text-3xl font-bold text-black">{formatCurrency(quickPrice)}</span>
                  {quickOriginalPrice > quickPrice ? (
                    <span className="text-sm text-muted-foreground line-through">{formatCurrency(quickOriginalPrice)}</span>
                  ) : null}
                </div>
                <div>
                  {quickInStock ? (
                    <Badge className="bg-emerald-100 text-emerald-700 border-emerald-200">In Stock</Badge>
                  ) : (
                    <Badge className="bg-amber-100 text-amber-700 border-amber-200">Out of Stock</Badge>
                  )}
                </div>

                {variantOptions.length > 0 ? (
                  <div className="space-y-2">
                    <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-700">Sizes</p>
                    <div className="flex flex-wrap gap-2">
                      {variantOptions.map((option) => (
                        <button
                          key={option.id}
                          type="button"
                          onClick={() => {
                            setSelectedQuickVariantId(option.id);
                            setQuickAddSuccess('');
                            setQuickAddError('');
                            setNotifyError('');
                          }}
                          className={`h-9 px-4 rounded-lg border text-sm transition-colors ${
                            quickVariant?.id === option.id
                              ? 'bg-primary text-primary-foreground border-primary'
                              : 'bg-white text-slate-700 border-border hover:border-primary/40'
                          }`}
                        >
                          {option.label}
                        </button>
                      ))}
                    </div>
                  </div>
                ) : null}

                {quickHighlights.length > 0 ? (
                  <ul className="space-y-1 text-sm text-slate-700">
                    {quickHighlights.map((entry) => (
                      <li key={entry}>• {entry}</li>
                    ))}
                  </ul>
                ) : null}

                <div className="space-y-3 pt-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <div className="flex items-center border border-border rounded-xl h-10">
                      <button
                        type="button"
                        onClick={() => setQuickQuantity((q) => Math.max(1, q - 1))}
                        className="h-full px-2.5 border-r hover:text-primary"
                      >
                        <Minus size={14} />
                      </button>
                      <span className="w-9 text-center font-semibold text-sm">{quickQuantity}</span>
                      <button
                        type="button"
                        onClick={() => setQuickQuantity((q) => q + 1)}
                        className="h-full px-2.5 border-l hover:text-primary"
                      >
                        <Plus size={14} />
                      </button>
                    </div>
                    <Button
                      type="button"
                      onClick={() => void handleQuickAddToCart()}
                      disabled={!quickInStock}
                      className="h-10 rounded-xl bg-primary text-primary-foreground hover:bg-primary/90 disabled:bg-muted disabled:text-muted-foreground"
                    >
                      <span className="inline-flex items-center gap-2">
                        <ShoppingCart size={16} />
                        <span>{quickInStock ? 'Add to Cart' : 'Out of Stock'}</span>
                      </span>
                    </Button>
                    <Button asChild variant="outline" className="h-10 rounded-xl">
                      <Link to={`/product/${product.slug}`}>View Full Details</Link>
                    </Button>
                  </div>
                  {quickAddSuccess ? <p className="text-xs font-medium text-emerald-700">{quickAddSuccess}</p> : null}
                  {quickAddError ? <p className="text-xs font-medium text-red-600">{quickAddError}</p> : null}
                </div>

                {!quickInStock ? (
                  <div className="rounded-xl border border-border bg-muted/20 p-3 space-y-2">
                    <p className="text-sm font-semibold text-black">Notify Me When Available</p>
                    {notifySubmitted ? (
                      <Badge variant="surface" className="w-full rounded-lg px-3 py-2 text-xs text-emerald-800 whitespace-normal">
                        You’ll be notified when this product is back in stock
                      </Badge>
                    ) : !isLoggedIn ? (
                      <div className="grid grid-cols-1 gap-2">
                        <Input type="text" placeholder="Name" value={notifyName} onChange={(event) => setNotifyName(event.target.value)} />
                        <Input type="email" placeholder="Email" value={notifyEmail} onChange={(event) => setNotifyEmail(event.target.value)} />
                        <Input type="tel" placeholder="Phone" value={notifyPhone} onChange={(event) => setNotifyPhone(event.target.value)} />
                      </div>
                    ) : null}

                    {notifyError ? <p className="text-xs text-red-600">{notifyError}</p> : null}
                    {!notifySubmitted ? (
                      <Button
                        type="button"
                        onClick={handleQuickNotify}
                        disabled={notifyLoading}
                        className="h-9 rounded-lg bg-primary text-primary-foreground hover:bg-primary/90"
                      >
                        {notifyLoading ? 'Submitting...' : 'Notify Me'}
                      </Button>
                    ) : null}
                  </div>
                ) : null}

                <div className="rounded-lg border border-border/70 bg-white/80 px-3 py-2 text-[11px] leading-relaxed text-slate-600">
                  🔒 We respect your privacy. Your information is securely stored and used only for stock notifications — never shared with third parties.
                </div>
              </div>
            </div>
          )}
        </ModalContent>
      </Modal>
    </>
  );
};
