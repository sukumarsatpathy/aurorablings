import React, { useEffect, useMemo, useState } from 'react';
import catalogService from '@/services/api/catalog';
import { DealProductCard } from '@/components/storefront/Deals/DealProductCard';
import type { DealProduct } from '@/types/product';
import { gsap, shouldAnimate } from '@/animations/gsapConfig';

interface ProductListItem {
  id: string;
  name: string;
  slug?: string;
  short_description?: string;
  category_name?: string;
  brand_name?: string | null;
  rating?: string;
  primary_image?: string | null;
  hover_image?: string | null;
  default_variant?: { id?: string; sku?: string; price?: string | number | null; stock_quantity?: number } | null;
  price_range?: { min?: string | number | null; max?: string | number | null } | null;
  variants?: DealProduct['variants'];
  total_stock?: number;
  has_active_offer?: boolean;
  is_featured?: boolean;
}

const shuffleArray = <T,>(items: T[]): T[] => {
  const next = [...items];
  for (let index = next.length - 1; index > 0; index -= 1) {
    const swapIndex = Math.floor(Math.random() * (index + 1));
    [next[index], next[swapIndex]] = [next[swapIndex], next[index]];
  }
  return next;
};

const extractRows = (payload: unknown): ProductListItem[] => {
  if (Array.isArray(payload)) {
    return payload as ProductListItem[];
  }

  if (payload && typeof payload === 'object') {
    const root = payload as Record<string, unknown>;
    if (Array.isArray(root.data)) {
      return root.data as ProductListItem[];
    }
    if (Array.isArray(root.results)) {
      return root.results as ProductListItem[];
    }
    if (root.data && typeof root.data === 'object') {
      const data = root.data as Record<string, unknown>;
      if (Array.isArray(data.results)) {
        return data.results as ProductListItem[];
      }
      if (Array.isArray(data.data)) {
        return data.data as ProductListItem[];
      }
    }
  }

  return [];
};

const toNumber = (value: string | number | null | undefined): number => {
  if (typeof value === 'number') return value;
  if (typeof value === 'string') {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : 0;
  }
  return 0;
};

const fallbackImage =
  'https://images.unsplash.com/photo-1515377905703-c4788e51af15?auto=format&fit=crop&q=80&w=900';

