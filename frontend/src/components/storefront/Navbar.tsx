import React, { useState, useEffect, useRef } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { Menu, X, ShoppingBag } from 'lucide-react';
import { cn } from '@/lib/utils';
import { gsap } from 'gsap';
import { useBranding } from '@/hooks/useBranding';
import cartService from '@/services/api/cart';

const normalizeRole = (role?: string) => String(role || '').trim().toLowerCase();
const isPrivilegedRole = (role?: string) => {
  const normalized = normalizeRole(role);
  return normalized === 'admin' || normalized === 'staff';
};

const readCachedRole = (): string => {
  try {
    const raw = localStorage.getItem('auth_user');
    return raw ? JSON.parse(raw)?.role || '' : '';
  } catch {
    return '';
  }
};

type MenuItem = {
  label: string;
  path: string;
  action?: () => void;
};

export const Navbar: React.FC = () => {
  const location = useLocation();
  const [isScrolled, setIsScrolled] = useState(false);
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const [cartCount, setCartCount] = useState(0);
  const [isAuthenticated, setIsAuthenticated] = useState(Boolean(localStorage.getItem('auth_token')));
  const [userRole, setUserRole] = useState<string>(() => readCachedRole());
  const navRef = useRef<HTMLElement>(null);
  const pillRef = useRef<HTMLDivElement>(null);
  const hoverBgRef = useRef<HTMLDivElement>(null);
  const lastScrollY = useRef(0);
  const isHidden = useRef(false);
  const tween = useRef<gsap.core.Tween | null>(null);
  const branding = useBranding();

  const navItems = [
    { label: 'Home', path: '/' },
    { label: 'Our Products', path: '/products/' },
    { label: 'Contact', path: '/contact-us/' },
  ];
  const accountHome = isPrivilegedRole(userRole) ? '/admin/dashboard' : '/account';
  const accountLabel = isPrivilegedRole(userRole) ? 'Admin' : 'Account';
  const menuItems: MenuItem[] = [
    ...navItems,
    isAuthenticated
      ? { label: accountLabel, path: accountHome }
      : {
          label: 'Sign In',
          path: '#',
          action: () => {
            window.dispatchEvent(new CustomEvent('aurora:open-auth-modal', { detail: { mode: 'login' } }));
          },
        },
  ];

  const syncCartCount = async () => {
    try {
      const response = await cartService.getCart();
      const next = Number(response?.data?.item_count || 0);
      setCartCount(Math.max(0, next));
      return;
    } catch {
      // fallback to local storage below
    }
    try {
      const raw = localStorage.getItem('aurora_cart_items');
      if (!raw) {
        setCartCount(0);
        return;
      }
      const parsed = JSON.parse(raw) as Array<{ quantity?: number }>;
      if (!Array.isArray(parsed)) {
        setCartCount(0);
        return;
      }
      const total = parsed.reduce((sum, item) => sum + Math.max(0, Number(item.quantity || 0)), 0);
      setCartCount(total);
    } catch {
      setCartCount(0);
    }
  };

  const floatAway = () => {
    if (isHidden.current || !navRef.current) return;
    isHidden.current = true;
    tween.current?.kill();
    tween.current = gsap.to(navRef.current, {
      // Floats upward and fades — like antigravity
      y: '-120%',
      opacity: 0,
      duration: 0.6,
      ease: 'power2.inOut',
    });
  };

  const dropIn = () => {
    if (!isHidden.current || !navRef.current) return;
    isHidden.current = false;
    tween.current?.kill();
    tween.current = gsap.to(navRef.current, {
      // Drops back in with a slight overshoot bounce — gravity returning
      y: '0%',
      opacity: 1,
      duration: 0.55,
      ease: 'back.out(1.4)',
    });
  };

  useEffect(() => {
    lastScrollY.current = window.scrollY;

    const handleScroll = () => {
      const currentScrollY = window.scrollY;
      const delta = currentScrollY - lastScrollY.current;

      setIsScrolled(currentScrollY > 20);

      if (currentScrollY <= 60) {
        // Near the top — always show, reset fully
        if (isHidden.current) {
          isHidden.current = false;
          tween.current?.kill();
          gsap.to(navRef.current, { y: '0%', opacity: 1, duration: 0.4, ease: 'back.out(1.4)' });
        }
      } else if (delta > 8) {
        // Scrolling DOWN — float away (antigravity: drifts upward)
        floatAway();
      } else if (delta < -8) {
        // Scrolling UP — drop back in (gravity restored)
        dropIn();
      }

      lastScrollY.current = currentScrollY;
    };

    window.addEventListener('scroll', handleScroll, { passive: true });
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  useEffect(() => {
    setIsAuthenticated(Boolean(localStorage.getItem('auth_token')));
    setUserRole(readCachedRole());
  }, [location.pathname]);

  useEffect(() => {
    const syncAuthState = () => {
      setIsAuthenticated(Boolean(localStorage.getItem('auth_token')));
      setUserRole(readCachedRole());
    };
    const onStorage = (event: StorageEvent) => {
      if (!event.key || event.key === 'auth_token') {
        syncAuthState();
      }
      if (!event.key || event.key === 'aurora_cart_items') {
        void syncCartCount();
      }
    };
    const onAuthChanged = () => {
      syncAuthState();
    };
    const onCartUpdated = () => { void syncCartCount(); };
    void syncCartCount();
    window.addEventListener('aurora:auth-changed', onAuthChanged as EventListener);
    window.addEventListener('aurora:cart-updated', onCartUpdated as EventListener);
    window.addEventListener('focus', syncAuthState);
    window.addEventListener('storage', onStorage);
    return () => {
      window.removeEventListener('aurora:auth-changed', onAuthChanged as EventListener);
      window.removeEventListener('aurora:cart-updated', onCartUpdated as EventListener);
      window.removeEventListener('focus', syncAuthState);
      window.removeEventListener('storage', onStorage);
    };
  }, []);

  const moveHoverBg = (offsetLeft: number, offsetWidth: number) => {
    if (!hoverBgRef.current || !pillRef.current) return;
    gsap.to(hoverBgRef.current, {
      x: offsetLeft,
      width: offsetWidth,
      duration: 0.3,
      ease: 'power2.out',
      opacity: 1,
    });
  };

  const handleMouseEnter = (e: React.MouseEvent<HTMLAnchorElement>) => {
    const { offsetLeft, offsetWidth } = e.currentTarget;
    moveHoverBg(offsetLeft, offsetWidth);
  };

  const handleMouseLeavePill = () => {
    if (!hoverBgRef.current) return;
    gsap.to(hoverBgRef.current, { opacity: 0, duration: 0.3, ease: 'power2.inOut' });
  };

  return (
    <nav
      ref={navRef}
      className={cn(
        'storefront-navbar fixed top-0 left-0 right-0 z-[100] py-6 transition-colors duration-500',
        isScrolled
          ? 'bg-background/70 backdrop-blur-xl border-b border-slate-200/50 py-4 shadow-none'
          : 'bg-transparent'
      )}
    // No CSS transition on transform — GSAP owns it fully
    >
      <div className="max-w-7xl mx-auto px-6 flex items-center justify-between">

        {/* Logo */}
        <Link to="/" className="flex items-center gap-4 transition-transform hover:scale-105">
          {branding.logoUrl ? (
            <img
              src={branding.logoUrl}
              alt={branding.brandName}
              className="h-16 md:h-20 w-auto object-contain transition-all duration-300 transform origin-left contrast-125 drop-shadow-[0_0_0.7px_rgba(0,0,0,0.4)]"
            />
          ) : (
            <span className="text-slate-900 font-bold text-2xl tracking-tight uppercase">
              {branding.brandName}
            </span>
          )}
        </Link>

        {/* Desktop Nav Pill */}
        <div
          ref={pillRef}
          onMouseLeave={handleMouseLeavePill}
          className={cn(
            "hidden md:flex items-center relative bg-slate-900/5 border border-slate-200 rounded-full px-2 py-1.5 backdrop-blur-xl transition-shadow duration-300",
            isScrolled ? "shadow-none" : "shadow-lg"
          )}
        >
          <div
            ref={hoverBgRef}
            className="absolute top-1.5 bottom-1.5 left-0 bg-[#517b4b] rounded-full pointer-events-none opacity-0"
          />
          {menuItems.map((item) => (
            item.action ? (
                <button
                  key={item.label}
                  type="button"
                  onMouseEnter={(e) => {
                    const target = e.currentTarget;
                    moveHoverBg(target.offsetLeft, target.offsetWidth);
                  }}
                  onClick={item.action}
                  className="relative px-6 py-2 text-sm font-medium text-slate-600 hover:text-white transition-all duration-300 hover:-translate-y-0.5"
                >
                {item.label}
              </button>
            ) : (
              <Link
                key={item.label}
                to={item.path}
                onMouseEnter={handleMouseEnter}
                className="relative px-6 py-2 text-sm font-medium text-slate-600 hover:text-white transition-all duration-300 hover:-translate-y-0.5"
              >
                {item.label}
              </Link>
            )
          ))}
        </div>

        {/* Actions & Mobile Toggle */}
        <div className="flex items-center gap-4 md:gap-6">
          <Link to="/cart" className="hidden md:inline-flex relative text-slate-600 hover:text-primary transition-colors">
            <ShoppingBag size={20} />
            <span className="absolute -top-2 -right-2 bg-primary text-primary-foreground text-[10px] font-bold h-4 min-w-4 px-1 rounded-full flex items-center justify-center">
              {cartCount > 99 ? '99+' : cartCount}
            </span>
          </Link>
          <button
            className="md:hidden text-slate-700 hover:text-primary transition-colors"
            onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
          >
            {isMobileMenuOpen ? <X size={24} /> : <Menu size={24} />}
          </button>
        </div>
      </div>

      {/* Mobile Menu */}
      {isMobileMenuOpen && (
        <div className="md:hidden absolute top-full left-0 right-0 bg-white/95 backdrop-blur-2xl border-b border-slate-200 shadow-2xl animate-in slide-in-from-top duration-300">
          <div className="flex flex-col p-6 gap-4">
            {menuItems.map((item) => (
              item.action ? (
                <button
                  key={item.label}
                  type="button"
                  onClick={() => {
                    item.action?.();
                    setIsMobileMenuOpen(false);
                  }}
                  className="text-left text-lg font-medium text-slate-700 hover:text-primary transition-colors"
                >
                  {item.label}
                </button>
              ) : (
                <Link
                  key={item.label}
                  to={item.path}
                  onClick={() => setIsMobileMenuOpen(false)}
                  className="text-lg font-medium text-slate-700 hover:text-primary transition-colors"
                >
                  {item.label}
                </Link>
              )
            ))}
            <hr className="border-slate-100" />
            <Link to="/cart" onClick={() => setIsMobileMenuOpen(false)} className="text-lg font-medium text-slate-700 hover:text-primary transition-colors">Cart</Link>
          </div>
        </div>
      )}
    </nav>
  );
};
