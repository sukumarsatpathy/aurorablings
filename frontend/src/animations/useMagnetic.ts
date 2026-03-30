import { useEffect } from 'react';
import type { RefObject } from 'react';
import { gsap, isDesktopPointer, prefersReducedMotion } from './gsapConfig';

interface MagneticOptions {
  strength?: number;
  maxOffset?: number;
}

export const useMagnetic = <T extends HTMLElement>(ref: RefObject<T | null>, options: MagneticOptions = {}) => {
  useEffect(() => {
    if (!ref.current || prefersReducedMotion() || !isDesktopPointer()) {
      return;
    }

    const target = ref.current;
    const strength = options.strength ?? 0.18;
    const maxOffset = options.maxOffset ?? 8;

    const onMove = (event: MouseEvent) => {
      const rect = target.getBoundingClientRect();
      const centerX = rect.left + rect.width / 2;
      const centerY = rect.top + rect.height / 2;
      const offsetX = Math.max(-maxOffset, Math.min(maxOffset, (event.clientX - centerX) * strength));
      const offsetY = Math.max(-maxOffset, Math.min(maxOffset, (event.clientY - centerY) * strength));

      gsap.to(target, { x: offsetX, y: offsetY, duration: 0.25, ease: 'power2.out' });
    };

    const onLeave = () => {
      gsap.to(target, { x: 0, y: 0, duration: 0.45, ease: 'elastic.out(1, 0.4)' });
    };

    target.addEventListener('mousemove', onMove);
    target.addEventListener('mouseleave', onLeave);

    return () => {
      target.removeEventListener('mousemove', onMove);
      target.removeEventListener('mouseleave', onLeave);
    };
  }, [ref, options.maxOffset, options.strength]);
};
