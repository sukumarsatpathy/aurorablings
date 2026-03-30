import { useLayoutEffect } from 'react';
import type { RefObject } from 'react';
import { gsap, initGsap, shouldAnimate } from './gsapConfig';

interface SlideUpOptions {
  y?: number;
  duration?: number;
  delay?: number;
  trigger?: Element | string;
  start?: string;
  once?: boolean;
}

export const useSlideUp = <T extends HTMLElement>(ref: RefObject<T | null>, options: SlideUpOptions = {}) => {
  useLayoutEffect(() => {
    if (!ref.current || !shouldAnimate()) {
      return;
    }

    initGsap();

    const ctx = gsap.context(() => {
      const scrollTrigger = {
        trigger: options.trigger ?? ref.current,
        start: options.start ?? 'top 85%',
        once: options.once ?? true,
      };

      gsap.fromTo(
        ref.current,
        { y: options.y ?? 26, autoAlpha: 0 },
        {
          y: 0,
          autoAlpha: 1,
          duration: options.duration ?? 0.8,
          delay: options.delay ?? 0,
          ease: 'power3.out',
          scrollTrigger,
        }
      );
    }, ref);

    return () => ctx.revert();
  }, [ref, options.delay, options.duration, options.once, options.start, options.trigger, options.y]);
};
