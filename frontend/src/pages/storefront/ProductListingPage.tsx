import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import {
  LayoutGrid,
  List,
  ChevronLeft,
  ChevronRight as ChevronRightIcon,
  SlidersHorizontal,
  Box,
  ShoppingBag,
  Tags,
  Sparkles,
  Star,
  Heart,
} from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { cn } from '@/lib/utils';
import { DealProductCard } from '@/components/storefront/Deals/DealProductCard';
import catalogService from '@/services/api/catalog';
import { useCurrency } from '@/hooks/useCurrency';
import type { DealProduct } from '@/types/product';
import { useSectionTransition } from '@/animations/useSectionTransition';

interface ProductListItem {
  id: string;
  name: string;
  slug?: string;
  short_description?: string;
  category_name?: string;
  category?: { name?: string; slug?: string };
  brand_name?: string | null;
  rating?: string | number;
  primary_image?: string | null;
  hover_image?: string | null;
  default_variant?: { id?: string; sku?: string; price?: string | number | null; stock_quantity?: number } | null;
  price_range?: { min?: string | number | null; max?: string | number | null } | null;
  variants?: DealProduct['variants'];
  total_stock?: number;
  has_active_offer?: boolean;
  is_featured?: boolean;
}

interface CategoryListItem {
  id: string;
  name: string;
  slug?: string;
  image?: string | null;
  product_count?: number;
}

type ViewMode = 'blog' | 'list';
type SortMode = 'low-high' | 'high-low';

const extractRows = (payload: unknown): ProductListItem[] => {
  if (Array.isArray(payload)) return payload as ProductListItem[];
  if (payload && typeof payload === 'object') {
    const root = payload as Record<string, unknown>;
    if (Array.isArray(root.data)) return root.data as ProductListItem[];
    if (Array.isArray(root.results)) return root.results as ProductListItem[];
    if (root.data && typeof root.data === 'object') {
      const nested = root.data as Record<string, unknown>;
      if (Array.isArray(nested.results)) return nested.results as ProductListItem[];
      if (Array.isArray(nested.data)) return nested.data as ProductListItem[];
    }
  }
  return [];
};

const toNumber = (value: string | number | null | undefined): number => {
  if (typeof value === 'number') return value;
  if (typeof value === 'string') {
    const n = Number(value);
    return Number.isFinite(n) ? n : 0;
  }
  return 0;
};

const normalize = (value: string) => value.trim().toLowerCase().replace(/[^a-z0-9]+/g, '-');

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

const fallbackImage =
  'https://images.unsplash.com/photo-1515377905703-c4788e51af15?auto=format&fit=crop&q=80&w=900';

const categoryPalette = [
  'bg-rose-50',
  'bg-emerald-50',
  'bg-violet-50',
  'bg-amber-50',
  'bg-pink-50',
  'bg-teal-50',
];

const categoryIcons = [Box, ShoppingBag, Tags, Sparkles, Star, Heart];

const buildPageWindow = (current: number, total: number): Array<number | string> => {
  if (total <= 7) return Array.from({ length: total }, (_, idx) => idx + 1);
  if (current <= 3) return [1, 2, 3, 4, '…', total];
  if (current >= total - 2) return [1, '…', total - 3, total - 2, total - 1, total];
  return [1, '…', current - 1, current, current + 1, '…', total];
};

