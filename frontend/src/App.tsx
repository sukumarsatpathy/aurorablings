import { useEffect, useState } from 'react';
import type { ReactNode } from 'react';
import { useLenis } from './hooks/useLenis';
import { Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { AppProviders } from './app/providers';
import { MainLayout } from './components/layouts/MainLayout';
import { DashboardLayout } from './components/layouts/DashboardLayout';
import { HomePage } from './pages/storefront/HomePage';
import { ProductListingPage } from './pages/storefront/ProductListingPage';
import { ProductDetailPage } from './pages/storefront/ProductDetailPage';
import { AboutUsPage } from './pages/storefront/AboutUsPage';
import { ContactUsPage } from './pages/storefront/ContactUsPage';
import { TermsAndConditionsPage } from './pages/storefront/TermsAndConditionsPage';
import { ReturnRefundPolicyPage } from './pages/storefront/ReturnRefundPolicyPage';
import { ShippingPolicyPage } from './pages/storefront/ShippingPolicyPage';
import { PrivacyPolicyPage } from './pages/storefront/PrivacyPolicyPage';
import { CartPage } from './pages/storefront/CartPage';
import { CheckoutPage } from './pages/storefront/CheckoutPage';
import { OrderThankYouPage } from './pages/storefront/OrderThankYouPage';
import { ResetPasswordPage } from './pages/storefront/ResetPasswordPage';
import { AccountLayout } from './components/account/AccountLayout';
import { AccountDashboardPage } from './pages/account/AccountDashboardPage';
import { AccountOrdersPage } from './pages/account/AccountOrdersPage';
import { AccountAddressPage } from './pages/account/AccountAddressPage';
import { AccountProfilePage } from './pages/account/AccountProfilePage';
import { AccountLogoutPage } from './pages/account/AccountLogoutPage';

// Admin Imports
import { Dashboard } from './pages/admin/Dashboard';
import { ProductManagement } from './pages/admin/ProductManagement';
import { Orders } from './pages/admin/Orders';
import { Shipments } from './pages/admin/Shipments';
import { Attributes } from './pages/admin/Attributes';
import { Inventory } from './pages/admin/Inventory';
import { Returns } from './pages/admin/Returns';
import { Customers } from './pages/admin/Customers';
import { Features } from './pages/admin/Features';
import { Reviews } from './pages/admin/Reviews';
import { Settings } from './pages/admin/Settings';
import { Coupons } from './pages/admin/Coupons';
import { AuditLogs } from './pages/admin/AuditLogs';
import { HealthDashboard } from './pages/admin/HealthDashboard';
import { CategoryManagement } from './pages/admin/CategoryManagement';
import { NotifyRequests } from './pages/admin/NotifyRequests';
import { Enquiries } from './pages/admin/Enquiries';
import { NotificationDashboard } from './pages/admin/NotificationDashboard';
import { NotificationLogs } from './pages/admin/NotificationLogs';
import { NewsletterSubscribers } from './pages/admin/NewsletterSubscribers';
import TrackingSettings from './pages/admin/TrackingSettings';
import GTMSettings from './pages/admin/GTMSettings';
import AdminBannersPage from './pages/admin/AdminBannersPage/AdminBannersPage';
import apiClient from './services/api/client';
import { SessionTimeoutManager } from './components/auth/SessionTimeoutManager';
import { useBranding } from './hooks/useBranding';
import { CookieConsentRoot } from './privacy/CookieConsentRoot';
import trackingLoader from './services/trackingLoader';
import trackingApi from './services/trackingApi';
import { applySeo } from './lib/seo';

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
  useLenis(); // Smooth scroll initialization
  const branding = useBranding();
  const location = useLocation();

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

  useEffect(() => {
    let mounted = true;
    const hydrateTracking = async () => {
      try {
        const config = await trackingApi.getPublicGTMConfig();
        if (!mounted) return;
        if (config?.is_gtm_enabled && config?.gtm_container_id) {
          trackingLoader.loadGTM(config.gtm_container_id);
        }
      } catch {
        // GTM is optional and should never block app startup.
      }
    };
    void hydrateTracking();
    return () => {
      mounted = false;
    };
  }, []);

  return (
    <>
      <SessionTimeoutManager preferredTitle={branding.tabTitle} />
      <CookieConsentRoot />
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
            </DashboardLayout>
          </RequireAdminOrStaff>
        } />
      </Routes>
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
