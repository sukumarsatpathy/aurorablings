import { useLayoutEffect } from 'react';
import type { RefObject } from 'react';
import { gsap, initGsap, shouldAnimate } from './gsapConfig';

interface FadeInOptions {
  duration?: number;
  delay?: number;
  from?: gsap.TweenVars;
  to?: gsap.TweenVars;
}

export const useFadeIn = <T extends HTMLElement>(ref: RefObject<T | null>, options: FadeInOptions = {}) => {
  useLayoutEffect(() => {
    if (!ref.current || !shouldAnimate()) {
      return;
    }

    initGsap();

    const ctx = gsap.context(() => {
      gsap.fromTo(
        ref.current,
        { autoAlpha: 0, ...options.from },
        {
          autoAlpha: 1,
          duration: options.duration ?? 0.65,
          delay: options.delay ?? 0,
          ease: 'power2.out',
          ...options.to,
        }
      );
    }, ref);

    return () => ctx.revert();
  }, [ref, options.delay, options.duration, options.from, options.to]);
};
