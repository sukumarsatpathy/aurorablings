import React, { useEffect, useRef, useState } from 'react';
import catalogService from '@/services/api/catalog';
import { Swiper, SwiperSlide } from 'swiper/react';
import { Autoplay, Navigation } from 'swiper/modules';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import { useScrollReveal } from '@/animations/useScrollReveal';

// Swiper styles
import 'swiper/css';
import 'swiper/css/navigation';

import type { DealProduct } from '@/types/product';
import { DealProductCard } from './DealProductCard';
import { DealTimer } from './DealTimer';

export const DealSection: React.FC = () => {
  const [deals, setDeals] = useState<DealProduct[]>([]);
  const [loading, setLoading] = useState(true);
  const sectionRef = useRef<HTMLElement>(null);
  const headerRef = useRef<HTMLDivElement>(null);
  const sliderRef = useRef<HTMLDivElement>(null);

  useScrollReveal(sectionRef, { type: 'fade-up', duration: 1, threshold: 0.1, once: true });
  useScrollReveal(headerRef, { type: 'fade-up', duration: 0.9, threshold: 0.08, once: true });
  useScrollReveal(sliderRef, { type: 'scale', duration: 0.95, threshold: 0.12, once: true, stagger: 0.08 });

  useEffect(() => {
    const fetchDeals = async () => {
      try {
        const res = await catalogService.listDeals();
        
        // Comprehensive extraction logic mirroring AdminTable's extractRows
        let dataArray: DealProduct[] = [];
        if (Array.isArray(res)) {
          dataArray = res;
        } else if (res?.data) {
          if (Array.isArray(res.data)) {
            dataArray = res.data;
          } else if (Array.isArray(res.data.results)) {
            dataArray = res.data.results;
          }
        } else if (Array.isArray(res?.results)) {
          dataArray = res.results;
        }
        
        setDeals(dataArray);
      } catch (error) {
        console.error('Failed to fetch deals:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchDeals();
  }, []);

  const getEarliestEndDate = () => {
    if (!Array.isArray(deals) || deals.length === 0) return undefined;
    
    // Collect all valid end dates from all active variants across all products
    const allDates = deals.flatMap(p => 
      (p.variants || [])
        .filter(v => v.has_active_offer && v.offer_ends_at)
        .map(v => v.offer_ends_at as string)
    );
    
    if (allDates.length === 0) return undefined;
    
    // Return the minimum (earliest) date
    return allDates.sort()[0];
  };

  return (
    <section ref={sectionRef} className="py-16 md:py-24 bg-white overflow-hidden">
      <div className="container mx-auto px-4">
        {loading ? (
          <div className="h-96 w-full animate-pulse bg-gray-50 rounded-3xl" />
        ) : deals.length === 0 ? null : (
          <>
            {/* Header */}
            <div ref={headerRef} className="flex flex-col md:flex-row md:items-end justify-between gap-6 mb-12">
              <div className="space-y-3">
                <h2 className="text-3xl md:text-4xl font-bold text-gray-950 flex items-center gap-2">
                  Deal Of The <span className="text-[#517b4b]">Day</span>
                </h2>
              </div>
              
              <div className="flex items-center gap-8">
                <DealTimer endDate={getEarliestEndDate()} />
                
                {/* Custom Navigation */}
                <div className="hidden md:flex items-center gap-2">
                  <button className="deal-prev w-10 h-10 rounded-full border border-gray-100 flex items-center justify-center text-gray-400 hover:bg-[#517b4b] hover:text-white hover:border-[#517b4b] transition-all duration-300">
                    <ChevronLeft size={20} />
                  </button>
                  <button className="deal-next w-10 h-10 rounded-full border border-gray-100 flex items-center justify-center text-gray-400 hover:bg-[#517b4b] hover:text-white hover:border-[#517b4b] transition-all duration-300">
                    <ChevronRight size={20} />
                  </button>
                </div>
              </div>
            </div>

            {/* Swiper Slider */}
            <div ref={sliderRef} className="relative">
              <Swiper
                modules={[Autoplay, Navigation]}
                spaceBetween={24}
                slidesPerView={1}
                navigation={{
                  prevEl: '.deal-prev',
                  nextEl: '.deal-next',
                }}
                autoplay={{
                  delay: 5000,
                  disableOnInteraction: false,
                }}
                breakpoints={{
                  640: { slidesPerView: 2 },
                  1024: { slidesPerView: 3 },
                  1280: { slidesPerView: 4 },
                }}
                className="!overflow-visible"
              >
                {deals.map((product) => (
                  <SwiperSlide key={product.id} className="h-auto" data-scroll-item>
                    <DealProductCard product={product} />
                  </SwiperSlide>
                ))}
              </Swiper>
            </div>
          </>
        )}
      </div>
    </section>
  );
};
