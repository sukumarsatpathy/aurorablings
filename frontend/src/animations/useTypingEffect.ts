import { useLayoutEffect } from 'react';
import type { RefObject } from 'react';
import { gsap, ScrollTrigger, shouldAnimate } from './gsapConfig';

interface TypingEffectOptions {
  stagger?: number;
  duration?: number;
  delay?: number;
  once?: boolean;
}

// WeakMap survives Strict Mode remounts without adding a hook
const originalTextCache = new WeakMap<HTMLElement, string>();

export const useTypingEffect = <T extends HTMLElement>(
  ref: RefObject<T | null>,
  options: TypingEffectOptions = {}
) => {
  const { stagger = 0.05, duration = 0.1, delay = 0, once = true } = options;

  useLayoutEffect(() => {
    if (!ref.current || !shouldAnimate()) return;

    const el = ref.current;

    // Read and cache original text only on first mount
    if (!originalTextCache.has(el)) {
      const text = el.innerText;
      if (!text.trim()) return;
      originalTextCache.set(el, text);
    }

    const text = originalTextCache.get(el)!;
    if (!text.trim()) return;

    // Split into character spans preserving line breaks
    const lines = text.split('\n');
    el.innerHTML = lines.map((line, i) => {
      const chars = line.split('').map(char =>
        `<span class="typing-char" style="opacity:0;display:inline-block;white-space:pre;">${char === ' ' ? '&nbsp;' : char}</span>`
      ).join('');
      return i < lines.length - 1 ? chars + '<br/>' : chars;
    }).join('');

    const charElements = Array.from(el.querySelectorAll<HTMLElement>('.typing-char'));
    if (charElements.length === 0) return;

    const rect = el.getBoundingClientRect();
    const alreadyInView = rect.top < window.innerHeight && rect.bottom > 0;

    let tween: gsap.core.Tween;

    if (alreadyInView) {
      tween = gsap.fromTo(
        charElements,
        { opacity: 0 },
        { opacity: 1, duration, stagger, delay, ease: 'none' }
      );
    } else {
      tween = gsap.fromTo(
        charElements,
        { opacity: 0 },
        {
          opacity: 1,
          duration,
          stagger,
          delay,
          ease: 'none',
          scrollTrigger: {
            trigger: el,
            start: 'top 95%',
            once,
          },
        }
      );
    }

    return () => {
      tween.kill();
      ScrollTrigger.getAll()
        .filter(st => st.trigger === el)
        .forEach(st => st.kill());
      el.innerText = text; // restore using cached original
    };
  }, []);
};