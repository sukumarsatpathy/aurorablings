import { useLayoutEffect } from 'react';
import type { RefObject } from 'react';
import { gsap, initGsap, shouldAnimate } from './gsapConfig';

export type AnimationType = 'fade-up' | 'fade-down' | 'fade-left' | 'fade-right' | 'scale' | 'blur';

interface ScrollRevealOptions {
  type?: AnimationType;
  delay?: number;
  duration?: number;
  stagger?: number;
  threshold?: number;
  scrub?: boolean | number;
  once?: boolean;
  start?: string;
  end?: string;
}

export const useScrollReveal = <T extends HTMLElement>(
  ref: RefObject<T | null>,
  options: ScrollRevealOptions = {}
) => {
  const {
    type = 'fade-up',
    delay = 0,
    duration = 0.8,
    stagger = 0.1,
    threshold = 0.1,
    scrub = false,
    once = false,
    start,
    end,
  } = options;

  useLayoutEffect(() => {
    if (!ref.current || !shouldAnimate()) {
      return;
    }

    initGsap();

    const element = ref.current;
    const ctx = gsap.context(() => {
      // Define initial state based on type
      let initialVars: gsap.TweenVars = { autoAlpha: 0 };
      let activeVars: gsap.TweenVars = { 
        autoAlpha: 1, 
        duration, 
        delay, 
        ease: 'power3.out',
        overwrite: 'auto'
      };

      switch (type) {
        case 'fade-up':
          initialVars.y = 50;
          activeVars.y = 0;
          break;
        case 'fade-down':
          initialVars.y = -50;
          activeVars.y = 0;
          break;
        case 'fade-left':
          initialVars.x = 50;
          activeVars.x = 0;
          break;
        case 'fade-right':
          initialVars.x = -50;
          activeVars.x = 0;
          break;
        case 'scale':
          initialVars.scale = 0.9;
          activeVars.scale = 1;
          break;
        case 'blur':
          initialVars.filter = 'blur(10px)';
          activeVars.filter = 'blur(0px)';
          break;
      }

      // If there are children to stagger, apply to them instead or in addition
      const children = element.querySelectorAll('[data-scroll-item]');
      const target = children.length > 0 ? children : element;

      if (children.length > 0) {
        activeVars.stagger = stagger;
      }

      gsap.fromTo(target, initialVars, {
        ...activeVars,
        scrollTrigger: {
          trigger: element,
          start: start ?? `top bottom-=${threshold * 100}%`,
          end: end ?? `bottom top+=${threshold * 100}%`,
          toggleActions: once 
            ? 'play none none none' 
            : 'play reverse play reverse', // This handles the "disappear on scroll up"
          scrub: scrub,
        },
      });
    }, ref);

    return () => ctx.revert();
  }, [ref, type, delay, duration, stagger, threshold, scrub, once, start, end]);
};
