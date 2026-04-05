import React, { useRef, useEffect, useState, useCallback } from 'react';
import { Link } from 'react-router-dom';
import heroImg from '@/assets/bg-img.png';
import { Circle } from 'lucide-react';
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

const INTERVAL = 2500;
const CARD_GAP = 24;

const getVisibleCount = () => {
    if (typeof window === 'undefined') return 4;
    if (window.innerWidth < 640) return 1;
    if (window.innerWidth < 1024) return 2;
    return 4;
};

const CategoryShowcase: React.FC = () => {
    const [categories, setCategories] = useState<Category[]>([]);
    const [loading, setLoading] = useState(true);
    const [current, setCurrent] = useState(0);
    const [isResetting, setIsResetting] = useState(false);
    const [cardPxWidth, setCardPxWidth] = useState(0);
    const [visibleCount, setVisibleCount] = useState(getVisibleCount);

    const trackRef = useRef<HTMLDivElement>(null);
    const titleRef = useRef<HTMLHeadingElement>(null);
    const cardsRef = useRef<(HTMLDivElement | null)[]>([]);

    useEffect(() => {
        const loadCategories = async () => {
            try {
                setLoading(true);
                const raw = await catalogService.listAllCategories({ latest: true });

                // Map API categories to UI format
                const mapped: Category[] = raw
                    .filter(c => c.is_active)
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
            gsap.fromTo(titleRef.current,
                { y: 50, opacity: 0 },
                {
                    y: 0,
                    opacity: 1,
                    duration: 1,
                    delay: 0.6,
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
                    { rotateY: -90, opacity: 0, scale: 0.8 },
                    {
                        rotateY: 0,
                        opacity: 1,
                        scale: 1,
                        duration: 1,
                        delay: 0.2,
                        stagger: 0.1,
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

    const total = categories.length;
    const shouldLoop = total > visibleCount;
    const trackCategories = shouldLoop ? [...categories, ...categories] : categories;

    useEffect(() => {
        const measure = () => {
            const newVisible = getVisibleCount();
            setVisibleCount(newVisible);
            if (trackRef.current) {
                const containerW = trackRef.current.offsetWidth;
                const w = (containerW - CARD_GAP * (newVisible - 1)) / newVisible;
                setCardPxWidth(w);
            }
        };
        measure();
        window.addEventListener('resize', measure);
        return () => window.removeEventListener('resize', measure);
    }, [categories.length]);

    useEffect(() => {
        if (!shouldLoop) {
            setCurrent(0);
            setIsResetting(false);
        } else {
            setCurrent((c) => Math.min(c, total));
        }
    }, [shouldLoop, total]);

    useEffect(() => {
        if (!shouldLoop || cardPxWidth === 0) return;
        const timer = window.setTimeout(() => {
            setCurrent((value) => value + 1);
        }, INTERVAL);
        return () => window.clearTimeout(timer);
    }, [current, shouldLoop, cardPxWidth]);

    const handleTransitionEnd = useCallback(() => {
        if (!shouldLoop || current < total) return;
        setIsResetting(true);
        setCurrent(0);
    }, [current, shouldLoop, total]);

    useEffect(() => {
        if (!isResetting) return;
        const frame = window.requestAnimationFrame(() => {
            setIsResetting(false);
        });
        return () => window.cancelAnimationFrame(frame);
    }, [isResetting]);

    const offset = cardPxWidth > 0 ? current * (cardPxWidth + CARD_GAP) : 0;
    const fallbackWidth = `calc((100% - ${CARD_GAP * (visibleCount - 1)}px) / ${visibleCount})`;

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
                                alt="Category"
                                className="w-full h-full object-cover block rounded-[30px]"
                                width={536}
                                height={526}
                            />
                        </div>
                    </div>

                    {/* Right: Title + Carousel */}
                    <div className="lg:col-span-7 flex flex-col gap-6">

                        {/* Section heading */}
                        <div>
                            <h2
                                ref={titleRef}
                                className="text-6xl sm:text-7xl lg:text-8xl font-extrabold leading-[1.1] category-stroke-text select-none"
                            >
                                Explore<br />Categories
                            </h2>
                        </div>

                        {/* Carousel */}
                        <div
                            className="relative z-[1] lg:-ml-[30%] lg:mt-23 p-6 pt-7 bg-white rounded-[30px]"
                        >
                            <div className="overflow-hidden" ref={trackRef}>
                                <div
                                    className="flex ease-[cubic-bezier(0.4,0,0.2,1)]"
                                    onTransitionEnd={handleTransitionEnd}
                                    style={{
                                        gap: `${CARD_GAP}px`,
                                        transform: `translateX(-${offset}px)`,
                                        perspective: '2000px',
                                        transitionDuration: isResetting ? '0ms' : '500ms',
                                        transitionProperty: 'transform',
                                    }}
                                >
                                    {trackCategories.map((cat, idx) => (
                                        <div
                                            key={`${cat.id}-${idx}`}
                                            ref={el => { cardsRef.current[idx] = el; }}
                                            className="flex-shrink-0"
                                            style={{
                                                width: cardPxWidth > 0 ? `${cardPxWidth}px` : fallbackWidth,
                                                transformStyle: 'preserve-3d'
                                            }}
                                        >
                                            <Link to={cat.href} className="block group">
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
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </section>
    );
};

export default CategoryShowcase;
