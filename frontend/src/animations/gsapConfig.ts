import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';

gsap.registerPlugin(ScrollTrigger); // Register once at module level — safest place
gsap.config({ nullTargetWarn: false });

export const initGsap = () => { }; // Keep export to avoid breaking imports

export const prefersReducedMotion = () => {
  if (typeof window === 'undefined') return true;
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
};

export const isDesktopPointer = () => {
  if (typeof window === 'undefined') return false;
  return window.matchMedia('(hover: hover) and (pointer: fine)').matches;
};

export const shouldAnimate = () => !prefersReducedMotion();

export { gsap, ScrollTrigger };