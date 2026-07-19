import { useEffect, useState, lazy, Suspense } from 'react';
import type { ReactNode } from 'react';
import { Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { AppProviders } from './app/providers';
import { MainLayout } from './components/layouts/MainLayout';

/**
 * Route-level code splitting.
 *
 * Everything below that is `lazy()` used to be a static import, which meant
 * Rollup put all of it -- ~10k lines of admin pages plus recharts, lexical,
 * @dnd-kit and the full @radix-ui set -- in the entry chunk that every
 * anonymous shopper downloads before the homepage can render.
 *
 * Kept eager (critical path for a first visit):
 *   MainLayout, HomePage, and the small static content pages.
 *
 * Note on the `.then()` wrapper: React.lazy requires a module whose `default`
 * is the component. Pages using named exports need the wrapper; pages that
 * already `export default` must NOT have it, or the route renders as
 * `undefined` and React throws "Element type is invalid" at runtime --
 * which TypeScript does not catch. Verified per-file:
 *   default exports -> TrackingSettings, GTMSettings, AdminBannersPage
 *   named exports   -> everything else
 *   (Settings.tsx is a barrel: `export { SettingsPage as Settings }`)
 */

// ── Storefront (eager: cheap, and on the first-paint path) ───────────────────
import { HomePage } from './pages/storefront/HomePage';
import { AboutUsPage } from './pages/storefront/AboutUsPage';
import { ContactUsPage } from './pages/storefront/ContactUsPage';
import { TermsAndConditionsPage } from './pages/storefront/TermsAndConditionsPage';
import { ReturnRefundPolicyPage } from './pages/storefront/ReturnRefundPolicyPage';
import { ShippingPolicyPage } from './pages/storefront/ShippingPolicyPage';
import { PrivacyPolicyPage } from './pages/storefront/PrivacyPolicyPage';
import { OrderThankYouPage } from './pages/storefront/OrderThankYouPage';
import { ResetPasswordPage } from './pages/storefront/ResetPasswordPage';

// ── Storefront (lazy: large, and not needed to render the landing page) ──────
const ProductListingPage = lazy(() => import('./pages/storefront/ProductListingPage').then(m => ({ default: m.ProductListingPage })));
const ProductDetailPage = lazy(() => import('./pages/storefront/ProductDetailPage').then(m => ({ default: m.ProductDetailPage })));
const CartPage = lazy(() => import('./pages/storefront/CartPage').then(m => ({ default: m.CartPage })));
const CheckoutPage = lazy(() => import('./pages/storefront/CheckoutPage').then(m => ({ default: m.CheckoutPage })));

// ── Account area (lazy: behind auth) ────────────────────────────────────────
const AccountLayout = lazy(() => import('./components/account/AccountLayout').then(m => ({ default: m.AccountLayout })));
const AccountDashboardPage = lazy(() => import('./pages/account/AccountDashboardPage').then(m => ({ default: m.AccountDashboardPage })));
const AccountOrdersPage = lazy(() => import('./pages/account/AccountOrdersPage').then(m => ({ default: m.AccountOrdersPage })));
const AccountAddressPage = lazy(() => import('./pages/account/AccountAddressPage').then(m => ({ default: m.AccountAddressPage })));
const AccountProfilePage = lazy(() => import('./pages/account/AccountProfilePage').then(m => ({ default: m.AccountProfilePage })));
const AccountLogoutPage = lazy(() => import('./pages/account/AccountLogoutPage').then(m => ({ default: m.AccountLogoutPage })));

// ── Admin (all lazy: ~10k lines, unreachable without a staff token) ─────────
const DashboardLayout = lazy(() => import('./components/layouts/DashboardLayout').then(m => ({ default: m.DashboardLayout })));
const Dashboard = lazy(() => import('./pages/admin/Dashboard').then(m => ({ default: m.Dashboard })));
const ProductManagement = lazy(() => import('./pages/admin/ProductManagement').then(m => ({ default: m.ProductManagement })));
const Orders = lazy(() => import('./pages/admin/Orders').then(m => ({ default: m.Orders })));
const Shipments = lazy(() => import('./pages/admin/Shipments').then(m => ({ default: m.Shipments })));
const Attributes = lazy(() => import('./pages/admin/Attributes').then(m => ({ default: m.Attributes })));
const Inventory = lazy(() => import('./pages/admin/Inventory').then(m => ({ default: m.Inventory })));
const Returns = lazy(() => import('./pages/admin/Returns').then(m => ({ default: m.Returns })));
const Customers = lazy(() => import('./pages/admin/Customers').then(m => ({ default: m.Customers })));
const Features = lazy(() => import('./pages/admin/Features').then(m => ({ default: m.Features })));
const Reviews = lazy(() => import('./pages/admin/Reviews').then(m => ({ default: m.Reviews })));
const Settings = lazy(() => import('./pages/admin/Settings').then(m => ({ default: m.Settings })));
const Coupons = lazy(() => import('./pages/admin/Coupons').then(m => ({ default: m.Coupons })));
const AuditLogs = lazy(() => import('./pages/admin/AuditLogs').then(m => ({ default: m.AuditLogs })));
const HealthDashboard = lazy(() => import('./pages/admin/HealthDashboard').then(m => ({ default: m.HealthDashboard })));
const CategoryManagement = lazy(() => import('./pages/admin/CategoryManagement').then(m => ({ default: m.CategoryManagement })));
const NotifyRequests = lazy(() => import('./pages/admin/NotifyRequests').then(m => ({ default: m.NotifyRequests })));
const Enquiries = lazy(() => import('./pages/admin/Enquiries').then(m => ({ default: m.Enquiries })));
const NotificationDashboard = lazy(() => import('./pages/admin/NotificationDashboard').then(m => ({ default: m.NotificationDashboard })));
const NotificationLogs = lazy(() => import('./pages/admin/NotificationLogs').then(m => ({ default: m.NotificationLogs })));
const NewsletterSubscribers = lazy(() => import('./pages/admin/NewsletterSubscribers').then(m => ({ default: m.NewsletterSubscribers })));

// Default exports — no `.then()` wrapper. See the note at the top of the file.
const TrackingSettings = lazy(() => import('./pages/admin/TrackingSettings'));
const GTMSettings = lazy(() => import('./pages/admin/GTMSettings'));
const AdminBannersPage = lazy(() => import('./pages/admin/AdminBannersPage/AdminBannersPage'));

import apiClient from './services/api/client';
import { SessionTimeoutManager } from './components/auth/SessionTimeoutManager';
import { useBranding } from './hooks/useBranding';
import { CookieConsentRoot } from './privacy/CookieConsentRoot';
import { applySeo } from './lib/seo';
import ClarityTracker from './components/tracking/ClarityTracker';
import { useTrackingSettings } from './hooks/useTrackingSettings';

/**
 * Shared Suspense fallback for lazily-loaded routes.
 *
 * Deliberately a neutral skeleton rather than a spinner: on a fast connection
 * the chunk resolves in a few frames, and a spinner that flashes for 80ms
 * reads as jank. `min-h-[60vh]` keeps the footer from jumping up and back
 * down while the chunk loads, which would otherwise show up as layout shift.
 */
function RouteFallback() {
  return (
    <div className="min-h-[60vh] w-full px-4 py-16" role="status" aria-busy="true">
      <span className="sr-only">Loading…</span>
      <div className="mx-auto max-w-5xl space-y-4">
        <div className="h-8 w-1/3 animate-pulse rounded-lg bg-muted/40" />
        <div className="h-64 w-full animate-pulse rounded-2xl bg-muted/30" />
      </div>
    </div>
  );
}

const normalizeRole = (role?: string) => String(role || '').trim().toLowerCase();
const isPrivilegedRole = (role?: string) => {
  const normalized = normalizeRole(role);
  return normalized === 'admin' || normalized === 'staff';
};

const defaultRouteByRole = (role?: string) => {
  const normalized = normalizeRole(role);
  if (normalized === 'admin' || normalized === 'staff') return '/admin/dashboard';
  return '/account';
};

const readCachedRole = (): string => {
  try {
    const raw = localStorage.getItem('auth_user');
    return raw ? JSON.parse(raw)?.role || '' : '';
  } catch {
    return '';
  }
};

const hasGtmAdminAccess = (user: any): boolean => {
  const role = normalizeRole(user?.role);
  return (
    user?.is_staff === true ||
    user?.is_superuser === true ||
    role === 'admin' ||
    role === 'staff' ||
    role === 'super_admin' ||
    role === 'superadmin'
  );
};

const readCachedStaffFlag = (): boolean => {
  try {
    const raw = localStorage.getItem('auth_user');
    const parsed = raw ? JSON.parse(raw) : null;
    return hasGtmAdminAccess(parsed);
  } catch {
    return false;
  }
};

function LoginPage() {
  const location = useLocation();
  const requestedNext = new URLSearchParams(location.search).get('next') || '';
  if (localStorage.getItem('auth_token')) {
    let cachedRole = '';
    try {
      const raw = localStorage.getItem('auth_user');
      if (raw) cachedRole = JSON.parse(raw)?.role || '';
    } catch {
      cachedRole = '';
    }
    return <Navigate to={requestedNext || defaultRouteByRole(cachedRole)} replace />;
  }

  return (
    <Navigate
      to="/"
      replace
      state={{ openLoginModal: true, next: requestedNext || '' }}
    />
  );
}

function RegisterPage() {
  const location = useLocation();
  const requestedNext = new URLSearchParams(location.search).get('next') || '';
  if (localStorage.getItem('auth_token')) {
    let cachedRole = '';
    try {
      const raw = localStorage.getItem('auth_user');
      if (raw) cachedRole = JSON.parse(raw)?.role || '';
    } catch {
      cachedRole = '';
    }
    return <Navigate to={requestedNext || defaultRouteByRole(cachedRole)} replace />;
  }

  return (
    <Navigate
      to="/"
      replace
      state={{ openAuthModal: true, mode: 'register', next: requestedNext || '' }}
    />
  );
}

function ForgotPasswordEntry() {
  if (localStorage.getItem('auth_token')) {
    return <Navigate to="/account" replace />;
  }
  return <Navigate to="/" replace state={{ openAuthModal: true, mode: 'forgot' }} />;
}

function RequireAuth({ children }: { children: ReactNode }) {
  const location = useLocation();
  const token = localStorage.getItem('auth_token');

  if (!token) {
    const next = `${location.pathname}${location.search}`;
    return <Navigate to={`/login?next=${encodeURIComponent(next)}`} replace />;
  }

  return <>{children}</>;
}

function RequireAdminOrStaff({ children }: { children: ReactNode }) {
  const location = useLocation();
  const token = localStorage.getItem('auth_token');
  const cachedRole = readCachedRole();
  const [resolvedRole, setResolvedRole] = useState<string>(() => cachedRole);
  const [checkingRole, setCheckingRole] = useState<boolean>(() => !cachedRole);

  useEffect(() => {
    let mounted = true;
    const hydrateRole = async () => {
      if (!token) {
        setCheckingRole(false);
        return;
      }
      if (resolvedRole) {
        setCheckingRole(false);
        return;
      }
      try {
        const response = await apiClient.get('/v1/auth/profile/');
        const user = response?.data?.data || null;
        const role = String(user?.role || '');
        if (user) localStorage.setItem('auth_user', JSON.stringify(user));
        if (mounted) setResolvedRole(role);
      } catch {
        if (mounted) setResolvedRole('');
      } finally {
        if (mounted) setCheckingRole(false);
      }
    };
    void hydrateRole();
    return () => {
      mounted = false;
    };
  }, [resolvedRole, token]);

  if (!token) {
    const next = `${location.pathname}${location.search}`;
    return <Navigate to={`/login?next=${encodeURIComponent(next)}`} replace />;
  }

  if (checkingRole) {
    return null;
  }

  if (!isPrivilegedRole(resolvedRole)) {
    return <Navigate to="/account" replace />;
  }

  return <>{children}</>;
}

function UnauthorizedPage() {
  return (
    <MainLayout>
      <div className="mx-auto max-w-3xl px-4 py-16">
        <div className="rounded-2xl border border-destructive/30 bg-destructive/10 p-8 shadow-soft">
          <h1 className="text-2xl font-semibold text-destructive">Unauthorized</h1>
          <p className="mt-2 text-sm text-destructive/90">
            You do not have permission to access this page.
          </p>
        </div>
      </div>
    </MainLayout>
  );
}

function RequireStaffOnly({ children }: { children: ReactNode }) {
  const location = useLocation();
  const token = localStorage.getItem('auth_token');
  const [isStaff, setIsStaff] = useState<boolean>(() => readCachedStaffFlag());
  const [checking, setChecking] = useState<boolean>(() => !readCachedStaffFlag());

  useEffect(() => {
    let mounted = true;
    const resolveStaff = async () => {
      if (!token) {
        setChecking(false);
        return;
      }
      if (isStaff) {
        setChecking(false);
        return;
      }
      try {
        const response = await apiClient.get('/v1/auth/profile/');
        const user = response?.data?.data || null;
        if (user) localStorage.setItem('auth_user', JSON.stringify(user));
        if (mounted) setIsStaff(hasGtmAdminAccess(user));
      } catch {
        if (mounted) setIsStaff(false);
      } finally {
        if (mounted) setChecking(false);
      }
    };
    void resolveStaff();
    return () => {
      mounted = false;
    };
  }, [isStaff, token]);

  if (!token) {
    const next = `${location.pathname}${location.search}`;
    return <Navigate to={`/login?next=${encodeURIComponent(next)}`} replace />;
  }

  if (checking) return null;

  if (!isStaff) {
    return <Navigate to="/unauthorized" replace />;
  }

  return <>{children}</>;
}

function DashboardHomeRedirect() {
  const token = localStorage.getItem('auth_token');
  if (!token) {
    return <Navigate to="/login?next=/dashboard" replace />;
  }

  const role = readCachedRole();
  return <Navigate to={defaultRouteByRole(role)} replace />;
}

function AppContent() {
  // useLenis() moved to MainLayout — smooth scroll is storefront-only and was
  // previously running its rAF loop on admin routes too.
  const branding = useBranding();
  const location = useLocation();
  const trackingSettings = useTrackingSettings();

  useEffect(() => {
    const genericDescription = branding.tagline
      ? `${branding.brandName} | ${branding.tagline}`
      : `${branding.brandName} brings stylish, premium accessories and standout picks for every occasion.`;

    applySeo({
      title: branding.tabTitle,
      description: genericDescription,
      image: branding.logoUrl || branding.faviconUrl,
      imageAlt: branding.brandName,
      url: `${window.location.origin}${location.pathname}${location.search}`,
      siteName: branding.brandName,
    });
  }, [
    branding.brandName,
    branding.faviconUrl,
    branding.logoUrl,
    branding.tabTitle,
    branding.tagline,
    location.pathname,
    location.search,
  ]);

  useEffect(() => {
    if (!branding.faviconUrl) return;

    const cacheBusted = `${branding.faviconUrl}${branding.faviconUrl.includes('?') ? '&' : '?'}v=${Date.now()}`;
    const rels = ['icon', 'shortcut icon', 'apple-touch-icon'];
    const lower = branding.faviconUrl.toLowerCase();
    const iconType = lower.endsWith('.png')
      ? 'image/png'
      : lower.endsWith('.ico')
        ? 'image/x-icon'
        : lower.endsWith('.webp')
          ? 'image/webp'
          : lower.endsWith('.jpg') || lower.endsWith('.jpeg')
            ? 'image/jpeg'
            : 'image/svg+xml';

    rels.forEach((rel) => {
      const existing = document.querySelector(`link[rel='${rel}']`) as HTMLLinkElement | null;
      if (existing) {
        existing.href = cacheBusted;
        existing.type = iconType;
      } else {
        const link = document.createElement('link');
        link.rel = rel;
        link.href = cacheBusted;
        link.type = iconType;
        document.head.appendChild(link);
      }
    });
  }, [branding.faviconUrl]);

  return (
    <>
      <ClarityTracker
        trackingId={trackingSettings.clarity_tracking_id}
        enabled={trackingSettings.clarity_enabled}
      />
      <SessionTimeoutManager preferredTitle={branding.tabTitle} />
      <CookieConsentRoot />
      <Suspense fallback={<RouteFallback />}>
      <Routes>
        {/* Storefront Routes */}
        <Route path="/" element={<MainLayout><HomePage /></MainLayout>} />
        <Route path="/products" element={<Navigate to="/products/" replace />} />
        <Route path="/products/" element={<MainLayout><ProductListingPage /></MainLayout>} />
        <Route path="/about-us" element={<Navigate to="/about-us/" replace />} />
        <Route path="/about-us/" element={<MainLayout><AboutUsPage /></MainLayout>} />
        <Route path="/shop" element={<Navigate to="/products/" replace />} />
        <Route path="/contact" element={<Navigate to="/contact-us/" replace />} />
        <Route path="/contact-us" element={<Navigate to="/contact-us/" replace />} />
        <Route path="/contact-us/" element={<MainLayout><ContactUsPage /></MainLayout>} />
        <Route path="/terms" element={<Navigate to="/terms-and-conditions/" replace />} />
        <Route path="/terms-and-conditions" element={<Navigate to="/terms-and-conditions/" replace />} />
        <Route path="/terms-and-conditions/" element={<MainLayout><TermsAndConditionsPage /></MainLayout>} />
        <Route path="/refund-policy" element={<Navigate to="/return-and-refund-policy/" replace />} />
        <Route path="/refund-policy/" element={<Navigate to="/return-and-refund-policy/" replace />} />
        <Route path="/return-and-refund-policy" element={<Navigate to="/return-and-refund-policy/" replace />} />
        <Route path="/return-and-refund-policy/" element={<MainLayout><ReturnRefundPolicyPage /></MainLayout>} />
        <Route path="/privacy" element={<Navigate to="/privacy-policy/" replace />} />
        <Route path="/privacy/" element={<Navigate to="/privacy-policy/" replace />} />
        <Route path="/privacy-policy" element={<Navigate to="/privacy-policy/" replace />} />
        <Route path="/privacy-policy/" element={<MainLayout><PrivacyPolicyPage /></MainLayout>} />
        <Route path="/shipping-policy" element={<Navigate to="/shipping-policy/" replace />} />
        <Route path="/shipping-policy/" element={<MainLayout><ShippingPolicyPage /></MainLayout>} />
        <Route path="/product/:id" element={<MainLayout><ProductDetailPage /></MainLayout>} />
        <Route path="/cart" element={<MainLayout><CartPage /></MainLayout>} />
        <Route path="/checkout" element={<MainLayout><CheckoutPage /></MainLayout>} />
        <Route path="/order/thank-you" element={<MainLayout><OrderThankYouPage /></MainLayout>} />
        <Route path="/account" element={
          <MainLayout>
            <RequireAuth>
              <AccountLayout />
            </RequireAuth>
          </MainLayout>
        }>
          <Route index element={<AccountDashboardPage />} />
          <Route path="orders" element={<AccountOrdersPage />} />
          <Route path="address" element={<AccountAddressPage />} />
          <Route path="profile" element={<AccountProfilePage />} />
          <Route path="logout" element={<AccountLogoutPage />} />
        </Route>
        <Route path="/dashboard" element={<DashboardHomeRedirect />} />
        
        {/* Auth Routes */}
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route path="/forgot-password" element={<ForgotPasswordEntry />} />
        <Route path="/reset-password" element={<ResetPasswordPage />} />
        <Route path="/auth/reset-password" element={<ResetPasswordPage />} />
        <Route path="/unauthorized" element={<UnauthorizedPage />} />
        
        {/* Admin/Dashboard Routes */}
        <Route path="/admin" element={<Navigate to="/admin/dashboard" replace />} />
        <Route path="/admin/*" element={
          <RequireAdminOrStaff>
            <DashboardLayout>
              {/* Inner boundary so the dashboard chrome (sidebar, header) stays
                  on screen while an individual admin page chunk loads, instead
                  of the whole shell being replaced by the outer fallback. */}
              <Suspense fallback={<RouteFallback />}>
              <Routes>
                <Route path="dashboard" element={<Dashboard />} />
                <Route path="products" element={<ProductManagement />} />
                <Route path="categories" element={<CategoryManagement />} />
                <Route path="attributes" element={<Attributes />} />
                <Route path="orders" element={<Orders />} />
                <Route path="shipments" element={<Shipments />} />
                <Route path="inventory" element={<Inventory />} />
                <Route path="returns" element={<Returns />} />
                <Route path="customers" element={<Customers />} />
                <Route path="features" element={<Features />} />
                <Route path="reviews" element={<Reviews />} />
                <Route path="notifications" element={<NotificationDashboard />} />
                <Route path="notifications/logs" element={<NotificationLogs />} />
                <Route path="newsletter" element={<NewsletterSubscribers />} />
                <Route path="notify-requests" element={<NotifyRequests />} />
                <Route path="enquiries" element={<Enquiries />} />
                <Route path="coupons" element={<Coupons />} />
                <Route path="audit-logs" element={<AuditLogs />} />
                <Route path="settings" element={<Settings />} />
                <Route
                  path="gtm-settings"
                  element={
                    <RequireStaffOnly>
                      <GTMSettings />
                    </RequireStaffOnly>
                  }
                />
                <Route path="tracking-settings" element={<TrackingSettings />} />
                <Route path="banners" element={<AdminBannersPage />} />
                <Route path="health" element={<HealthDashboard />} />
              </Routes>
              </Suspense>
            </DashboardLayout>
          </RequireAdminOrStaff>
        } />
      </Routes>
      </Suspense>
    </>
  );
}

function App() {
  return (
    <AppProviders>
      <AppContent />
    </AppProviders>
  );
}

export default App;
