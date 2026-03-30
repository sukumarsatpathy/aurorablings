import { useEffect, useRef, type CSSProperties } from 'react';
import { Link } from 'react-router-dom';
import { gsap } from '@/animations/gsapConfig';
import { usePromoBanners } from '@/hooks/usePromoBanners';
import type { PromoBanner } from '@/types/promo';
import styles from './DualPromoBanner.module.css';

// Default assets if none provided in admin
import snackIcon from '@/assets/icon-snacks.png';
import veggieIcon from '@/assets/icon-vegetables.png';

const DualPromoBanner = () => {
    const { banners, loading } = usePromoBanners();
    const sectionRef = useRef<HTMLElement | null>(null);
    const cardsRef = useRef<Array<HTMLDivElement | null>>([]);

    const fallbackLeft: PromoBanner = {
        id: 'fallback-dual-left',
        position: 'dual-banner-left',
        title: 'Tasty Snack & Fast food',
        subtitle: 'The flavour of something special',
        cta_label: 'Shop Now',
        cta_url: '/products/',
        image: snackIcon,
        bg_color: '#fbf2e5',
        shape_color: '#f4dab4',
    };

    const fallbackRight: PromoBanner = {
        id: 'fallback-dual-right',
        position: 'dual-banner-right',
        title: 'Fresh Fruits & Vegetables',
        subtitle: 'A healthy meal for every one',
        cta_label: 'Shop Now',
        cta_url: '/products/',
        image: veggieIcon,
        bg_color: '#ffdce5',
        shape_color: '#f9bac6',
    };

    useEffect(() => {
        if (loading || banners.length === 0) return;

        const ctx = gsap.context(() => {
            gsap.fromTo(cardsRef.current,
                { y: 50, opacity: 0 },
                {
                    y: 0,
                    opacity: 1,
                    duration: 1,
                    stagger: 0.2,
                    ease: "power2.out",
                    scrollTrigger: {
                        trigger: sectionRef.current,
                        start: "top 80%",
                        once: true
                    }
                }
            );
        }, sectionRef);

        return () => ctx.revert();
    }, [loading, banners]);

    if (loading) return null;

    const leftBanner = banners.find(b => b.position === 'dual-banner-left') || fallbackLeft;
    const rightBanner = banners.find(b => b.position === 'dual-banner-right') || fallbackRight;

    const renderBanner = (banner: PromoBanner | undefined, defaultIcon: string, index: number) => {
        if (!banner) return null;

        const bannerStyle = {
            backgroundColor: banner.bg_color || '#fbf2e5',
            ['--shape-color' as any]: banner.shape_color || '#f4dab4'
        } as CSSProperties;

        return (
            <div 
                key={banner.id}
                ref={(el) => {
                    cardsRef.current[index] = el;
                }}
                className={styles.col}
            >
                <div 
                    className={styles.bannerBox} 
                    style={bannerStyle}
                >
                    <div className={styles.innerBox}>
                        <div className={styles.sideImage}>
                            <div className={styles.imageFrame}>
                                <img src={banner.image || defaultIcon} alt={banner.title} />
                            </div>
                        </div>
                        <div className={styles.contact}>
                            <h5>{banner.title}</h5>
                            {banner.subtitle && <p className="text-sm font-medium">{banner.subtitle}</p>}
                            <Link to={banner.cta_url || '#'} className={"mt-4 inline-block px-6 py-2 bg-[#6c7fd8] text-white rounded-lg font-semibold hover:bg-[#5a6bc2] transition-colors"}>
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
                    {renderBanner(leftBanner, snackIcon, 0)}
                    {renderBanner(rightBanner, veggieIcon, 1)}
                </div>
            </div>
        </section>
    );
};

export default DualPromoBanner;
