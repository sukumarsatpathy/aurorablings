import { useLayoutEffect } from 'react';
import type { RefObject } from 'react';
import { gsap, initGsap, shouldAnimate } from './gsapConfig';

interface TextRevealOptions {
  stagger?: number;
  duration?: number;
  y?: number;
  delay?: number;
}

export const useTextReveal = <T extends HTMLElement>(ref: RefObject<T | null>, options: TextRevealOptions = {}) => {
  useLayoutEffect(() => {
    if (!ref.current || !shouldAnimate()) {
      return;
    }

    initGsap();

    const el = ref.current;
    const original = el.textContent ?? '';
    const words = original.split(' ').filter(Boolean);
    const fragment = document.createDocumentFragment();

    words.forEach((word, idx) => {
      const wrapper = document.createElement('span');
      wrapper.style.display = 'inline-block';
      wrapper.style.overflow = 'hidden';

      const inner = document.createElement('span');
      inner.style.display = 'inline-block';
      inner.textContent = `${word}${idx === words.length - 1 ? '' : ' '}`;

      wrapper.appendChild(inner);
      fragment.appendChild(wrapper);
    });

    el.textContent = '';
    el.appendChild(fragment);

    const targets = Array.from(el.querySelectorAll('span > span'));

    const ctx = gsap.context(() => {
      gsap.fromTo(
        targets,
        { yPercent: options.y ?? 110, autoAlpha: 0 },
        {
          yPercent: 0,
          autoAlpha: 1,
          duration: options.duration ?? 0.85,
          delay: options.delay ?? 0.15,
          ease: 'power3.out',
          stagger: options.stagger ?? 0.05,
        }
      );
    }, ref);

    return () => {
      ctx.revert();
      el.textContent = original;
    };
  }, [ref, options.delay, options.duration, options.stagger, options.y]);
};
