import { useEffect } from 'react';
import { useLocation, useNavigationType } from 'react-router-dom';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import { getLenis } from './useLenis';

/**
 * Reset the scroll position to the top on client-side navigation.
 *
 * ── The bug this fixes ───────────────────────────────────────────────────────
 *
 * The app had no scroll handling on route change at all -- no <ScrollRestoration>,
 * no ScrollToTop component, no window.scrollTo anywhere. React Router's <Routes>
 * (as opposed to the data router) does not reset scroll for you, and a pushState
 * navigation does not reset it either: only a full document load does.
 *
 * So the window scroll offset simply carried over from the previous page. Scroll
 * a third of the way down the homepage, click a product card, and the product
 * page mounts with the window still at ~3900px. If that offset is past the new
 * page's height it clamps to the bottom -- which is the footer. Reproduced
 * before the fix:
 *
 *     /privacy-policy/ (h=4878) at y=3878  ->  /products/ (h=1694) at y=894
 *
 * 894 + 800 (viewport) = 1694 = exactly the bottom of the document. That is the
 * reported symptom precisely: a blank footer on arrival, with the product
 * description sitting above it once you scroll up. Refreshing "fixed" it only
 * because a real document load starts at 0.
 *
 * ── Why window.scrollTo alone is not enough ──────────────────────────────────
 *
 * Lenis drives window scroll from its own requestAnimationFrame loop. Setting
 * window.scrollY directly gets overwritten on the very next frame by whatever
 * Lenis still holds as its target, so the reset has to go through the instance
 * when one exists. Lenis initialises lazily (deferred to requestIdleCallback,
 * see useLenis), so it may legitimately be null on an early navigation -- hence
 * the fallback.
 *
 * ── Ordering ─────────────────────────────────────────────────────────────────
 *
 * This is a useEffect, deliberately, and it belongs in the layout rather than in
 * a page. React runs child effects before parent effects, so by the time this
 * fires the page's own useLayoutEffect work -- notably the ScrollTrigger setup
 * in useScrollReveal / useStagger, which measures the document -- has already
 * run. The extra requestAnimationFrame pass covers content that arrives a frame
 * later, which is the normal case for the lazy routes (product detail, product
 * listing, cart, checkout all sit behind React.lazy + Suspense).
 *
 * ScrollTrigger.refresh() afterwards makes the triggers recompute against the
 * corrected position; without it, reveal animations can believe they are already
 * past their start point and fire immediately or not at all.
 */
export function useScrollToTop() {
  const { pathname, hash } = useLocation();
  const navigationType = useNavigationType();

  useEffect(() => {
    // An in-page anchor (/page#reviews) is an explicit request for a position
    // that is not the top. Leave those alone.
    if (hash) return;

    // POP is the back/forward button. Browsers keep a scroll offset per history
    // entry and restore it themselves (history.scrollRestoration defaults to
    // 'auto'), and on a storefront that matters -- going back from a product to
    // the grid should return you to the product you were looking at, not to the
    // top of the page. So only PUSH and REPLACE reset.
    if (navigationType === 'POP') return;

    let rafId = 0;

    const toTop = () => {
      const lenis = getLenis();
      if (lenis) {
        // immediate: skip the easing, this is a navigation and not a scroll.
        // force: allow it even if Lenis is currently stopped (e.g. a modal has
        // locked scrolling).
        lenis.scrollTo(0, { immediate: true, force: true });
      }
      // Always set the window too: it covers the window before Lenis has
      // initialised, and keeps the two in sync when it has.
      window.scrollTo(0, 0);
    };

    toTop();
    rafId = requestAnimationFrame(() => {
      toTop();
      // Only refresh if triggers actually exist -- refresh() forces a full
      // layout read, and there is no reason to pay for it on a page with no
      // scroll animations.
      if (ScrollTrigger.getAll().length > 0) {
        ScrollTrigger.refresh();
      }
    });

    return () => cancelAnimationFrame(rafId);
  }, [pathname, hash, navigationType]);
}
