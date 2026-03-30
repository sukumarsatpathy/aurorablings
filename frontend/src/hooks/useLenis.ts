import { useEffect } from 'react';
import Lenis from 'lenis';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import { initGsap } from '@/animations/gsapConfig';

export function useLenis() {
  useEffect(() => {
    initGsap();

    const lenis = new Lenis({
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

    let rafId = 0;

    lenis.on('scroll', ({ velocity }) => {
      ScrollTrigger.update();
      // Small, clamped value for subtle velocity-reactive UI details.
      const clamped = Math.max(-3, Math.min(3, velocity));
      document.documentElement.style.setProperty('--scroll-velocity', clamped.toFixed(3));
    });

    function raf(time: number) {
      lenis.raf(time);
      rafId = requestAnimationFrame(raf);
    }

    rafId = requestAnimationFrame(raf);

    return () => {
      cancelAnimationFrame(rafId);
      document.documentElement.style.removeProperty('--scroll-velocity');
      lenis.destroy();
    };
  }, []);
}
