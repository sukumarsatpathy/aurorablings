import { useEffect, useMemo, useRef, type CSSProperties } from 'react';
import { Link } from 'react-router-dom';
import { gsap } from '@/animations/gsapConfig';
import { usePromoBanners } from '@/hooks/usePromoBanners';
import type { PromoBanner } from '@/types/promo';
import { OptimizedImage } from '@/components/ui/OptimizedImage';
import styles from './DualPromoBanner.module.css';

import snackIcon from '@/assets/icon-snacks.png';
import veggieIcon from '@/assets/icon-vegetables.png';

const HERO_IMAGE_DEFAULT = '/media/banner-1200.webp';
const HERO_IMAGE_SRCSET_DEFAULT =
  '/media/banner-480.webp 480w, /media/banner-768.webp 768w, /media/banner-1200.webp 1200w';
const HERO_IMAGE_SIZES = '(max-width: 768px) 100vw, 1200px';

const withSrcSet = (banner: PromoBanner | undefined, fallback: string) => {
  const src = banner?.image_large || banner?.image || fallback;
  const small = banner?.image_small;
  const medium = banner?.image_medium;
  const large = banner?.image_large || banner?.image;
  const srcSet =
    [small ? `${small} 480w` : '', medium ? `${medium} 768w` : '', large ? `${large} 1200w` : '']
      .filter(Boolean)
      .join(', ') || undefined;
  return { src, srcSet };
};

const DualPromoBanner = () => {
  const { banners } = usePromoBanners();
  const sectionRef = useRef<HTMLElement | null>(null);
  const cardsRef = useRef<Array<HTMLDivElement | null>>([]);

  const fallbackLeft: PromoBanner = useMemo(
    () => ({
      id: 'fallback-dual-left',
      position: 'dual-banner-left',
      title: 'Tasty Snack & Fast food',
      subtitle: 'The flavour of something special',
      cta_label: 'Shop Now',
      cta_url: '/products/',
      image: HERO_IMAGE_DEFAULT,
      image_small: '/media/banner-480.webp',
      image_medium: '/media/banner-768.webp',
      image_large: HERO_IMAGE_DEFAULT,
      bg_color: '#fbf2e5',
      shape_color: '#f4dab4',
    }),
    []
  );

  const fallbackRight: PromoBanner = useMemo(
    () => ({
      id: 'fallback-dual-right',
      position: 'dual-banner-right',
      title: 'Fresh Fruits & Vegetables',
      subtitle: 'A healthy meal for every one',
      cta_label: 'Shop Now',
      cta_url: '/products/',
      image: veggieIcon,
      bg_color: '#ffdce5',
      shape_color: '#f9bac6',
    }),
    []
  );

  const leftBanner = useMemo(
    () => banners.find((b) => b.position === 'dual-banner-left') || fallbackLeft,
    [banners, fallbackLeft]
  );
  const rightBanner = useMemo(
    () => banners.find((b) => b.position === 'dual-banner-right') || fallbackRight,
    [banners, fallbackRight]
  );

  useEffect(() => {
    const ctx = gsap.context(() => {
      gsap.fromTo(
        cardsRef.current,
        { y: 50, opacity: 0 },
        {
          y: 0,
          opacity: 1,
          duration: 1,
          stagger: 0.2,
          ease: 'power2.out',
          scrollTrigger: {
            trigger: sectionRef.current,
            start: 'top 80%',
            once: true,
          },
        }
      );
    }, sectionRef);

    return () => ctx.revert();
  }, [banners.length]);

  const renderBanner = (
    banner: PromoBanner | undefined,
    defaultIcon: string,
    index: number,
    priority = false
  ) => {
    if (!banner) return null;

    const bannerStyle = {
      backgroundColor: banner.bg_color || '#fbf2e5',
      ['--shape-color' as any]: banner.shape_color || '#f4dab4',
    } as CSSProperties;

    const { src, srcSet } = withSrcSet(banner, defaultIcon);
    const resolvedSrcSet = priority ? srcSet || HERO_IMAGE_SRCSET_DEFAULT : srcSet;

    return (
      <div
        key={banner.id}
        ref={(el) => {
          cardsRef.current[index] = el;
        }}
        className={styles.col}
      >
        <div className={styles.bannerBox} style={bannerStyle}>
          <div className={styles.innerBox}>
            <div className={styles.sideImage}>
              <div className={styles.imageFrame}>
                <OptimizedImage
                  src={src}
                  srcSet={resolvedSrcSet}
                  sizes={HERO_IMAGE_SIZES}
                  alt={banner.title || 'Promotional banner'}
                  className={styles.image}
                  width={1200}
                  height={700}
                  priority={priority}
                  loading={priority ? 'eager' : 'lazy'}
                  decoding={priority ? 'sync' : 'async'}
                  fallbackSrc={defaultIcon}
                  style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                />
              </div>
            </div>
            <div className={styles.contact}>
              <h5>{banner.title}</h5>
              {banner.subtitle && <p className="text-sm font-medium">{banner.subtitle}</p>}
              <Link
                to={banner.cta_url || '#'}
                className="mt-4 inline-block px-6 py-2 bg-[#6c7fd8] text-white rounded-lg font-semibold hover:bg-[#5a6bc2] transition-colors"
              >
                {banner.cta_label || 'Shop Now'}
              </Link>
            </div>
          </div>
        </div>
      </div>
    );
  };

  return (
    <section ref={sectionRef} className={styles.section}>
      <div className="container mx-auto px-4">
        <div className={styles.row}>
          {renderBanner(leftBanner, snackIcon, 0, true)}
          {renderBanner(rightBanner, veggieIcon, 1, false)}
        </div>
      </div>
    </section>
  );
};

export default DualPromoBanner;