export const ProductListingPage: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const rootRef = useRef<HTMLDivElement>(null);
  const [loading, setLoading] = useState(true);
  const [products, setProducts] = useState<ProductListItem[]>([]);
  const [catalogCategories, setCatalogCategories] = useState<CategoryListItem[]>([]);
  const [viewMode, setViewMode] = useState<ViewMode>('blog');
  const [sortMode, setSortMode] = useState<SortMode>('low-high');
  const [selectedCategory, setSelectedCategory] = useState('All');
  const [currentPage, setCurrentPage] = useState(1);
  const { formatCurrency } = useCurrency();

  useSectionTransition(rootRef);

  useEffect(() => {
    const fetchProducts = async () => {
      try {
        setLoading(true);
        const [productRes, categoryRes] = await Promise.all([
          catalogService.listProducts(),
          catalogService.listCategories(),
        ]);
        setProducts(extractRows(productRes));
        setCatalogCategories(extractRows(categoryRes) as CategoryListItem[]);
      } catch (error) {
        console.error('Failed to load products:', error);
        setProducts([]);
        setCatalogCategories([]);
      } finally {
        setLoading(false);
      }
    };
    fetchProducts();
  }, []);

  const categories = useMemo(() => {
    const fallbackNames = Array.from(
      new Set(
        products
          .map((item) => (item.category_name || item.category?.name || '').trim())
          .filter(Boolean)
      )
    );
    const dbNames = catalogCategories.map((item) => String(item.name || '').trim()).filter(Boolean);
    const names = dbNames.length > 0 ? dbNames : fallbackNames;
    return ['All', ...names];
  }, [products, catalogCategories]);

  const categoryMetaByName = useMemo(() => {
    const map = new Map<string, CategoryListItem>();
    for (const category of catalogCategories) {
      const key = normalize(String(category.name || ''));
      if (!key) continue;
      map.set(key, category);
      if (category.slug) {
        map.set(normalize(category.slug), category);
      }
    }
    return map;
  }, [catalogCategories]);

  useEffect(() => {
    const rawCategory = (searchParams.get('category') || '').trim();
    if (!rawCategory) {
      setSelectedCategory('All');
      return;
    }
    const fromMeta = categoryMetaByName.get(normalize(rawCategory));
    if (fromMeta?.name) {
      setSelectedCategory(fromMeta.name);
      return;
    }
    const matched = categories.find((cat) => normalize(cat) === normalize(rawCategory));
    if (matched) {
      setSelectedCategory(matched);
      return;
    }
    const loose = categories.find((cat) => normalize(cat).replace(/s$/, '') === normalize(rawCategory).replace(/s$/, ''));
    setSelectedCategory(loose || 'All');
  }, [searchParams, categories, categoryMetaByName]);

  const mappedProducts = useMemo<DealProduct[]>(() => {
    return products.map((item): DealProduct => {
      const minPrice = toNumber(item.default_variant?.price ?? item.price_range?.min).toFixed(2);
      const maxPriceNum = toNumber(item.price_range?.max);
      const compareAtPrice = maxPriceNum > Number(minPrice) ? maxPriceNum.toFixed(2) : null;
      const variant =
        item.variants?.[0] ??
        {
          id: item.default_variant?.id || '',
          sku: item.default_variant?.sku || 'NA',
          name: item.name,
          price: minPrice,
          compare_at_price: compareAtPrice,
          offer_price: null,
          offer_starts_at: null,
          offer_ends_at: null,
          offer_label: '',
          offer_is_active: false,
          has_active_offer: !!item.has_active_offer,
          effective_price: minPrice,
          display_compare_at_price: compareAtPrice,
          stock_quantity: item.total_stock ?? item.default_variant?.stock_quantity ?? 0,
          is_active: true,
          is_default: true,
          discount_percentage: null,
          is_in_stock: (item.total_stock ?? item.default_variant?.stock_quantity ?? 0) > 0,
          is_low_stock: false,
        };

      return {
        id: item.id,
        name: item.name,
        slug: item.slug || item.id,
        short_description: item.short_description || '',
        category_name: item.category_name || item.category?.name || 'General',
        brand_name: item.brand_name || null,
        is_featured: !!item.is_featured,
        rating: String(item.rating || '0'),
        primary_image: item.primary_image || fallbackImage,
        hover_image: item.hover_image || null,
        price_range: { min: minPrice, max: compareAtPrice ?? minPrice },
        default_variant: {
          id: variant.id,
          sku: variant.sku,
          price: minPrice,
          stock_quantity: variant.stock_quantity,
        },
        variants: [variant],
        total_stock: item.total_stock ?? variant.stock_quantity,
      };
    });
  }, [products]);

  const categoryCounts = useMemo(() => {
    const counts = new Map<string, number>();
    for (const product of mappedProducts) {
      const key = normalize(product.category_name || 'General');
      counts.set(key, (counts.get(key) || 0) + 1);
    }
    return counts;
  }, [mappedProducts]);

  const categoryCards = useMemo(() => {
    const allCard = { key: 'all', name: 'All', slug: 'all', image: '', count: mappedProducts.length };
    if (catalogCategories.length > 0) {
      return [
        allCard,
        ...catalogCategories.map((item) => ({
          key: item.id,
          name: String(item.name || '').trim() || 'Category',
          slug: String(item.slug || item.name || '').trim(),
          image: normalizeAssetUrl(item.image),
          count: categoryCounts.get(normalize(String(item.name || ''))) || 0,
        })),
      ];
    }
    const fallback = categories
      .filter((item) => item !== 'All')
      .map((item, idx) => ({
        key: `fallback-${idx}`,
        name: item,
        slug: item,
        image: '',
        count: categoryCounts.get(normalize(item)) || 0,
      }));
    return [allCard, ...fallback];
  }, [catalogCategories, categories, categoryCounts, mappedProducts.length]);

  const filteredAndSorted = useMemo(() => {
    const filtered =
      selectedCategory === 'All'
        ? mappedProducts
        : mappedProducts.filter((p) => normalize(p.category_name) === normalize(selectedCategory));

    const sorted = [...filtered].sort((a, b) => {
      const aPrice = toNumber(a.variants?.[0]?.effective_price || a.default_variant?.price || a.price_range?.min);
      const bPrice = toNumber(b.variants?.[0]?.effective_price || b.default_variant?.price || b.price_range?.min);
      return sortMode === 'low-high' ? aPrice - bPrice : bPrice - aPrice;
    });

    return sorted;
  }, [mappedProducts, selectedCategory, sortMode]);

  useEffect(() => {
    setCurrentPage(1);
  }, [selectedCategory, sortMode, viewMode]);

  const pageSize = viewMode === 'blog' ? 15 : 10;
  const totalPages = Math.max(1, Math.ceil(filteredAndSorted.length / pageSize));
  const safePage = Math.min(currentPage, totalPages);
  const visible = filteredAndSorted.slice((safePage - 1) * pageSize, safePage * pageSize);
  const pageWindow = buildPageWindow(safePage, totalPages);

  const handleCategoryClick = (category: string) => {
    setSelectedCategory(category);
    const next = new URLSearchParams(searchParams);
    if (category === 'All') {
      next.delete('category');
    } else {
      const categoryMeta = categoryMetaByName.get(normalize(category));
      next.set('category', normalize(categoryMeta?.slug || category));
    }
    setSearchParams(next, { replace: true });
  };

  if (loading) {
    return (
      <div className="pt-32 pb-24">
        <div className="container mx-auto px-4">
          <div className="h-[560px] rounded-3xl bg-gray-50 animate-pulse" />
        </div>
      </div>
    );
  }

  return (
    <div ref={rootRef} className="pt-32 pb-24 bg-transparent">
      <div className="container mx-auto px-4">
        <div className="mb-8">
          <div className="inline-flex items-center gap-2 rounded-full border border-border/70 bg-white/70 backdrop-blur-sm px-4 py-2">
            <Link to="/" className="text-[10px] uppercase tracking-[0.18em] font-semibold text-muted-foreground hover:text-primary transition-colors">
              Home
            </Link>
            <span className="h-1 w-1 rounded-full bg-border" />
            <span className="text-[10px] uppercase tracking-[0.16em] font-bold text-foreground">Shop</span>
          </div>
          <h1 className="mt-4 text-4xl md:text-5xl font-bold tracking-tight text-foreground">Shop</h1>
        </div>

        <div className="mb-6 overflow-x-auto no-scrollbar">
          <div className="inline-flex gap-4 min-w-full pb-1">
            {categoryCards.map((category, index) => {
              const ActiveIcon = categoryIcons[index % categoryIcons.length];
              const isActive = selectedCategory === category.name;
              return (
                <button
                  key={category.key}
                  type="button"
                  onClick={() => handleCategoryClick(category.name)}
                  className={cn(
                    'w-[190px] shrink-0 rounded-[22px] border p-5 text-center transition-all',
                    isActive
                      ? 'border-primary/50 ring-2 ring-primary/20 bg-white'
                      : `${categoryPalette[index % categoryPalette.length]} border-transparent hover:border-primary/30`
                  )}
                >
                  <div className="mx-auto mb-3 inline-flex h-10 w-10 items-center justify-center rounded-full bg-white/80">
                    {category.image ? (
                      <img src={category.image} alt={category.name} className="h-6 w-6 object-contain" />
                    ) : (
                      <ActiveIcon size={22} className="text-primary" />
                    )}
                  </div>
                  <div className="text-2xl leading-none font-semibold text-foreground">{category.name}</div>
                  <div className="mt-1">
                    {category.count > 0 ? (
                      <span className="text-sm text-muted-foreground">{category.count} items</span>
                    ) : (
                      <span className="inline-flex items-center rounded-full bg-primary/12 px-2.5 py-0.5 text-xs font-semibold text-primary">
                        Coming Soon
                      </span>
                    )}
                  </div>
                </button>
              );
            })}
          </div>
        </div>

        <div className="mb-8 rounded-3xl border border-border/80 bg-white/70 backdrop-blur-sm px-4 py-3 flex flex-col md:flex-row md:items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <button
              type="button"
              className="h-10 w-10 rounded-full border border-border bg-white text-foreground inline-flex items-center justify-center"
              aria-label="Filters"
              title="Filters"
            >
              <SlidersHorizontal size={16} />
            </button>
            <button
              type="button"
              onClick={() => setViewMode('blog')}
              className={cn(
                'h-10 w-10 rounded-full border inline-flex items-center justify-center text-sm font-medium transition-colors',
                viewMode === 'blog'
                  ? 'bg-primary text-primary-foreground border-primary'
                  : 'bg-white/70 backdrop-blur-sm border-border text-muted-foreground hover:text-foreground'
              )}
              aria-label="Blog layout"
              title="Blog layout"
            >
              <LayoutGrid size={17} />
            </button>
            <button
              type="button"
              onClick={() => setViewMode('list')}
              className={cn(
                'h-10 w-10 rounded-full border inline-flex items-center justify-center text-sm font-medium transition-colors',
                viewMode === 'list'
                  ? 'bg-primary text-primary-foreground border-primary'
                  : 'bg-white/70 backdrop-blur-sm border-border text-muted-foreground hover:text-foreground'
              )}
              aria-label="List layout"
              title="List layout"
            >
              <List size={16} />
            </button>
          </div>

          <div className="flex items-center gap-3">
            <span className="text-sm text-muted-foreground">Sort By</span>
            <select
              value={sortMode}
              onChange={(e) => setSortMode(e.target.value as SortMode)}
              className="h-10 rounded-xl border border-border bg-white/80 backdrop-blur-sm px-3 text-sm"
            >
              <option value="low-high">Price Low to High</option>
              <option value="high-low">Price High to Low</option>
            </select>
          </div>
        </div>

        {visible.length === 0 ? (
          <div className="rounded-2xl border border-border bg-white/70 backdrop-blur-sm p-10 text-center text-muted-foreground">
            No products found for this category.
          </div>
        ) : viewMode === 'blog' ? (
          <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-5 gap-x-5 gap-y-10">
            {visible.map((product) => (
              <DealProductCard key={product.id} product={product} />
            ))}
          </div>
        ) : (
          <div className="space-y-4">
            {visible.map((product) => {
              const variant = product.variants?.[0];
              const price = toNumber(variant?.effective_price || product.default_variant?.price || 0);
              const original = toNumber(variant?.display_compare_at_price || variant?.compare_at_price || 0);
              return (
                <div key={product.id} className="rounded-2xl border border-border bg-white/75 backdrop-blur-sm p-4 md:p-5">
                  <div className="flex flex-col md:flex-row md:items-center gap-4">
                    <Link to={`/product/${product.slug}`} className="w-full md:w-32 h-32 rounded-xl overflow-hidden bg-muted/20 shrink-0">
                      <img src={product.primary_image || fallbackImage} alt={product.name} className="w-full h-full object-contain" />
                    </Link>
                    <div className="min-w-0 flex-1 space-y-1">
                      <p className="text-[11px] uppercase tracking-[0.14em] text-muted-foreground">{product.category_name}</p>
                      <Link to={`/product/${product.slug}`} className="block text-lg font-semibold text-foreground hover:text-primary transition-colors truncate">
                        {product.name}
                      </Link>
                      <p className="text-sm text-muted-foreground line-clamp-2">{product.short_description || 'Premium product.'}</p>
                    </div>
                    <div className="md:text-right md:min-w-[180px]">
                      <div className="text-xl font-bold text-primary">{formatCurrency(price)}</div>
                      {original > price ? (
                        <div className="text-sm text-muted-foreground line-through">{formatCurrency(original)}</div>
                      ) : null}
                      <Button asChild className="mt-3 h-9 rounded-lg px-4 bg-primary text-primary-foreground hover:bg-primary/90">
                        <Link to={`/product/${product.slug}`}>View Details</Link>
                      </Button>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {totalPages > 1 ? (
          <div className="mt-10 flex flex-wrap items-center justify-center gap-2">
            <Button
              type="button"
              variant="outline"
              className="h-10 px-3 rounded-xl bg-white/75"
              onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
              disabled={safePage === 1}
            >
              <ChevronLeft size={16} />
            </Button>
            {pageWindow.map((token, idx) =>
              typeof token === 'number' ? (
                <button
                  key={`${token}-${idx}`}
                  type="button"
                  onClick={() => setCurrentPage(token)}
                  className={cn(
                    'h-10 min-w-10 px-3 rounded-xl border text-sm font-semibold transition-colors',
                    safePage === token
                      ? 'bg-primary border-primary text-primary-foreground'
                      : 'bg-white/75 border-border text-foreground hover:border-primary/40'
                  )}
                >
                  {token}
                </button>
              ) : (
                <span key={`ellipsis-${idx}`} className="px-2 text-muted-foreground">
                  {token}
                </span>
              )
            )}
            <Button
              type="button"
              variant="outline"
              className="h-10 px-3 rounded-xl bg-white/75"
              onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
              disabled={safePage === totalPages}
            >
              <ChevronRightIcon size={16} />
            </Button>
          </div>
        ) : null}
      </div>
    </div>
  );
};
