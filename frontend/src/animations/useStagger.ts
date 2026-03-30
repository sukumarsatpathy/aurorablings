import { useLayoutEffect } from 'react';
import type { RefObject } from 'react';
import { gsap, initGsap, shouldAnimate } from './gsapConfig';

interface StaggerOptions {
  itemSelector?: string;
  y?: number;
  stagger?: number;
  duration?: number;
  start?: string;
  once?: boolean;
  trigger?: Element | string;
}

export const useStagger = <T extends HTMLElement>(
  containerRef: RefObject<T | null>,
  options: StaggerOptions = {}
) => {
  useLayoutEffect(() => {
    if (!containerRef.current || !shouldAnimate()) {
      return;
    }

    initGsap();

    const ctx = gsap.context(() => {
      const nodes = gsap.utils.toArray<HTMLElement>(
        options.itemSelector ?? '[data-stagger-item]',
        containerRef.current ?? undefined
      );

      if (!nodes.length) {
        return;
      }

      gsap.fromTo(
        nodes,
        { y: options.y ?? 20, autoAlpha: 0 },
        {
          y: 0,
          autoAlpha: 1,
          duration: options.duration ?? 0.7,
          ease: 'power2.out',
          stagger: options.stagger ?? 0.08,
          scrollTrigger: {
            trigger: options.trigger ?? containerRef.current,
            start: options.start ?? 'top 82%',
            once: options.once ?? true,
          },
        }
      );
    }, containerRef);

    return () => ctx.revert();
  }, [containerRef, options.duration, options.itemSelector, options.once, options.start, options.stagger, options.trigger, options.y]);
};
