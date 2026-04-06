import React from 'react';
import { Link } from 'react-router-dom';
import { ShoppingCart, Eye } from 'lucide-react';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { useCurrency } from '@/hooks/useCurrency';
import cartService from '@/services/api/cart';
import catalogService from '@/services/api/catalog';

export interface Product {
  id: string;
  name: string;
  price: number;
  originalPrice?: number;
  image: string;
  category: string;
  badge?: string;
  isNew?: boolean;
}

interface ProductCardProps {
  product: Product;
}

export const ProductCard: React.FC<ProductCardProps> = ({ product }) => {
  const { formatCurrency } = useCurrency();

  const resolveDefaultVariantId = async () => {
    try {
      const bySlug = await catalogService.getProductBySlug(product.id);
      const slugData = bySlug?.data && typeof bySlug.data === 'object' ? bySlug.data : bySlug;
      const variants = Array.isArray(slugData?.variants) ? slugData.variants.filter((variant: any) => variant.is_active !== false) : [];
      const selected = variants.find((variant: any) => variant.is_default) || variants[0];
      if (selected?.id) return String(selected.id);
    } catch {
      // fallback below
    }

    const byId = await catalogService.getProduct(product.id);
    const idData = byId?.data && typeof byId.data === 'object' ? byId.data : byId;
    const variants = Array.isArray(idData?.variants) ? idData.variants.filter((variant: any) => variant.is_active !== false) : [];
    const selected = variants.find((variant: any) => variant.is_default) || variants[0];
    return selected?.id ? String(selected.id) : '';
  };

  const handleAddToCart = async () => {
    try {
      const variantId = await resolveDefaultVariantId();
      if (!variantId) return;
      await cartService.addItem(variantId, 1);
      cartService.emitCartUpdated();
    } catch {
      // ignore add failures on listing cards
    }
  };

  return (
    <Card data-stagger-item data-scroll-item className="group relative overflow-hidden border-none shadow-none bg-transparent h-full flex flex-col transition-transform duration-300 hover:-translate-y-1">
      {/* Image Container */}
      <div className="relative aspect-[4/5] overflow-hidden rounded-2xl bg-muted/50">
        <img 
          src={product.image} 
          alt={product.name}
          className="h-full w-full object-cover transition-transform duration-700 will-change-transform group-hover:scale-[1.08]"
          loading="lazy"
        />
        
        {/* Badges */}
        {product.badge && (
          <Badge className="absolute top-3 left-3 bg-primary/90 backdrop-blur-sm border-none shadow-sm">
            {product.badge}
          </Badge>
        )}
        {product.isNew && !product.badge && (
          <Badge className="absolute top-3 left-3 bg-white/90 text-primary border-none shadow-sm">
            New
          </Badge>
        )}

        {/* Quick Actions Overlay */}
        <div className="absolute inset-0 bg-black/5 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center gap-3">
           <Button size="icon" variant="secondary" className="rounded-full shadow-lg scale-90 group-hover:scale-100 transition-transform">
             <Eye size={18} />
           </Button>
           <Button
             size="icon"
             onClick={() => void handleAddToCart()}
             className="rounded-full shadow-lg scale-90 group-hover:scale-100 transition-transform"
           >
             <ShoppingCart size={18} />
           </Button>
        </div>
      </div>

      {/* Content */}
      <div className="pt-4 flex flex-col flex-1">
        <p className="text-[10px] uppercase tracking-widest text-muted-foreground mb-1">{product.category}</p>
        <Link to={`/product/${product.id}`} className="hover:text-primary transition-colors" data-cursor="hover">
          <h3 className="text-sm md:text-base font-medium leading-tight mb-2 line-clamp-2">{product.name}</h3>
        </Link>
        <div className="mt-auto flex items-center gap-2">
          <span className="text-sm md:text-lg font-bold text-primary">{formatCurrency(product.price)}</span>
          {product.originalPrice && (
            <span className="text-xs text-muted-foreground line-through">{formatCurrency(product.originalPrice)}</span>
          )}
        </div>
      </div>
    </Card>
  );
};
