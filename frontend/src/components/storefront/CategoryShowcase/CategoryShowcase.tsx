import React, { useRef, useEffect, useState, useCallback } from 'react';
import { Link } from 'react-router-dom';
// WebP renditions of the old bg-img.png (1.7 MB) — 115 KB at 1024px,
// 63 KB at 640px. The PNG is kept in the repo only as the editable master;
// nothing imports it.
import heroImg from '@/assets/bg-img.webp';
import heroImgSmall from '@/assets/bg-img-640.webp';
import { Circle, ChevronLeft, ChevronRight } from 'lucide-react';
import { gsap } from '@/animations/gsapConfig';
import catalogService from '@/services/api/catalog';
import { Badge } from '@/components/ui/Badge';

interface Category {
    id: string;
    title: string;
    count: string;
    is_coming_soon: boolean;
    icon?: React.ElementType;
    image?: string;
    href: string;
    color: 'pink' | 'green';
}

const CARD_GAP = 24;

const getVisibleCount = () => {
    if (typeof window === 'undefined') return 4;
    // Two per view on phones: one card at a time left a mostly empty white box.
    if (window.innerWidth < 640) return 2;
    if (window.innerWidth < 1024) return 3;
    return 4;
};

const CategoryShowcase: React.FC = () => {
    const [categories, setCategories] = useState<Category[]>([]);
    const [loading, setLoading] = useState(true);
    const [cardPxWidth, setCardPxWidth] = useState(0);
    const [visibleCount, setVisibleCount] = useState(getVisibleCount);
    // Which arrows make sense right now. Derived from the real scroll position,
    // so a swipe, a trackpad flick or a scrollbar drag all keep them honest.
    const [canPrev, setCanPrev] = useState(false);
    const [canNext, setCanNext] = useState(false);

    const trackRef = useRef<HTMLDivElement>(null);
    const titleRef = useRef<HTMLHeadingElement>(null);
    const cardsRef = useRef<(HTMLDivElement | null)[]>([]);

    useEffect(() => {
        const loadCategories = async () => {
            try {
                setLoading(true);
                const raw = await catalogService.listAllCategories({ latest: true });

                // Map API categories to UI format
                // Shoppable categories first; "Coming Soon" / empty ones after (stable sort).
                const isComingSoon = (c: (typeof raw)[number]) => !!c.is_coming_soon || !(c.product_count || 0);
                const mapped: Category[] = raw
                    .filter(c => c.is_active)
                    .sort((a, b) => Number(isComingSoon(a)) - Number(isComingSoon(b)))
                    .map((c, idx) => ({
                        id: c.id,
                        title: c.name,
                        count: `${c.product_count || 0} items`,
                        is_coming_soon: !!c.is_coming_soon,
                        image: c.image,
                        href: `/products/?category=${c.slug}`,
                        color: idx % 2 === 0 ? 'pink' : 'green',
                    }));

                setCategories(mapped);
            } catch (err) {
                console.error("Failed to load categories:", err);
            } finally {
                setLoading(false);
            }
        };
        loadCategories();
    }, []);

    useEffect(() => {
        if (!titleRef.current || categories.length === 0) return;

        const ctx = gsap.context(() => {
            // Short and subtle: long, delayed reveals read as empty space while scrolling.
            gsap.fromTo(titleRef.current,
                { y: 16, opacity: 0 },
                {
                    y: 0,
                    opacity: 1,
                    duration: 0.5,
                    ease: "power2.out",
                    scrollTrigger: {
                        trigger: titleRef.current,
                        start: "top 90%",
                        once: true
                    }
                }
            );

            const validCards = cardsRef.current
                .slice(0, categories.length)
                .filter(c => c !== null);
            if (validCards.length > 0) {
                gsap.fromTo(validCards,
                    { y: 16, opacity: 0 },
                    {
                        y: 0,
                        opacity: 1,
                        duration: 0.45,
                        stagger: 0.06,
                        ease: "power2.out",
                        scrollTrigger: {
                            trigger: trackRef.current,
                            start: "top 80%",
                            once: true
                        }
                    }
                );
            }
        }, trackRef);

        return () => {
            ctx.revert();
        };
    }, [categories]);

    // Manual scroller: the browser owns the scrolling (touch swipe, trackpad,
    // shift+wheel, scrollbar, keyboard), we only size the cards and drive the
    // arrows. No autoplay and no duplicated cards, so each category appears once.
    useEffect(() => {
        const measure = () => {
            const newVisible = getVisibleCount();
            setVisibleCount(newVisible);
            if (trackRef.current) {
                const containerW = trackRef.current.clientWidth;
                const w = (containerW - CARD_GAP * (newVisible - 1)) / newVisible;
                setCardPxWidth(w);
            }
        };
        measure();
        window.addEventListener('resize', measure);
        return () => window.removeEventListener('resize', measure);
    }, [categories.length]);

    const updateArrows = useCallback(() => {
        const el = trackRef.current;
        if (!el) return;
        // 2px of slack absorbs sub-pixel rounding at the ends.
        setCanPrev(el.scrollLeft > 2);
        setCanNext(el.scrollLeft + el.clientWidth < el.scrollWidth - 2);
    }, []);

    useEffect(() => {
        updateArrows();
    }, [updateArrows, cardPxWidth, categories.length]);

    const scrollByCards = useCallback((direction: 1 | -1) => {
        const el = trackRef.current;
        if (!el) return;
        // One "page" of cards per click, so nothing is skipped or half-shown.
        const step = (cardPxWidth > 0 ? cardPxWidth + CARD_GAP : el.clientWidth) * Math.max(1, visibleCount - 1);
        el.scrollBy({ left: direction * step, behavior: 'smooth' });
    }, [cardPxWidth, visibleCount]);

    const fallbackWidth = `calc((100% - ${CARD_GAP * (visibleCount - 1)}px) / ${visibleCount})`;
    const showArrows = canPrev || canNext;

    if (loading && categories.length === 0) {
        return <div className="py-24 text-center text-muted-foreground">Loading categories...</div>;
    }

    if (!loading && categories.length === 0) {
        return null; // Don't show empty segment
    }

    return (
        <section className="py-12">
            <div className="container mx-auto px-4">
                <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">

                    {/* Left: Hero image */}
                    <div className="lg:col-span-5 flex">
                        <div className="relative w-full lg:w-[536px] lg:h-[526px] rounded-[30px] overflow-hidden min-h-[340px]">
                            <img
                                src={heroImg}
                                srcSet={`${heroImgSmall} 640w, ${heroImg} 1024w`}
                                sizes="(max-width: 1024px) 100vw, 536px"
                                alt="Category"
                                className="w-full h-full object-cover block rounded-[30px]"
                                width={536}
                                height={526}
                                loading="lazy"
                                decoding="async"
                            />
                        </div>
                    </div>

                    {/* Right: Title + Carousel */}
                    <div className="lg:col-span-7 flex flex-col gap-6">

                        {/* Section heading */}
                        <div>
                            <h2
                                ref={titleRef}
                                className="text-5xl sm:text-6xl lg:text-7xl font-extrabold leading-[1.05] tracking-tight text-gray-950 select-none"
                            >
                                Explore<br /><span className="text-[#517b4b]">Categories</span>
                            </h2>
                        </div>

                        {/* Carousel */}
                        <div
                            className="relative z-[1] lg:-ml-[30%] lg:mt-23 p-6 pt-7 bg-white rounded-[30px]"
                        >
                            <div
                                ref={trackRef}
                                onScroll={updateArrows}
                                role="region"
                                aria-label="Product categories"
                                tabIndex={0}
                                className="category-scroller flex overflow-x-auto snap-x snap-mandatory scroll-smooth pt-2 pb-3 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#517b4b]/40 rounded-[20px]"
                                style={{ gap: `${CARD_GAP}px` }}
                            >
                                {categories.map((cat, idx) => (
                                    <div
                                        key={cat.id}
                                        ref={el => { cardsRef.current[idx] = el; }}
                                        className="flex-shrink-0 snap-start"
                                        style={{ width: cardPxWidth > 0 ? `${cardPxWidth}px` : fallbackWidth }}
                                    >
                                        <Link to={cat.href} className="block group" draggable={false}>
                                            <div
                                                className={`flex flex-col items-center justify-center w-[250px] max-w-full h-[180px] mx-auto p-6 rounded-[20px] text-center cursor-pointer transition-all duration-300 hover:-translate-y-1.5 ${cat.color === 'pink' ? 'bg-category-pink' : 'bg-category-green'
                                                    }`}
                                            >
                                                <div className="w-16 h-16 sm:w-20 sm:h-20 flex items-center justify-center mb-1.5 text-primary group-hover:animate-zoom-in-out">
                                                    {cat.image ? (
                                                        <img
                                                            src={cat.image}
                                                            alt={cat.title}
                                                            className="w-10 h-10 sm:w-12 sm:h-12 object-contain"
                                                            draggable={false}
                                                        />
                                                    ) : cat.icon ? (
                                                        <cat.icon className="w-10 h-10 sm:w-12 sm:h-12 stroke-[1.5]" />
                                                    ) : (
                                                        <Circle className="w-10 h-10 sm:w-12 sm:h-12 stroke-[1.5]" />
                                                    )}
                                                </div>
                                                <h5 className="text-sm sm:text-base font-bold text-foreground mb-1 whitespace-nowrap overflow-hidden text-ellipsis w-full px-2">
                                                    {cat.title}
                                                </h5>
                                                {cat.is_coming_soon ? (
                                                    <Badge variant="surface" className="text-[10px] bg-amber-50 text-amber-600 border-amber-100 font-bold px-2 py-0">
                                                        Coming Soon
                                                    </Badge>
                                                ) : (
                                                    <p className="text-xs text-muted-foreground font-medium">{cat.count}</p>
                                                )}
                                            </div>
                                        </Link>
                                    </div>
                                ))}
                            </div>

                            {showArrows && (
                                <div className="flex justify-end gap-2 mt-3">
                                    <button
                                        type="button"
                                        onClick={() => scrollByCards(-1)}
                                        disabled={!canPrev}
                                        aria-label="Previous categories"
                                        className="w-10 h-10 rounded-full border border-gray-200 flex items-center justify-center text-gray-500 hover:bg-[#517b4b] hover:text-white hover:border-[#517b4b] transition-all duration-300 disabled:opacity-40 disabled:pointer-events-none"
                                    >
                                        <ChevronLeft size={20} />
                                    </button>
                                    <button
                                        type="button"
                                        onClick={() => scrollByCards(1)}
                                        disabled={!canNext}
                                        aria-label="Next categories"
                                        className="w-10 h-10 rounded-full border border-gray-200 flex items-center justify-center text-gray-500 hover:bg-[#517b4b] hover:text-white hover:border-[#517b4b] transition-all duration-300 disabled:opacity-40 disabled:pointer-events-none"
                                    >
                                        <ChevronRight size={20} />
                                    </button>
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            </div>
        </section>
    );
};

export default CategoryShowcase;
