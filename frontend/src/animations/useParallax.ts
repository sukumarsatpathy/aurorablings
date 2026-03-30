import { useLayoutEffect } from 'react';
import type { RefObject } from 'react';
import { gsap, initGsap, shouldAnimate } from './gsapConfig';

interface ParallaxOptions {
  yPercent?: number;
  start?: string;
  end?: string;
  scrub?: number;
}

export const useParallax = <T extends HTMLElement>(ref: RefObject<T | null>, options: ParallaxOptions = {}) => {
  useLayoutEffect(() => {
    if (!ref.current || !shouldAnimate()) {
      return;
    }

    initGsap();

    const ctx = gsap.context(() => {
      gsap.fromTo(
        ref.current,
        { yPercent: -(options.yPercent ?? 8) },
        {
          yPercent: options.yPercent ?? 8,
          ease: 'none',
          scrollTrigger: {
            trigger: ref.current,
            start: options.start ?? 'top bottom',
            end: options.end ?? 'bottom top',
            scrub: options.scrub ?? 1,
          },
        }
      );
    }, ref);

    return () => ctx.revert();
  }, [ref, options.end, options.scrub, options.start, options.yPercent]);
};
