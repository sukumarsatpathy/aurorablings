import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import catalogService from '@/services/api/catalog';

/**
 * The hover image swap on product cards.
 *
 * A card starts with the one or two pictures the listing endpoint already
 * returned. When a pointer settles on it, the rest of that product's gallery is
 * fetched once and the card cycles through them.
 *
 * Four decisions in here are about not making the site slower, on a server where
 * Postgres, Redis, Django and Celery share a single core:
 *
 *   1. Nothing is fetched until hover, so first paint and LCP are untouched.
 *   2. Hover has to be *meant*. Sweeping a mouse across a row of eight cards
 *      used to fire eight requests; a short dwell means only the card you
 *      actually stopped on asks for anything.
 *   3. It asks for `gallery`, which is media rows and nothing else, rather than
 *      the full product detail with its variants, attributes and info items.
 *   4. It renders the medium rendition. The masters are 1800px and these cards
 *      are 300-400 CSS px wide; cycling four masters on 4G is exactly the kind
 *      of thing that makes a gallery feel worse than no gallery.
 *
 * On a touch device none of this runs at all: there is no hover there, so
 * fetching a gallery nobody can trigger is pure waste.
 */

/** How long a pointer must rest on a card before it counts as intent. */
const HOVER_INTENT_MS = 150;

/** A product with twelve photographs should not stream twelve photographs. */
const MAX_FRAMES = 4;

/** Dwell time on each frame once cycling starts. */
const FRAME_MS = 850;

export const supportsHover = (): boolean => {
  if (typeof window === 'undefined' || !window.matchMedia) return true;
  return window.matchMedia('(hover: hover) and (pointer: fine)').matches;
};

interface Options {
  /** Product id, for the gallery request. */
  productId?: string | null;
  /** Images the card already has — primary first, then the hover image. */
  baseImages: string[];
  /** Turn each media URL into something the browser can load. */
  normalize?: (raw?: string | null) => string;
}

interface HoverGallery {
  /** Every frame to render, deduped and capped. Index 0 is the resting image. */
  images: string[];
  activeIndex: number;
  /** Spread onto the card's root element. */
  hoverProps: {
    onMouseEnter: () => void;
    onMouseLeave: () => void;
  };
}

const identity = (raw?: string | null) => String(raw || '').trim();

export function useHoverGallery({ productId, baseImages, normalize = identity }: Options): HoverGallery {
  const [isHovered, setIsHovered] = useState(false);
  const [extraImages, setExtraImages] = useState<string[]>([]);
  const [activeIndex, setActiveIndex] = useState(0);
  const fetchedRef = useRef(false);
  const intentTimerRef = useRef<number | null>(null);

  const images = useMemo(() => {
    const seen = new Set<string>();
    const ordered = [...baseImages, ...extraImages]
      .map((image) => normalize(image))
      .filter(Boolean);
    const unique = ordered.filter((image) => {
      if (seen.has(image)) return false;
      seen.add(image);
      return true;
    });
    return unique.slice(0, MAX_FRAMES);
    // `normalize` is a module-level function at every call site; excluded so a
    // caller defining it inline can't re-run this on every render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [baseImages, extraImages]);

  const clearIntent = useCallback(() => {
    if (intentTimerRef.current !== null) {
      window.clearTimeout(intentTimerRef.current);
      intentTimerRef.current = null;
    }
  }, []);

  const loadGallery = useCallback(async () => {
    if (fetchedRef.current || !productId) return;
    fetchedRef.current = true;
    try {
      const response = await catalogService.getProductGallery(productId);
      const rows = Array.isArray(response?.data) ? response.data : [];
      setExtraImages(
        rows
          .map((row: any) => row?.image_medium || row?.image)
          .filter((image: unknown): image is string => Boolean(image))
      );
    } catch {
      // A card that can't load its gallery keeps the picture it already has.
      setExtraImages([]);
    }
  }, [productId]);

  const onMouseEnter = useCallback(() => {
    if (!supportsHover()) return;
    setIsHovered(true);
    if (fetchedRef.current) return;
    clearIntent();
    intentTimerRef.current = window.setTimeout(() => {
      void loadGallery();
    }, HOVER_INTENT_MS);
  }, [clearIntent, loadGallery]);

  const onMouseLeave = useCallback(() => {
    clearIntent();
    setIsHovered(false);
  }, [clearIntent]);

  useEffect(() => clearIntent, [clearIntent]);

  useEffect(() => {
    if (!isHovered || images.length <= 1) {
      setActiveIndex(0);
      return;
    }
    const intervalId = window.setInterval(() => {
      setActiveIndex((current) => (current + 1) % images.length);
    }, FRAME_MS);
    return () => window.clearInterval(intervalId);
  }, [images.length, isHovered]);

  return { images, activeIndex, hoverProps: { onMouseEnter, onMouseLeave } };
}

export default useHoverGallery;
