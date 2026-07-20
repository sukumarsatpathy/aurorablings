import React from 'react';
import { useRef, useEffect, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { Navbar } from '@/components/storefront/Navbar';
import { Footer } from '@/components/storefront/Footer';
import { PremiumCursor } from '@/components/storefront/PremiumCursor';
import { BackgroundDecoration } from '@/components/storefront/BackgroundDecoration';
import { SignInModal } from '@/components/storefront/SignInModal';
import { gsap, shouldAnimate } from '@/animations/gsapConfig';
import { useLenis } from '@/hooks/useLenis';

interface LayoutProps {
  children: React.ReactNode;
}

export const MainLayout: React.FC<LayoutProps> = ({ children }) => {
  // Smooth scroll belongs to the storefront only. This used to be called in
  // AppContent at the app root, so its requestAnimationFrame loop — which calls
  // ScrollTrigger.update() and writes a CSS variable on <html> every frame —
  // also ran for the whole time an admin was using the dashboard, where smooth
  // scrolling is neither wanted nor used.
  useLenis();

  const mainRef = useRef<HTMLElement>(null);
  const location = useLocation();
  const navigate = useNavigate();
  const [isSignInOpen, setIsSignInOpen] = useState(false);
  const [nextPath, setNextPath] = useState('');
  const [authMode, setAuthMode] = useState<'login' | 'register' | 'forgot'>('login');

  useEffect(() => {
    if (!mainRef.current || !shouldAnimate()) {
      return;
    }

    // The pre-hydration shell (see index.html) already painted the homepage
    // hero before React loaded. Fading <main> in from autoAlpha:0 here would
    // hide content the visitor is ALREADY looking at and replay it — a
    // visible flash that also delays the "settled" paint. Skip the entrance
    // tween once, for that first hydration; route changes animate as before.
    if ((window as unknown as { __SHELL_PAINTED__?: boolean }).__SHELL_PAINTED__) {
      delete (window as unknown as { __SHELL_PAINTED__?: boolean }).__SHELL_PAINTED__;
      return;
    }

    gsap.fromTo(
      mainRef.current,
      { autoAlpha: 0, y: 10 },
      { autoAlpha: 1, y: 0, duration: 0.45, ease: 'power2.out' }
    );
  }, [location.pathname]);

  useEffect(() => {
    const onOpenAuth = (event: Event) => {
      const custom = event as CustomEvent<{ next?: string; mode?: 'login' | 'register' | 'forgot' }>;
      const next = String(custom.detail?.next || '').trim();
      const mode = custom.detail?.mode || 'login';
      setNextPath(next);
      setAuthMode(mode);
      setIsSignInOpen(true);
    };

    window.addEventListener('aurora:open-auth-modal', onOpenAuth as EventListener);
    return () => {
      window.removeEventListener('aurora:open-auth-modal', onOpenAuth as EventListener);
    };
  }, []);

  useEffect(() => {
    const state = (location.state || {}) as {
      openAuthModal?: boolean;
      openLoginModal?: boolean;
      next?: string;
      mode?: 'login' | 'register' | 'forgot';
    };
    if (!state.openAuthModal && !state.openLoginModal) return;

    const next = String(state.next || '').trim();
    const mode = state.mode || 'login';
    setNextPath(next);
    setAuthMode(mode);
    setIsSignInOpen(true);
    navigate(location.pathname + location.search, { replace: true, state: null });
  }, [location.pathname, location.search, location.state, navigate]);

  return (
    <div className="min-h-screen flex flex-col bg-background premium-bg selection:bg-primary/20 selection:text-primary overflow-x-hidden relative">
      <BackgroundDecoration />
      <PremiumCursor />
      <Navbar />
      <main ref={mainRef} className="flex-1 pt-20 relative z-10">
        {children}
      </main>
      <SignInModal
        open={isSignInOpen}
        onOpenChange={setIsSignInOpen}
        nextPath={nextPath}
        initialMode={authMode}
      />
      <Footer />
    </div>
  );
};
