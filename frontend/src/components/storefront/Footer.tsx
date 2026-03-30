import React, { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { Mail, MapPin, MessageCircle } from 'lucide-react';
import catalogService from '@/services/api/catalog';
import { useBranding } from '@/hooks/useBranding';

interface CategoryListItem {
  id: string;
  name: string;
  slug?: string;
}

const extractRows = (payload: unknown): CategoryListItem[] => {
  if (Array.isArray(payload)) return payload as CategoryListItem[];
  if (payload && typeof payload === 'object') {
    const root = payload as Record<string, unknown>;
    if (Array.isArray(root.data)) return root.data as CategoryListItem[];
    if (Array.isArray(root.results)) return root.results as CategoryListItem[];
    if (root.data && typeof root.data === 'object') {
      const nested = root.data as Record<string, unknown>;
      if (Array.isArray(nested.results)) return nested.results as CategoryListItem[];
      if (Array.isArray(nested.data)) return nested.data as CategoryListItem[];
    }
  }
  return [];
};

export const Footer: React.FC = () => {
  const branding = useBranding();
  const [catalogCategories, setCatalogCategories] = useState<CategoryListItem[]>([]);
  const currentYear = new Date().getFullYear();

  useEffect(() => {
    const loadCategories = async () => {
      try {
        const response = await catalogService.listCategories();
        setCatalogCategories(extractRows(response));
      } catch {
        setCatalogCategories([]);
      }
    };
    loadCategories();
  }, []);

  const directoryCategories = useMemo(() => {
    return catalogCategories
      .map((item) => ({
        name: String(item.name || '').trim(),
        slug: String(item.slug || item.name || '').trim(),
      }))
      .filter((item) => item.name)
      .slice(0, 14);
  }, [catalogCategories]);

  return (
    <footer className="mt-16 border-t border-border/60 bg-[#f5f8f2]">
      <div className="border-b border-border/60 py-10 bg-[#f5f8f2]">
        <div className="container mx-auto px-4">
          <h4 className="text-lg font-bold text-foreground">Brands Directory</h4>
          <div className="mt-5 text-sm text-muted-foreground">
            <p className="leading-7">
              <span className="font-semibold text-foreground">Jewellery :</span>{' '}
              {directoryCategories.length > 0 ? (
                directoryCategories.map((category, index) => (
                  <React.Fragment key={category.slug || category.name}>
                    <Link
                      to={`/shop?category=${encodeURIComponent(category.slug || category.name)}`}
                      className="hover:text-primary transition-colors"
                    >
                      {category.name}
                    </Link>
                    {index < directoryCategories.length - 1 ? ', ' : ''}
                  </React.Fragment>
                ))
              ) : (
                'No categories yet. Add categories from Admin to show here.'
              )}
            </p>
          </div>
        </div>
      </div>

      <div className="py-12 bg-[#f5f8f2]">
        <div className="container mx-auto px-4">
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-5 gap-8">
            <div>
              <h4 className="text-base font-bold text-foreground">Company</h4>
              <ul className="mt-4 space-y-2 text-sm text-muted-foreground">
                <li><Link to="/about" className="hover:text-primary transition-colors">Our Story</Link></li>
                <li><Link to="/contact-us/" className="hover:text-primary transition-colors">Contact Us</Link></li>
              </ul>
            </div>

            <div>
              <h4 className="text-base font-bold text-foreground">Account</h4>
              <ul className="mt-4 space-y-2 text-sm text-muted-foreground">
                <li><Link to="/login" className="hover:text-primary transition-colors">SignIn</Link></li>
                <li><Link to="/cart" className="hover:text-primary transition-colors">View Cart</Link></li>
                <li><Link to="/shop" className="hover:text-primary transition-colors">Affiliate Program</Link></li>
              </ul>
            </div>

            <div>
              <h4 className="text-base font-bold text-foreground">Help</h4>
              <ul className="mt-4 space-y-2 text-sm text-muted-foreground">
                <li><Link to="/checkout" className="hover:text-primary transition-colors">Payments</Link></li>
                <li><Link to="/shipping" className="hover:text-primary transition-colors">Shipping</Link></li>
                <li><Link to="/track-order" className="hover:text-primary transition-colors">Order Tracking</Link></li>
              </ul>
            </div>

            <div>
              <h4 className="text-base font-bold text-foreground">Consumer Policies</h4>
              <ul className="mt-4 space-y-2 text-sm text-muted-foreground">
                <li><Link to="/terms-and-conditions/" className="hover:text-primary transition-colors">Terms & Conditions</Link></li>
                <li><Link to="/return-and-refund-policy/" className="hover:text-primary transition-colors">Return & Refund Policy</Link></li>
                <li><Link to="/privacy-policy/" className="hover:text-primary transition-colors">Privacy Policy</Link></li>
                <li><Link to="/shipping-policy" className="hover:text-primary transition-colors">Shipping Policy</Link></li>
              </ul>
            </div>

            <div>
              <h4 className="text-base font-bold text-foreground">Company Address</h4>
              <ul className="mt-4 space-y-3 text-sm text-muted-foreground">
                <li className="flex items-start gap-2">
                  <MapPin size={16} className="mt-0.5 shrink-0 text-primary" />
                  <span>Gangamata Bagicha, Near Nabakalebara Road, Puri 752002</span>
                </li>
                <li className="flex items-center gap-2">
                  <MessageCircle size={16} className="shrink-0 text-primary" />
                  <a href="https://wa.me/917847090866" target="_blank" rel="noreferrer" className="hover:text-primary transition-colors">
                    +91 7847090866
                  </a>
                </li>
                <li className="flex items-center gap-2">
                  <Mail size={16} className="shrink-0 text-primary" />
                  <a href="mailto:connect@aurora.blings.com" className="hover:text-primary transition-colors">connect@aurora.blings.com</a>
                </li>
              </ul>
              <div className="mt-5 flex items-center gap-2">
                <a href="#" className="h-9 min-w-9 px-2 rounded-full border border-border flex items-center justify-center text-[11px] font-semibold text-muted-foreground hover:text-primary hover:border-primary/40 transition-colors" aria-label="Facebook">
                  <svg viewBox="0 0 24 24" className="h-4 w-4 fill-current" aria-hidden="true">
                    <path d="M13.5 8.5V6.9c0-.7.5-.9.8-.9h2V3h-2.8c-3.1 0-3.8 2.3-3.8 3.8v1.7H8v3h1.7V21h3.8v-9.5h2.6l.4-3h-3z" />
                  </svg>
                </a>
                <a href="https://www.youtube.com/@aurora_blings" target="_blank" rel="noreferrer" className="h-9 min-w-9 px-2 rounded-full border border-border flex items-center justify-center text-[11px] font-semibold text-muted-foreground hover:text-primary hover:border-primary/40 transition-colors" aria-label="YouTube">
                  <svg viewBox="0 0 24 24" className="h-4 w-4 fill-current" aria-hidden="true">
                    <path d="M23.5 7.2a3 3 0 0 0-2.1-2.1C19.5 4.5 12 4.5 12 4.5s-7.5 0-9.4.6A3 3 0 0 0 .5 7.2 31 31 0 0 0 0 12a31 31 0 0 0 .5 4.8 3 3 0 0 0 2.1 2.1c1.9.6 9.4.6 9.4.6s7.5 0 9.4-.6a3 3 0 0 0 2.1-2.1A31 31 0 0 0 24 12a31 31 0 0 0-.5-4.8zM9.6 15.3V8.7L15.8 12l-6.2 3.3z" />
                  </svg>
                </a>
                <a href="https://www.instagram.com/aurora_blings" target="_blank" rel="noreferrer" className="h-9 min-w-9 px-2 rounded-full border border-border flex items-center justify-center text-[11px] font-semibold text-muted-foreground hover:text-primary hover:border-primary/40 transition-colors" aria-label="Instagram">
                  <svg viewBox="0 0 24 24" className="h-4 w-4 fill-current" aria-hidden="true">
                    <path d="M12 2.2c3.2 0 3.6 0 4.8.1 1.1.1 1.7.2 2.1.4.6.2 1 .4 1.5.9s.7.9.9 1.5c.2.4.3 1 .4 2.1.1 1.2.1 1.6.1 4.8s0 3.6-.1 4.8c-.1 1.1-.2 1.7-.4 2.1-.2.6-.4 1-.9 1.5s-.9.7-1.5.9c-.4.2-1 .3-2.1.4-1.2.1-1.6.1-4.8.1s-3.6 0-4.8-.1c-1.1-.1-1.7-.2-2.1-.4a3.8 3.8 0 0 1-1.5-.9 3.8 3.8 0 0 1-.9-1.5c-.2-.4-.3-1-.4-2.1C2.2 15.6 2.2 15.2 2.2 12s0-3.6.1-4.8c.1-1.1.2-1.7.4-2.1.2-.6.4-1 .9-1.5s.9-.7 1.5-.9c.4-.2 1-.3 2.1-.4C8.4 2.2 8.8 2.2 12 2.2zm0 1.9c-3.2 0-3.5 0-4.7.1-1 .1-1.5.2-1.8.3-.4.1-.7.3-1 .6s-.5.6-.6 1c-.1.3-.2.8-.3 1.8-.1 1.2-.1 1.5-.1 4.7s0 3.5.1 4.7c.1 1 .2 1.5.3 1.8.1.4.3.7.6 1s.6.5 1 .6c.3.1.8.2 1.8.3 1.2.1 1.5.1 4.7.1s3.5 0 4.7-.1c1-.1 1.5-.2 1.8-.3.8-.3 1.3-.8 1.6-1.6.1-.3.2-.8.3-1.8.1-1.2.1-1.5.1-4.7s0-3.5-.1-4.7c-.1-1-.2-1.5-.3-1.8-.1-.4-.3-.7-.6-1s-.6-.5-1-.6c-.3-.1-.8-.2-1.8-.3-1.2-.1-1.5-.1-4.7-.1zm0 3.2a4.7 4.7 0 1 1 0 9.4 4.7 4.7 0 0 1 0-9.4zm0 1.9a2.8 2.8 0 1 0 0 5.6 2.8 2.8 0 0 0 0-5.6zm6-2.2a1.1 1.1 0 1 1 0 2.2 1.1 1.1 0 0 1 0-2.2z" />
                  </svg>
                </a>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="border-t border-border/60 py-5 bg-[#eef4e7]">
        <div className="container mx-auto px-4 flex flex-col md:flex-row items-center justify-between gap-4">
          <p className="text-sm text-muted-foreground">
            Copyright © {currentYear} <Link to="/" className="text-primary font-semibold">{branding.brandName}</Link> all rights reserved.
          </p>
          <img src="/assets/img/payment/payment.png" alt="payment" className="h-7 w-auto object-contain" />
        </div>
      </div>
    </footer>
  );
};
