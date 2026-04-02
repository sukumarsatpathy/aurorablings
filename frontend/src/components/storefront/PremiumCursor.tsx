import React, { useEffect, useRef } from 'react';
import { gsap, isDesktopPointer, prefersReducedMotion } from '@/animations/gsapConfig';

export const PremiumCursor: React.FC = () => {
  const dotRef = useRef<HTMLDivElement>(null);
  const ringRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!dotRef.current || !ringRef.current || prefersReducedMotion() || !isDesktopPointer()) {
      return;
    }

    const dotX = gsap.quickTo(dotRef.current, 'x', { duration: 0.12, ease: 'power3.out' });
    const dotY = gsap.quickTo(dotRef.current, 'y', { duration: 0.12, ease: 'power3.out' });
    const ringX = gsap.quickTo(ringRef.current, 'x', { duration: 0.22, ease: 'power3.out' });
    const ringY = gsap.quickTo(ringRef.current, 'y', { duration: 0.22, ease: 'power3.out' });

    const interactiveSelector = 'a, button, [role="button"], input, textarea, select, [data-cursor="hover"]';

    const onMove = (e: MouseEvent) => {
      const x = e.clientX;
      const y = e.clientY;

      dotX(x);
      dotY(y);
      ringX(x);
      ringY(y);
    };

    const onOver = (e: MouseEvent) => {
      const target = e.target as HTMLElement | null;
      if (!target) {
        return;
      }

      const isInteractive = !!target.closest(interactiveSelector);
      gsap.to(ringRef.current, {
        scale: isInteractive ? 1.8 : 1,
        opacity: isInteractive ? 0.22 : 0.35,
        duration: 0.2,
      });
    };

    document.documentElement.classList.add('premium-cursor-enabled');
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseover', onOver);

    return () => {
      document.documentElement.classList.remove('premium-cursor-enabled');
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseover', onOver);
    };
  }, []);

  if (prefersReducedMotion() || !isDesktopPointer()) {
    return null;
  }

  return (
    <>
      <div
        ref={ringRef}
        className="pointer-events-none fixed left-0 top-0 z-[1200] h-8 w-8 -translate-x-1/2 -translate-y-1/2 rounded-full border border-primary/40 opacity-35"
      />
      <div
        ref={dotRef}
        className="pointer-events-none fixed left-0 top-0 z-[1201] h-1.5 w-1.5 -translate-x-1/2 -translate-y-1/2 rounded-full bg-primary/80"
      />
    </>
  );
};
