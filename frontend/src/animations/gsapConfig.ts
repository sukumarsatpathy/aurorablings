import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';

gsap.registerPlugin(ScrollTrigger); // Register once at module level — safest place
gsap.config({ nullTargetWarn: false });

/**
 * ScrollTrigger measures trigger positions once, at creation. On the homepage
 * the sections below the fold are lazy-loaded and grow after that, so the
 * stored positions went stale and reveals fired late or never — sections sat
 * invisible ("blank areas while scrolling"). Re-measure whenever the page
 * height changes noticeably, debounced so it costs one refresh per settle.
 */
let layoutWatcherStarted = false;
const watchLayoutForScrollTriggers = () => {
  if (layoutWatcherStarted || typeof window === 'undefined' || typeof ResizeObserver === 'undefined') return;
  layoutWatcherStarted = true;
  let lastHeight = document.body.scrollHeight;
  let timer: number | undefined;
  new ResizeObserver(() => {
    const height = document.body.scrollHeight;
    if (Math.abs(height - lastHeight) < 40) return;
    lastHeight = height;
    window.clearTimeout(timer);
    timer = window.setTimeout(() => ScrollTrigger.refresh(), 200);
  }).observe(document.body);
};

export const initGsap = () => {
  watchLayoutForScrollTriggers();
};

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