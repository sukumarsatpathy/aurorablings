import React, { useRef } from 'react';
import { Link } from 'react-router-dom';
import { useScrollReveal } from '@/animations/useScrollReveal';
import { usePromoBanners } from '@/hooks/usePromoBanners';
import PromoBannerGrid from '@/components/promo/PromoBannerGrid/PromoBannerGrid';
import DualPromoBanner from '@/components/promo/DualPromoBanner/DualPromoBanner';
import CategoryShowcase from '@/components/storefront/CategoryShowcase/CategoryShowcase';
import { DealSection } from '@/components/storefront/Deals/DealSection';
import { NewArrivalsSection } from '@/components/storefront/NewArrivals/NewArrivalsSection';

export const HomePage: React.FC = () => {
  const { banners, loading } = usePromoBanners();
  const heroRef = useRef<HTMLElement>(null);
  const categoryRef = useRef<HTMLElement>(null);
  const dualBannerRef = useRef<HTMLElement>(null);
  const dealRef = useRef<HTMLElement>(null);
  const newArrivalsRef = useRef<HTMLElement>(null);

  useScrollReveal(heroRef, { type: 'blur', duration: 1, threshold: 0.01 });
  useScrollReveal(categoryRef, { type: 'fade-up', threshold: 0.01 });
  useScrollReveal(dualBannerRef, { type: 'fade-up', duration: 1.15, threshold: 0.2, once: true });
  useScrollReveal(dealRef, { type: 'scale', delay: 0.2, duration: 1.15, threshold: 0.14, once: true });
  useScrollReveal(newArrivalsRef, { type: 'fade-up', duration: 1.05, threshold: 0.14, once: true });

  return (
    <div className="w-full bg-transparent">
      {/* New Hero Section: Promotional Banner Grid */}
      <section ref={heroRef} className="pt-24 pb-12">
        <div className="container mx-auto">
          {!loading && <PromoBannerGrid banners={banners} />}
          {loading && (
            <div className="w-full h-[80vh] bg-muted animate-pulse rounded-3xl" />
          )}
        </div>
      </section>

      {/* Premium Category Showcase */}
      <section ref={categoryRef}>
        <CategoryShowcase />
      </section>

      {/* Deal of the Day Section */}
      <section ref={dealRef}>
        <DealSection />
      </section>

      {/* NEW: Blueberry Style Dual Banners */}
      <section ref={dualBannerRef}>
        <DualPromoBanner />
      </section>

      {/* New Arrivals (Blueberry style) */}
      <section ref={newArrivalsRef}>
        <NewArrivalsSection />
      </section>

      {/* Feature Highlights (Template style, below New Arrivals) */}
      <section className="py-16">
        <div className="container mx-auto px-4 grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-5">
          <div className="rounded-3xl border border-border bg-white/80 backdrop-blur-sm px-6 py-8 text-center">
            <div className="mx-auto mb-4 h-14 w-14 flex items-center justify-center">
              <img src="/assets/img/services/1.png" alt="services-1" className="h-12 w-12 object-contain" />
            </div>
            <h4 className="text-3xl font-semibold text-foreground">Free Shipping</h4>
            <p className="mt-2 text-base text-muted-foreground">
              Free delivery on orders above ₹799 because great style should come effortlessly.
            </p>
          </div>

          <div className="rounded-3xl border border-border bg-white/80 backdrop-blur-sm px-6 py-8 text-center">
            <div className="mx-auto mb-4 h-14 w-14 flex items-center justify-center">
              <img src="/assets/img/services/2.png" alt="services-2" className="h-12 w-12 object-contain" />
            </div>
            <h4 className="text-3xl font-semibold text-foreground">24x7 Support</h4>
            <p className="mt-2 text-base text-muted-foreground">
              Need help? Our support team is available anytime to assist you instantly.
            </p>
          </div>

          <div className="rounded-3xl border border-border bg-white/80 backdrop-blur-sm px-6 py-8 text-center">
            <div className="mx-auto mb-4 h-14 w-14 flex items-center justify-center">
              <img src="/assets/img/services/3.png" alt="services-3" className="h-12 w-12 object-contain" />
            </div>
            <h4 className="text-3xl font-semibold text-foreground">Simple Return</h4>
            <p className="mt-2 text-base text-muted-foreground">
              Shop with confidence—easy 7-day returns & exchanges, refer{' '}
              <Link to="/return-and-refund-policy/" className="text-primary hover:underline font-medium">
                Return & Refund Policy
              </Link>
              .
            </p>
          </div>

          <div className="rounded-3xl border border-border bg-white/80 backdrop-blur-sm px-6 py-8 text-center">
            <div className="mx-auto mb-4 h-14 w-14 flex items-center justify-center">
              <img src="/assets/img/services/4.png" alt="services-4" className="h-12 w-12 object-contain" />
            </div>
            <h4 className="text-3xl font-semibold text-foreground">Payment Secure</h4>
            <p className="mt-2 text-base text-muted-foreground">
              Secure checkout with industry-grade encryption for complete peace of mind.
            </p>
          </div>
        </div>
      </section>
    </div>
  );
};