export const NewArrivalsSection: React.FC = () => {
  const [products, setProducts] = useState<ProductListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedCategory, setSelectedCategory] = useState('All');
  const [animatedProducts, setAnimatedProducts] = useState<DealProduct[]>([]);
  const [isTransitioning, setIsTransitioning] = useState(false);
  const gridRef = React.useRef<HTMLDivElement>(null);
  const isInitialRenderRef = React.useRef(true);

  useEffect(() => {
    const fetchProducts = async () => {
      try {
        const res = await catalogService.listAllProducts();
        setProducts(shuffleArray(extractRows(res)));
      } catch (error) {
        console.error('Failed to fetch new arrivals:', error);
        setProducts([]);
      } finally {
        setLoading(false);
      }
    };

    fetchProducts();
  }, []);

  const categories = useMemo(() => {
    const names = Array.from(
      new Set(
        products
          .map((product) => product.category_name?.trim())
          .filter((name): name is string => Boolean(name))
      )
    );
    return ['All', ...names.slice(0, 4)];
  }, [products]);

  const mappedProducts = useMemo<DealProduct[]>(() => {
    const filtered =
      selectedCategory === 'All'
        ? products
        : products.filter((product) => product.category_name === selectedCategory);

    return filtered.slice(0, 12).map((item): DealProduct => {
      const price = toNumber(item.default_variant?.price ?? item.price_range?.min).toFixed(2);
      const maxPrice = toNumber(item.price_range?.max);
      const compareAtPrice = maxPrice > Number(price) ? maxPrice.toFixed(2) : null;
      const cardVariant =
        item.variants?.[0] ??
        {
          id: item.default_variant?.id || item.id,
          sku: item.default_variant?.sku || '',
          name: item.name,
          price,
          compare_at_price: compareAtPrice,
          offer_price: null,
          offer_starts_at: null,
          offer_ends_at: null,
          offer_label: '',
          offer_is_active: false,
          has_active_offer: !!item.has_active_offer,
          effective_price: price,
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
        category_name: item.category_name || 'General',
        brand_name: item.brand_name || null,
        is_featured: !!item.is_featured,
        rating: item.rating || '0',
        primary_image: item.primary_image || fallbackImage,
        hover_image: item.hover_image || null,
        price_range: {
          min: price,
          max: compareAtPrice ?? price,
        },
        default_variant: {
          id: cardVariant.id,
          sku: cardVariant.sku,
          price,
          stock_quantity: cardVariant.stock_quantity,
        },
        variants: [cardVariant],
        total_stock: item.total_stock ?? cardVariant.stock_quantity,
      };
    });
  }, [products, selectedCategory]);

  useEffect(() => {
    // Initial mount
    if (isInitialRenderRef.current) {
      isInitialRenderRef.current = false;
      setAnimatedProducts(mappedProducts);
      return;
    }

    // Skip heavy motion if reduced-motion is enabled
    if (!shouldAnimate()) {
      setAnimatedProducts(mappedProducts);
      return;
    }

    const grid = gridRef.current;
    const currentCards = grid?.querySelectorAll('[data-filter-card]');

    if (!grid || !currentCards || currentCards.length === 0) {
      setAnimatedProducts(mappedProducts);
      return;
    }

    setIsTransitioning(true);
    gsap.to(currentCards, {
      autoAlpha: 0,
      y: 10,
      duration: 0.2,
      stagger: 0.03,
      ease: 'power2.in',
      onComplete: () => {
        setAnimatedProducts(mappedProducts);
      },
    });
  }, [mappedProducts]);

  useEffect(() => {
    if (!shouldAnimate()) {
      setIsTransitioning(false);
      return;
    }
    const grid = gridRef.current;
    const nextCards = grid?.querySelectorAll('[data-filter-card]');
    if (!grid || !nextCards || nextCards.length === 0) {
      setIsTransitioning(false);
      return;
    }

    gsap.fromTo(
      nextCards,
      { autoAlpha: 0, y: 12 },
      {
        autoAlpha: 1,
        y: 0,
        duration: 0.28,
        stagger: 0.04,
        ease: 'power2.out',
        onComplete: () => setIsTransitioning(false),
      }
    );
  }, [animatedProducts]);

  if (loading) {
    return (
      <section className="py-16 md:py-24 bg-white">
        <div className="container mx-auto px-4">
          <div className="h-96 rounded-3xl bg-gray-50 animate-pulse" />
        </div>
      </section>
    );
  }

  return (
    <section className="py-16 md:py-24 bg-white">
      <div className="container mx-auto px-4">
        <div className="flex flex-col md:flex-row md:items-end justify-between gap-6 mb-10">
          <div>
            <h2 className="text-3xl md:text-4xl font-bold text-gray-950">
              New <span className="text-[#517b4b]">Arrivals</span>
            </h2>
            <p className="text-muted-foreground mt-2">
              Shop online for new arrivals and get free shipping!
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            {categories.map((category) => (
              <button
                key={category}
                type="button"
                onClick={() => setSelectedCategory(category)}
                className={`px-5 py-2 rounded-full text-sm border transition-all ${
                  selectedCategory === category
                    ? 'bg-[#517b4b] text-white border-[#517b4b]'
                    : 'bg-white text-muted-foreground border-border hover:border-[#517b4b]/50'
                }`}
              >
                {category}
              </button>
            ))}
          </div>
        </div>

        {animatedProducts.length > 0 ? (
          <div
            ref={gridRef}
            className={`grid grid-cols-2 md:grid-cols-3 xl:grid-cols-4 gap-x-6 gap-y-10 transition-opacity duration-200 ${isTransitioning ? 'pointer-events-none' : ''}`}
          >
            {animatedProducts.map((product) => (
              <div key={product.id} data-filter-card>
                <DealProductCard product={product} />
              </div>
            ))}
          </div>
        ) : (
          <div className="rounded-2xl border border-border bg-gray-50 px-6 py-10 text-center text-muted-foreground">
            No products available yet for this category.
          </div>
        )}
      </div>
    </section>
  );
};
