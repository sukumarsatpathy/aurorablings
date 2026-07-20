import { useEffect } from 'react';
import Lenis from 'lenis';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import { initGsap } from '@/animations/gsapConfig';

export function useLenis() {
  useEffect(() => {
    // Lenis's constructor and ScrollTrigger's first update both read layout
    // (scroll geometry, element rects) while the browser is still doing
    // startup style/layout work, which Lighthouse reports as forced reflow.
    // Smooth scrolling is not needed for the first paint, so init is deferred:
    // two rAFs guarantee we are past the first paint, then requestIdleCallback
    // waits for a quiet moment (with a timeout so scrolling never feels broken
    // on a busy page). Native scroll works fine in the gap.
    let lenis: Lenis | null = null;
    let rafId = 0;
    let idleId = 0;
    let deferRafId = 0;
    let cancelled = false;

    const start = () => {
      if (cancelled) return;
      initGsap();

      lenis = new Lenis({
        duration: 1.05,
        easing: (t) => Math.min(1, 1.001 - Math.pow(2, -10 * t)),
        orientation: 'vertical',
        gestureOrientation: 'vertical',
        smoothWheel: true,
        wheelMultiplier: 1,
        touchMultiplier: 1.2,
        infinite: false,
        prevent: (node) => {
          if (!node || !(node instanceof HTMLElement)) return false;
          return Boolean(node.closest('[data-lenis-prevent]'));
        },
      });

      // Writing a custom property on <html> invalidates style for every element
      // that inherits it — i.e. the whole document — so doing it on every scroll
      // frame was measurable. --scroll-velocity only drives subtle effects, so a
      // small dead zone is imperceptible and skips the majority of writes.
      let lastVelocity = 0;

      lenis.on('scroll', ({ velocity }) => {
        ScrollTrigger.update();
        // Small, clamped value for subtle velocity-reactive UI details.
        const clamped = Math.max(-3, Math.min(3, velocity));
        if (Math.abs(clamped - lastVelocity) > 0.05) {
          lastVelocity = clamped;
          document.documentElement.style.setProperty('--scroll-velocity', clamped.toFixed(2));
        }
      });

      function raf(time: number) {
        lenis?.raf(time);
        rafId = requestAnimationFrame(raf);
      }

      rafId = requestAnimationFrame(raf);
    };

    deferRafId = requestAnimationFrame(() => {
      deferRafId = requestAnimationFrame(() => {
        if (typeof window.requestIdleCallback === 'function') {
          idleId = window.requestIdleCallback(start, { timeout: 1500 });
        } else {
          idleId = window.setTimeout(start, 200) as unknown as number;
        }
      });
    });

    return () => {
      cancelled = true;
      cancelAnimationFrame(deferRafId);
      if (typeof window.cancelIdleCallback === 'function') {
        window.cancelIdleCallback(idleId);
      } else {
        window.clearTimeout(idleId);
      }
      cancelAnimationFrame(rafId);
      document.documentElement.style.removeProperty('--scroll-velocity');
      lenis?.destroy();
    };
  }, []);
}
