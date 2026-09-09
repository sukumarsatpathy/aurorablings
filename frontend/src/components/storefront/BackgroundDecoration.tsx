import React from 'react';

/**
 * Decorative background layer: three soft colour orbs plus a faint grid.
 *
 * These orbs used to be animated with two infinite GSAP tweens each (`repeat: -1`,
 * one moving, one scaling to up to 2.5x). That was the single largest cause of the
 * site feeling unresponsive.
 *
 * `.floating-orb` carries `blur-[120px]` (see index.css). A blurred layer cannot be
 * cheaply re-composited while it is being transformed -- the browser has to
 * re-rasterize the Gaussian blur every frame. Three of them, 500-700px each, scaled
 * up to 2.5x, running forever, on every route and every device, kept the compositor
 * permanently saturated. On mid-range phones that alone is enough to make scrolling
 * stutter and taps feel dropped, and it drains battery the whole time the tab is open.
 *
 * Static, the same orbs are rasterized once and cached, and cost essentially nothing.
 * The visual difference is negligible: the tweens drifted each orb by at most +/-100px
 * over 10-30s at 5-7% opacity, behind every other element on the page.
 *
 * If the motion is ever wanted back, gate it the way PremiumCursor does -- that
 * component guards itself with `prefersReducedMotion()` and `isDesktopPointer()` from
 * '@/animations/gsapConfig', and this one never did:
 *
 *   if (prefersReducedMotion() || !isDesktopPointer()) return;
 *
 * Even then, prefer animating `opacity` or a cheap `translate3d` over `scale` on a
 * blurred element, and drop the blur radius substantially.
 */
export const BackgroundDecoration: React.FC = () => {
  return (
    <div className="fixed inset-0 pointer-events-none z-[-1] overflow-hidden bg-white">
      <div className="floating-orb w-[600px] h-[600px] -top-20 -left-20 opacity-[0.07]" />
      <div className="floating-orb w-[500px] h-[500px] top-1/2 left-3/4 opacity-[0.05]" />
      <div className="floating-orb w-[700px] h-[700px] -bottom-40 left-1/4 opacity-[0.06]" />

      {/* Subtle Grid Pattern Overlay */}
      <div
        className="absolute inset-0 opacity-[0.03]"
        style={{
          backgroundImage: `linear-gradient(#517b4b 1px, transparent 1px), linear-gradient(90deg, #517b4b 1px, transparent 1px)`,
          backgroundSize: '40px 40px'
        }}
      />
    </div>
  );
};
