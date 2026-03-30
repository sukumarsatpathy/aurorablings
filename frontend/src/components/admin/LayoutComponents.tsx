import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { LayoutDashboard, ShoppingBag, Box, RotateCcw, Settings, Search, BellRing, Bell, Tags, Sparkles, UserCog, LogOut, ChevronDown, MapPin, KeyRound, Check, X, TicketPercent, ClipboardList, HeartPulse, MoonStar, SunMedium, Warehouse, Monitor, FolderTree, MessageSquare, Users } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Input } from '@/components/ui/Input';
import { Button } from '@/components/ui/Button';
import { Modal, ModalContent, ModalFooter, ModalHeader, ModalTitle } from '@/components/ui/Modal';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/DropdownMenu';
import profileService, { type AddressData, type ProfileData } from '@/services/api/profile';
import notifyService, { type ContactQueryItem } from '@/services/api/notify';
import { useBranding } from '@/hooks/useBranding';
import { useAddressAutoFill } from '@/hooks/useAddressAutoFill';

const NAV_ITEMS = [
  { path: '/admin/dashboard', icon: LayoutDashboard, label: 'Dashboard' },
  { path: '/admin/categories', icon: FolderTree, label: 'Categories' },
  { path: '/admin/attributes', icon: Tags, label: 'Attributes' },
  { path: '/admin/products', icon: Box, label: 'Products' },
  { path: '/admin/reviews', icon: MessageSquare, label: 'Reviews' },
  { path: '/admin/notifications', icon: BellRing, label: 'Notifications' },
  { path: '/admin/orders', icon: ShoppingBag, label: 'Orders' },
  { path: '/admin/customers', icon: Users, label: 'Users' },
  { path: '/admin/shipments', icon: MapPin, label: 'Shipments' },
  { path: '/admin/inventory', icon: Warehouse, label: 'Inventory' },
  { path: '/admin/returns', icon: RotateCcw, label: 'Return Exchange' },
  { path: '/admin/coupons', icon: TicketPercent, label: 'Coupons' },
  { path: '/admin/banners', icon: Monitor, label: 'Banners' },
  { path: '/admin/features', icon: Sparkles, label: 'Features' },
  { path: '/admin/settings', icon: Settings, label: 'Settings' },
  { path: '/admin/audit-logs', icon: ClipboardList, label: 'Audit Logs' },
];

const THEME_STORAGE_KEY = 'aurora-health-theme';

export const Sidebar: React.FC = () => {
  const location = useLocation();
  const branding = useBranding();

  return (
    <div className="w-16 bg-primary flex flex-col items-center py-5 gap-2 shrink-0 z-30 relative shadow-xl">
      {/* Brand Icon */}
      <Link 
        to="/admin" 
        className="w-10 h-10 rounded-xl bg-white/95 flex items-center justify-center mb-4 shadow-sm hover:scale-105 transition-transform"
        title={branding.brandName}
      >
        {branding.faviconUrl ? (
          <img src={branding.faviconUrl} alt={branding.brandName} className="h-6 w-6 object-contain" />
        ) : branding.logoUrl ? (
          <img src={branding.logoUrl} alt={branding.brandName} className="h-8 w-8 rounded-md object-cover" />
        ) : (
          <div className="w-5 h-5 rounded-full bg-primary flex items-center justify-center">
            <div className="w-2 h-2 rounded-full bg-white" />
          </div>
        )}
      </Link>

      {/* Nav Items */}
      {NAV_ITEMS.map((item) => {
        const isActive = location.pathname === item.path;
        return (
          <Link
            key={item.path}
            to={item.path}
            className="group relative flex items-center justify-center w-10 h-10 rounded-xl transition-all duration-200"
          >
            {/* Active Background */}
            <div 
              className={cn(
                "absolute inset-0 rounded-xl transition-colors duration-200",
                isActive ? "bg-white/20" : "group-hover:bg-white/10"
              )} 
            />
            
            {/* Icon */}
            <item.icon 
              size={20} 
              className={cn(
                "relative z-10 transition-colors duration-200",
                isActive ? "text-white" : "text-white/60 group-hover:text-white"
              )} 
            />

            {/* Tooltip */}
            <div className="absolute left-[52px] pointer-events-none opacity-0 group-hover:opacity-100 transition-opacity duration-200 z-[100]">
               <div className="bg-[#3a5936] text-white text-xs font-medium px-2.5 py-1.5 rounded-md whitespace-nowrap shadow-md">
                 {item.label}
                 {/* Tooltip Arrow */}
                 <div className="absolute top-1/2 -translate-y-1/2 -left-1 w-0 h-0 border-y-4 border-y-transparent border-r-4 border-r-[#3a5936]" />
               </div>
            </div>
          </Link>
        );
      })}
    </div>
  );
};

export const Topbar: React.FC = () => {
  type NotifyRequestItem = {
    id: string;
    product_name?: string;
    user_email?: string;
    email?: string;
    status?: string;
    is_notified?: boolean;
  };

  const location = useLocation();
  const navigate = useNavigate();
  const [sessionInfo, setSessionInfo] = useState({ warningOpen: false, secondsLeft: 0 });
  const [darkMode, setDarkMode] = useState(false);
  const [notifyUnreadCount, setNotifyUnreadCount] = useState(0);
  const [recentNotifyRequests, setRecentNotifyRequests] = useState<NotifyRequestItem[]>([]);
  const [enquiryUnreadCount, setEnquiryUnreadCount] = useState(0);
  const [recentEnquiries, setRecentEnquiries] = useState<ContactQueryItem[]>([]);
  const [profile, setProfile] = useState<ProfileData | null>(null);
  const [addresses, setAddresses] = useState<AddressData[]>([]);
  const [isAccountModalOpen, setIsAccountModalOpen] = useState(false);
  const [isAddressModalOpen, setIsAddressModalOpen] = useState(false);
  const [isAddressConfirmOpen, setIsAddressConfirmOpen] = useState(false);
  const [isPasswordModalOpen, setIsPasswordModalOpen] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [isChangingPassword, setIsChangingPassword] = useState(false);
  const [accountForm, setAccountForm] = useState({
    first_name: '',
    last_name: '',
    phone: '',
  });
  const [hasDifferentShipping, setHasDifferentShipping] = useState(false);
  const addressScrollRef = useRef<HTMLDivElement | null>(null);
  const [billingForm, setBillingForm] = useState({
    is_default: true,
    full_name: '',
    line1: '',
    line2: '',
    city: '',
    state: '',
    postal_code: '',
    country: 'India',
    phone: '',
  });
  const [shippingForm, setShippingForm] = useState({
    is_default: true,
    full_name: '',
    line1: '',
    line2: '',
    city: '',
    state: '',
    postal_code: '',
    country: 'India',
    phone: '',
  });
  const [billingFieldsLocked, setBillingFieldsLocked] = useState(false);
  const [shippingFieldsLocked, setShippingFieldsLocked] = useState(false);
  const [passwordForm, setPasswordForm] = useState({
    current_password: '',
    new_password: '',
    confirm_password: '',
  });

  const passwordRules = useMemo(() => {
    const p = passwordForm.new_password || '';
    return [
      { id: 'length', label: '8+ characters', met: p.length >= 8 },
      { id: 'upper', label: '1 uppercase letter', met: /[A-Z]/.test(p) },
      { id: 'digit', label: '1 digit', met: /[0-9]/.test(p) },
    ];
  }, [passwordForm.new_password]);

  const passwordStrength = useMemo(() => {
    const metCount = passwordRules.filter((rule) => rule.met).length;
    if (metCount === 0) return { score: 0, label: 'Weak', color: 'bg-destructive' };
    if (metCount === 1) return { score: 33, label: 'Fair', color: 'bg-orange-500' };
    if (metCount === 2) return { score: 66, label: 'Good', color: 'bg-yellow-500' };
    return { score: 100, label: 'Strong', color: 'bg-emerald-500' };
  }, [passwordRules]);

  const passwordsMatch = useMemo(() => {
    if (!passwordForm.confirm_password) return true;
    return passwordForm.new_password === passwordForm.confirm_password;
  }, [passwordForm.confirm_password, passwordForm.new_password]);

  const canSubmitPasswordChange = useMemo(() => {
    return (
      !!passwordForm.current_password &&
      !!passwordForm.new_password &&
      !!passwordForm.confirm_password &&
      passwordRules.every((rule) => rule.met) &&
      passwordsMatch
    );
  }, [passwordForm.current_password, passwordForm.new_password, passwordForm.confirm_password, passwordRules, passwordsMatch]);

  const handleBillingAutoResolved = useCallback((payload: { city: string; state: string; area: string; areas: string[]; pincode: string }, _source: 'pincode' | 'gps') => {
    setBillingForm((prev) => ({
      ...prev,
      city: payload.city || prev.city,
      state: payload.state || prev.state,
      line2: prev.line2 || payload.area || prev.line2,
    }));
    if (payload.city || payload.state) {
      setBillingFieldsLocked(true);
    }
  }, []);

  const handleShippingAutoResolved = useCallback((payload: { city: string; state: string; area: string; areas: string[]; pincode: string }, _source: 'pincode' | 'gps') => {
    setShippingForm((prev) => ({
      ...prev,
      city: payload.city || prev.city,
      state: payload.state || prev.state,
      line2: prev.line2 || payload.area || prev.line2,
    }));
    if (payload.city || payload.state) {
      setShippingFieldsLocked(true);
    }
  }, []);

  const billingAutoFill = useAddressAutoFill({
    pincode: billingForm.postal_code,
    onResolved: handleBillingAutoResolved,
    enabled: isAddressModalOpen,
  });

  const shippingAutoFill = useAddressAutoFill({
    pincode: shippingForm.postal_code,
    onResolved: handleShippingAutoResolved,
    enabled: isAddressModalOpen && hasDifferentShipping,
  });

  useEffect(() => {
    const savedTheme = localStorage.getItem(THEME_STORAGE_KEY);
    if (savedTheme === 'dark') {
      setDarkMode(true);
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
  }, []);

  useEffect(() => {
    const onSessionUpdate = (event: Event) => {
      const custom = event as CustomEvent<{ warningOpen: boolean; secondsLeft: number }>;
      if (!custom.detail) return;
      setSessionInfo({
        warningOpen: Boolean(custom.detail.warningOpen),
        secondsLeft: Number(custom.detail.secondsLeft || 0),
      });
    };

    window.addEventListener('aurora:session-timeout-update', onSessionUpdate as EventListener);
    return () => {
      window.removeEventListener('aurora:session-timeout-update', onSessionUpdate as EventListener);
    };
  }, []);

  const loadProfile = async () => {
    try {
      const profileRes = await profileService.getProfile();
      const addressRes = await profileService.getAddresses();
      const p = profileRes?.data as ProfileData;
      const a = Array.isArray(addressRes?.data) ? (addressRes.data as AddressData[]) : [];
      setProfile(p);
      setAddresses(a);

      const billing = a.find((x) => x.address_type === 'billing') || a.find((x) => x.is_default) || a[0];
      const shipping = a.find((x) => x.address_type === 'shipping');

      const sameAddress =
        !!billing &&
        !!shipping &&
        billing.full_name === shipping.full_name &&
        billing.line1 === shipping.line1 &&
        (billing.line2 || '') === (shipping.line2 || '') &&
        billing.city === shipping.city &&
        (billing.state || '') === (shipping.state || '') &&
        billing.postal_code === shipping.postal_code &&
        billing.country === shipping.country &&
        (billing.phone || '') === (shipping.phone || '');

      setHasDifferentShipping(Boolean(shipping && !sameAddress));
      setAccountForm({
        first_name: p?.first_name || '',
        last_name: p?.last_name || '',
        phone: p?.phone || '',
      });
      setBillingForm({
        is_default: billing?.is_default ?? true,
        full_name: billing?.full_name || `${p?.first_name || ''} ${p?.last_name || ''}`.trim(),
        line1: billing?.line1 || '',
        line2: billing?.line2 || '',
        city: billing?.city || '',
        state: billing?.state || '',
        postal_code: billing?.postal_code || '',
        country: billing?.country || 'India',
        phone: billing?.phone || p?.phone || '',
      });
      setShippingForm({
        is_default: shipping?.is_default ?? true,
        full_name: shipping?.full_name || `${p?.first_name || ''} ${p?.last_name || ''}`.trim(),
        line1: shipping?.line1 || '',
        line2: shipping?.line2 || '',
        city: shipping?.city || '',
        state: shipping?.state || '',
        postal_code: shipping?.postal_code || '',
        country: shipping?.country || 'India',
        phone: shipping?.phone || p?.phone || '',
      });
      setBillingFieldsLocked(false);
      setShippingFieldsLocked(false);
    } catch (error) {
      console.error('Failed to load profile:', error);
    }
  };

  useEffect(() => {
    loadProfile();
  }, []);

  useEffect(() => {
    const loadTopNotifications = async () => {
      try {
        const [notifyResponse, enquiryResponse] = await Promise.all([
          notifyService.listAdmin({ is_notified: 'false' }),
          notifyService.listContactQueries(),
        ]);

        const notifyRows = Array.isArray(notifyResponse?.data) ? (notifyResponse.data as NotifyRequestItem[]) : [];
        const enquiryRows = Array.isArray(enquiryResponse?.data) ? enquiryResponse.data : [];

        setNotifyUnreadCount(notifyRows.length);
        setRecentNotifyRequests(notifyRows.slice(0, 6));
        setEnquiryUnreadCount(enquiryRows.filter((item) => !item.is_read).length);
        setRecentEnquiries(enquiryRows.slice(0, 6));
      } catch {
        setNotifyUnreadCount(0);
        setRecentNotifyRequests([]);
        setEnquiryUnreadCount(0);
        setRecentEnquiries([]);
      }
    };

    loadTopNotifications();
    const timer = window.setInterval(loadTopNotifications, 60000);
    return () => window.clearInterval(timer);
  }, [location.pathname]);

  const markEnquiryRead = async (id: string) => {
    try {
      await notifyService.markContactQueriesRead([id]);
      setRecentEnquiries((prev) => prev.map((item) => (item.id === id ? { ...item, is_read: true, status: 'read' } : item)));
      setEnquiryUnreadCount((prev) => Math.max(0, prev - 1));
    } catch {
      // keep topbar responsive even if API fails
    }
  };

  const totalNotificationCount = notifyUnreadCount + enquiryUnreadCount;

  const mins = Math.floor(Math.max(0, sessionInfo.secondsLeft) / 60)
    .toString()
    .padStart(2, '0');
  const secs = (Math.max(0, sessionInfo.secondsLeft) % 60).toString().padStart(2, '0');
  const timerLabel = `${mins}:${secs}`;
  const displayName = (profile?.full_name || `${profile?.first_name || ''} ${profile?.last_name || ''}`.trim() || 'User').trim();
  const roleLabel = profile?.role ? `${profile.role.charAt(0).toUpperCase()}${profile.role.slice(1)}` : 'User';
  const initials = `${profile?.first_name?.[0] || ''}${profile?.last_name?.[0] || ''}`.toUpperCase() || 'U';

  const handleOpenAccount = () => {
    setIsAccountModalOpen(true);
  };

  const handleOpenAddress = () => {
    setIsAddressModalOpen(true);
  };

  const handleSaveAccountDetails = async () => {
    try {
      setIsSaving(true);
      const profilePayload = {
        first_name: accountForm.first_name.trim(),
        last_name: accountForm.last_name.trim(),
        phone: accountForm.phone.trim(),
      };
      await profileService.updateProfile(profilePayload);
      await loadProfile();

      const latestUser = {
        ...(JSON.parse(localStorage.getItem('auth_user') || '{}') || {}),
        first_name: profilePayload.first_name,
        last_name: profilePayload.last_name,
        full_name: `${profilePayload.first_name} ${profilePayload.last_name}`.trim(),
        phone: profilePayload.phone,
      };
      localStorage.setItem('auth_user', JSON.stringify(latestUser));
      setIsAccountModalOpen(false);
    } catch (error) {
      console.error(error);
      alert('Failed to update account details.');
    } finally {
      setIsSaving(false);
    }
  };

  const validateAddress = (label: string, data: typeof billingForm) => {
    if (!data.full_name.trim() || !data.line1.trim() || !data.city.trim() || !data.postal_code.trim() || !data.country.trim()) {
      alert(`${label}: Please fill full name, line 1, city, postal code, and country.`);
      return false;
    }
    return true;
  };

  const upsertAddress = async (type: 'billing' | 'shipping', payload: typeof billingForm) => {
    const existing = addresses.find((a) => a.address_type === type);
    const body: AddressData = {
      address_type: type,
      is_default: payload.is_default,
      full_name: payload.full_name.trim(),
      line1: payload.line1.trim(),
      line2: payload.line2.trim(),
      city: payload.city.trim(),
      state: payload.state.trim(),
      postal_code: payload.postal_code.trim(),
      country: payload.country.trim() || 'India',
      phone: payload.phone.trim(),
    };

    if (existing?.id) {
      await profileService.updateAddress(existing.id, body);
    } else {
      await profileService.createAddress(body);
    }
  };

  const persistAddressDetails = async (differentShipping: boolean) => {
    try {
      setIsSaving(true);
      await upsertAddress('billing', billingForm);
      if (differentShipping) {
        await upsertAddress('shipping', shippingForm);
      } else {
        await upsertAddress('shipping', {
          ...billingForm,
          is_default: true,
        });
      }
      await loadProfile();
      setIsAddressModalOpen(false);
      setIsAddressConfirmOpen(false);
    } catch (error) {
      console.error(error);
      alert('Failed to update address details.');
    } finally {
      setIsSaving(false);
    }
  };

  const handleSaveAddressDetails = async () => {
    if (!validateAddress('Billing address', billingForm)) return;
    if (hasDifferentShipping && !validateAddress('Shipping address', shippingForm)) return;

    if (!hasDifferentShipping) {
      setIsAddressConfirmOpen(true);
      return;
    }

    await persistAddressDetails(true);
  };

  const handleOpenPassword = () => {
    setPasswordForm({
      current_password: '',
      new_password: '',
      confirm_password: '',
    });
    setIsPasswordModalOpen(true);
  };

  const handleChangePassword = async () => {
    if (!passwordForm.current_password || !passwordForm.new_password || !passwordForm.confirm_password) {
      alert('Please fill all password fields.');
      return;
    }
    if (!passwordRules.every((rule) => rule.met)) {
      alert('Please enter a stronger password that meets all requirements.');
      return;
    }
    if (!passwordsMatch) {
      alert('New password and confirm password do not match.');
      return;
    }

    try {
      setIsChangingPassword(true);
      await profileService.changePassword({
        current_password: passwordForm.current_password,
        new_password: passwordForm.new_password,
      });
      setIsPasswordModalOpen(false);
      alert('Password changed successfully.');
    } catch (error: any) {
      const message = error?.response?.data?.message || 'Failed to change password.';
      alert(message);
    } finally {
      setIsChangingPassword(false);
    }
  };

  const handleAddressModalWheel = (event: React.WheelEvent<HTMLDivElement>) => {
    const container = addressScrollRef.current;
    if (!container) return;
    if (container.scrollHeight <= container.clientHeight) return;

    event.preventDefault();
    event.stopPropagation();
    container.scrollTop += event.deltaY;
  };

  const handleLogout = async () => {
    try {
      const refresh = localStorage.getItem('refresh_token');
      if (refresh) {
        await profileService.logout(refresh);
      }
    } catch (error) {
      // Proceed with local logout even if API logout fails.
    } finally {
      localStorage.removeItem('auth_token');
      localStorage.removeItem('refresh_token');
      localStorage.removeItem('auth_user');
      window.dispatchEvent(new CustomEvent('aurora:auth-changed'));
      navigate('/login', { replace: true });
    }
  };

  const handleToggleTheme = () => {
    const next = !darkMode;
    setDarkMode(next);
    localStorage.setItem(THEME_STORAGE_KEY, next ? 'dark' : 'light');
    document.documentElement.classList.toggle('dark', next);
  };

  return (
    <>
    <div className="flex items-center gap-4 mb-6 sticky top-0 bg-background/95 backdrop-blur-sm z-20 py-4 -mt-4">
      {/* Search */}
      <div className="flex-1 relative max-w-xl">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" size={16} />
        <Input 
          className="w-full pl-9 bg-white border-border rounded-xl shadow-sm h-10 text-sm" 
          placeholder="Search orders, products, or customers..." 
        />
      </div>

      <div className="ml-auto flex items-center gap-2">
        <div
          className={cn(
            'rounded-full border px-3 py-1 text-xs font-semibold transition-colors',
            sessionInfo.warningOpen
              ? 'border-red-300 bg-red-50 text-red-700'
              : 'border-primary/30 bg-primary/5 text-primary'
          )}
        >
          Auto logout in {timerLabel}
        </div>
        {sessionInfo.warningOpen ? (
          <>
            <button
              type="button"
              onClick={() => window.dispatchEvent(new Event('aurora:session-timeout-extend'))}
              className="rounded-full border border-primary/40 bg-white px-3 py-1 text-xs font-semibold text-primary transition-all hover:border-primary hover:bg-primary hover:text-primary-foreground"
            >
              Remain Logged In
            </button>
            <button
              type="button"
              onClick={() => window.dispatchEvent(new Event('aurora:session-timeout-logout'))}
              className="rounded-full border border-red-300 bg-white px-3 py-1 text-xs font-semibold text-red-600 transition-all hover:border-red-600 hover:bg-red-600 hover:text-white"
            >
              Logout
            </button>
          </>
        ) : null}
      </div>

      {/* Actions */}
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={handleToggleTheme}
          className="w-10 h-10 rounded-full border border-border bg-white flex items-center justify-center text-muted-foreground hover:text-foreground transition-colors"
          title={darkMode ? 'Switch to light mode' : 'Switch to dark mode'}
          aria-label={darkMode ? 'Switch to light mode' : 'Switch to dark mode'}
        >
          {darkMode ? <SunMedium size={18} /> : <MoonStar size={18} />}
        </button>
        <Link
          to="/admin/health"
          className="w-10 h-10 rounded-full border border-border bg-white flex items-center justify-center text-muted-foreground hover:text-foreground transition-colors"
          title="System Health"
          aria-label="Open system health"
        >
          <HeartPulse size={18} />
        </Link>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <button
              type="button"
              className="w-10 h-10 rounded-full border border-border bg-white flex items-center justify-center text-muted-foreground hover:text-foreground transition-colors relative"
              title={`Notifications${totalNotificationCount > 0 ? ` (${totalNotificationCount} unread)` : ''}`}
              aria-label={`Open notifications${totalNotificationCount > 0 ? `, ${totalNotificationCount} unread` : ''}`}
            >
              <Bell size={18} />
              {totalNotificationCount > 0 ? (
                <span className="absolute -top-1 -right-1 min-w-[18px] h-[18px] rounded-full bg-primary text-primary-foreground text-[10px] font-bold px-1 flex items-center justify-center">
                  {totalNotificationCount > 99 ? '99+' : totalNotificationCount}
                </span>
              ) : null}
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-[380px] p-0 overflow-hidden">
            <div className="px-4 py-3 border-b border-border bg-muted/20">
              <div className="text-sm font-semibold text-foreground">Notifications</div>
              <div className="text-xs text-muted-foreground">{totalNotificationCount} unread</div>
            </div>

            <div className="px-4 pt-3 pb-2 border-b border-border/70 bg-white">
              <div className="flex items-center justify-between">
                <div className="text-xs font-semibold text-foreground">Out-of-stock requests</div>
                <span className="text-[11px] text-muted-foreground">{notifyUnreadCount} unread</span>
              </div>
            </div>
            <div className="max-h-[180px] overflow-y-auto">
              {recentNotifyRequests.length === 0 ? (
                <div className="px-4 py-3 text-xs text-muted-foreground">No out-of-stock requests.</div>
              ) : (
                recentNotifyRequests.map((request) => (
                  <DropdownMenuItem
                    key={request.id}
                    onClick={() => {
                      navigate('/admin/notify-requests');
                    }}
                    className="items-start gap-2 px-4 py-3 cursor-pointer"
                  >
                    <div className="mt-1 h-2 w-2 rounded-full shrink-0 bg-primary" />
                    <div className="min-w-0 flex-1">
                      <div className="text-xs font-semibold text-foreground truncate">
                        {request.product_name || 'Product alert'}
                      </div>
                      <div className="text-[11px] text-muted-foreground truncate">
                        {(request.user_email || request.email || 'Guest request').trim()}
                      </div>
                    </div>
                  </DropdownMenuItem>
                ))
              )}
            </div>

            <div className="px-4 pt-3 pb-2 border-y border-border/70 bg-white">
              <div className="flex items-center justify-between">
                <div className="text-xs font-semibold text-foreground">Enquiries</div>
                <span className="text-[11px] text-muted-foreground">{enquiryUnreadCount} unread</span>
              </div>
            </div>
            <div className="max-h-[180px] overflow-y-auto">
              {recentEnquiries.length === 0 ? (
                <div className="px-4 py-3 text-xs text-muted-foreground">No enquiries yet.</div>
              ) : (
                recentEnquiries.map((enquiry) => (
                  <DropdownMenuItem
                    key={enquiry.id}
                    onClick={() => {
                      if (!enquiry.is_read) {
                        void markEnquiryRead(enquiry.id);
                      }
                    }}
                    className="items-start gap-2 px-4 py-3 cursor-pointer"
                  >
                    <div className={cn('mt-1 h-2 w-2 rounded-full shrink-0', enquiry.is_read ? 'bg-border' : 'bg-primary')} />
                    <div className="min-w-0 flex-1">
                      <div className="text-xs font-semibold text-foreground truncate">{enquiry.name}</div>
                      <div className="text-[11px] text-muted-foreground truncate">{enquiry.subject || 'General enquiry'}</div>
                      <div className="text-[11px] text-muted-foreground truncate">{enquiry.email}</div>
                    </div>
                  </DropdownMenuItem>
                ))
              )}
            </div>

            <div className="px-4 py-2 border-t border-border bg-muted/10 flex items-center justify-between gap-4">
              <button
                type="button"
                className="text-xs font-medium text-primary hover:underline"
                onClick={() => navigate('/admin/notify-requests')}
              >
                View stock requests
              </button>
              <button
                type="button"
                className="text-xs font-medium text-primary hover:underline"
                onClick={() => navigate('/admin/enquiries')}
              >
                View enquiries
              </button>
            </div>
          </DropdownMenuContent>
        </DropdownMenu>
        
        {/* Profile */}
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <button className="flex items-center gap-3 pl-2 border-l border-border">
              <div className="w-10 h-10 rounded-full bg-primary/10 border-2 border-primary/20 flex items-center justify-center text-primary font-bold text-sm shrink-0">
                {initials}
              </div>
              <div className="hidden lg:block text-left">
                <div className="text-sm font-bold text-foreground leading-none">{displayName}</div>
                <div className="text-xs text-muted-foreground mt-1">{roleLabel}</div>
              </div>
              <ChevronDown size={14} className="text-muted-foreground" />
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-[220px]">
            <DropdownMenuItem onClick={handleOpenAccount} className="flex items-center gap-2 cursor-pointer text-sm">
              <UserCog size={14} />
              Account Details
            </DropdownMenuItem>
            <DropdownMenuItem onClick={handleOpenAddress} className="flex items-center gap-2 cursor-pointer text-sm">
              <MapPin size={14} />
              Address Details
            </DropdownMenuItem>
            <DropdownMenuItem onClick={handleOpenPassword} className="flex items-center gap-2 cursor-pointer text-sm">
              <KeyRound size={14} />
              Change Password
            </DropdownMenuItem>
            <DropdownMenuItem onClick={handleLogout} className="flex items-center gap-2 cursor-pointer text-sm text-destructive focus:text-destructive">
              <LogOut size={14} />
              Logout
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </div>
    <Modal open={isAccountModalOpen} onOpenChange={setIsAccountModalOpen}>
      <ModalContent className="max-w-xl">
        <ModalHeader>
          <ModalTitle>Account Details</ModalTitle>
        </ModalHeader>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 py-4">
          <div className="grid gap-2">
            <label className="text-xs font-bold uppercase text-muted-foreground">First Name</label>
            <Input value={accountForm.first_name} onChange={(e) => setAccountForm({ ...accountForm, first_name: e.target.value })} />
          </div>
          <div className="grid gap-2">
            <label className="text-xs font-bold uppercase text-muted-foreground">Last Name</label>
            <Input value={accountForm.last_name} onChange={(e) => setAccountForm({ ...accountForm, last_name: e.target.value })} />
          </div>
          <div className="grid gap-2">
            <label className="text-xs font-bold uppercase text-muted-foreground">Email</label>
            <Input value={profile?.email || ''} readOnly className="bg-muted/30 cursor-not-allowed" />
          </div>
          <div className="grid gap-2">
            <label className="text-xs font-bold uppercase text-muted-foreground">Phone</label>
            <Input value={accountForm.phone} onChange={(e) => setAccountForm({ ...accountForm, phone: e.target.value })} />
          </div>
        </div>
        <ModalFooter>
          <Button
            variant="outline"
            onClick={() => setIsAccountModalOpen(false)}
            className="rounded-xl border-primary/40 bg-white text-primary hover:bg-primary hover:text-primary-foreground"
          >
            Cancel
          </Button>
          <Button
            variant="outline"
            onClick={handleSaveAccountDetails}
            disabled={isSaving}
            className="rounded-xl border-primary/40 bg-white text-primary hover:bg-primary hover:text-primary-foreground"
          >
            {isSaving ? 'Saving...' : 'Save Changes'}
          </Button>
        </ModalFooter>
      </ModalContent>
    </Modal>
    <Modal open={isAddressModalOpen} onOpenChange={setIsAddressModalOpen}>
      <ModalContent className="max-w-3xl max-h-[90vh] overflow-hidden">
        <ModalHeader>
          <ModalTitle>Address Details</ModalTitle>
        </ModalHeader>
        <div
          ref={addressScrollRef}
          className="max-h-[62vh] overflow-y-auto pr-1"
          onWheel={handleAddressModalWheel}
        >
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 py-4">
          <div className="md:col-span-2">
            <h4 className="text-sm font-bold text-foreground">Billing Address</h4>
            <p className="text-xs text-muted-foreground">Billing address is required by default.</p>
          </div>
          <div className="grid gap-2">
            <label className="text-xs font-bold uppercase text-muted-foreground">Recipient Name</label>
            <Input value={billingForm.full_name} onChange={(e) => setBillingForm({ ...billingForm, full_name: e.target.value })} />
          </div>
          <div className="grid gap-2">
            <label className="text-xs font-bold uppercase text-muted-foreground">Phone</label>
            <Input value={billingForm.phone} onChange={(e) => setBillingForm({ ...billingForm, phone: e.target.value })} />
          </div>
          <div className="grid gap-2 md:col-span-2">
            <label className="text-xs font-bold uppercase text-muted-foreground">Address Line 1</label>
            <Input value={billingForm.line1} onChange={(e) => setBillingForm({ ...billingForm, line1: e.target.value })} />
          </div>
          <div className="grid gap-2 md:col-span-2">
            <label className="text-xs font-bold uppercase text-muted-foreground">Address Line 2</label>
            <Input value={billingForm.line2} onChange={(e) => setBillingForm({ ...billingForm, line2: e.target.value })} />
          </div>
          <div className="grid gap-2">
            <label className="text-xs font-bold uppercase text-muted-foreground">Postal Code</label>
            <Input
              value={billingForm.postal_code}
              onChange={(e) => setBillingForm({ ...billingForm, postal_code: e.target.value.replace(/\D/g, '').slice(0, 6) })}
            />
            {billingAutoFill.isLoading ? <p className="text-xs text-muted-foreground">Detecting location...</p> : null}
            {billingAutoFill.locationLabel ? <p className="text-xs text-emerald-700">{billingAutoFill.locationLabel}</p> : null}
            {billingAutoFill.error ? <p className="text-xs text-amber-700">{billingAutoFill.error}</p> : null}
          </div>
          <div className="grid gap-2">
            <div className="flex items-center justify-between">
              <label className="text-xs font-bold uppercase text-muted-foreground">City</label>
              {billingFieldsLocked ? (
                <button type="button" className="text-[11px] text-primary underline" onClick={() => setBillingFieldsLocked(false)}>
                  Edit manually
                </button>
              ) : null}
            </div>
            <Input
              value={billingForm.city}
              disabled={billingFieldsLocked}
              onChange={(e) => setBillingForm({ ...billingForm, city: e.target.value })}
            />
          </div>
          <div className="grid gap-2">
            <label className="text-xs font-bold uppercase text-muted-foreground">State</label>
            <Input
              value={billingForm.state}
              disabled={billingFieldsLocked}
              onChange={(e) => setBillingForm({ ...billingForm, state: e.target.value })}
            />
          </div>
          <div className="grid gap-2">
            <label className="text-xs font-bold uppercase text-muted-foreground">Country</label>
            <Input value={billingForm.country} onChange={(e) => setBillingForm({ ...billingForm, country: e.target.value })} />
          </div>
          <div className="md:col-span-2 pt-2">
            <label className="flex items-center gap-2 text-sm text-muted-foreground">
              <input
                type="checkbox"
                checked={hasDifferentShipping}
                onChange={(e) => setHasDifferentShipping(e.target.checked)}
              />
              Add different shipping address
            </label>
          </div>
          {hasDifferentShipping ? (
            <>
              <div className="md:col-span-2 border-t border-border/70 pt-4 mt-1">
                <h4 className="text-sm font-bold text-foreground">Shipping Address</h4>
                <p className="text-xs text-muted-foreground">Provide shipping address only if it differs from billing.</p>
              </div>
              <div className="grid gap-2">
                <label className="text-xs font-bold uppercase text-muted-foreground">Recipient Name</label>
                <Input value={shippingForm.full_name} onChange={(e) => setShippingForm({ ...shippingForm, full_name: e.target.value })} />
              </div>
              <div className="grid gap-2">
                <label className="text-xs font-bold uppercase text-muted-foreground">Phone</label>
                <Input value={shippingForm.phone} onChange={(e) => setShippingForm({ ...shippingForm, phone: e.target.value })} />
              </div>
              <div className="grid gap-2 md:col-span-2">
                <label className="text-xs font-bold uppercase text-muted-foreground">Address Line 1</label>
                <Input value={shippingForm.line1} onChange={(e) => setShippingForm({ ...shippingForm, line1: e.target.value })} />
              </div>
              <div className="grid gap-2 md:col-span-2">
                <label className="text-xs font-bold uppercase text-muted-foreground">Address Line 2</label>
                <Input value={shippingForm.line2} onChange={(e) => setShippingForm({ ...shippingForm, line2: e.target.value })} />
              </div>
              <div className="grid gap-2">
                <label className="text-xs font-bold uppercase text-muted-foreground">Postal Code</label>
                <Input
                  value={shippingForm.postal_code}
                  onChange={(e) => setShippingForm({ ...shippingForm, postal_code: e.target.value.replace(/\D/g, '').slice(0, 6) })}
                />
                {shippingAutoFill.isLoading ? <p className="text-xs text-muted-foreground">Detecting location...</p> : null}
                {shippingAutoFill.locationLabel ? <p className="text-xs text-emerald-700">{shippingAutoFill.locationLabel}</p> : null}
                {shippingAutoFill.error ? <p className="text-xs text-amber-700">{shippingAutoFill.error}</p> : null}
              </div>
              <div className="grid gap-2">
                <div className="flex items-center justify-between">
                  <label className="text-xs font-bold uppercase text-muted-foreground">City</label>
                  {shippingFieldsLocked ? (
                    <button type="button" className="text-[11px] text-primary underline" onClick={() => setShippingFieldsLocked(false)}>
                      Edit manually
                    </button>
                  ) : null}
                </div>
                <Input
                  value={shippingForm.city}
                  disabled={shippingFieldsLocked}
                  onChange={(e) => setShippingForm({ ...shippingForm, city: e.target.value })}
                />
              </div>
              <div className="grid gap-2">
                <label className="text-xs font-bold uppercase text-muted-foreground">State</label>
                <Input
                  value={shippingForm.state}
                  disabled={shippingFieldsLocked}
                  onChange={(e) => setShippingForm({ ...shippingForm, state: e.target.value })}
                />
              </div>
              <div className="grid gap-2">
                <label className="text-xs font-bold uppercase text-muted-foreground">Country</label>
                <Input value={shippingForm.country} onChange={(e) => setShippingForm({ ...shippingForm, country: e.target.value })} />
              </div>
            </>
          ) : null}
        </div>
        </div>
        <ModalFooter>
          <Button
            variant="outline"
            onClick={() => setIsAddressModalOpen(false)}
            className="rounded-xl border-primary/40 bg-white text-primary hover:bg-primary hover:text-primary-foreground"
          >
            Cancel
          </Button>
          <Button
            variant="outline"
            onClick={handleSaveAddressDetails}
            disabled={isSaving}
            className="rounded-xl border-primary/40 bg-white text-primary hover:bg-primary hover:text-primary-foreground"
          >
            {isSaving ? 'Saving...' : 'Save Changes'}
          </Button>
        </ModalFooter>
      </ModalContent>
    </Modal>
    <Modal open={isAddressConfirmOpen} onOpenChange={setIsAddressConfirmOpen}>
      <ModalContent className="max-w-md">
        <ModalHeader>
          <ModalTitle>Confirm Address Usage</ModalTitle>
        </ModalHeader>
        <div className="space-y-3 py-2">
          <p className="text-sm text-muted-foreground">
            You have not added a different shipping address.
          </p>
          <div className="rounded-xl border border-border bg-muted/30 p-3 text-sm">
            Billing address will also be used as shipping address.
          </div>
          <p className="text-xs text-muted-foreground">
            Continue to save both billing and shipping with the same details?
          </p>
        </div>
        <ModalFooter>
          <Button
            variant="outline"
            onClick={() => setIsAddressConfirmOpen(false)}
            className="rounded-xl border-primary/40 bg-white text-primary hover:bg-primary hover:text-primary-foreground"
          >
            Review
          </Button>
          <Button
            variant="outline"
            onClick={() => persistAddressDetails(false)}
            disabled={isSaving}
            className="rounded-xl border-primary/40 bg-white text-primary hover:bg-primary hover:text-primary-foreground"
          >
            {isSaving ? 'Saving...' : 'Confirm & Save'}
          </Button>
        </ModalFooter>
      </ModalContent>
    </Modal>
    <Modal open={isPasswordModalOpen} onOpenChange={setIsPasswordModalOpen}>
      <ModalContent className="max-w-md">
        <ModalHeader>
          <ModalTitle>Change Password</ModalTitle>
        </ModalHeader>
        <div className="space-y-4 py-3">
          <div className="grid gap-2">
            <label className="text-xs font-bold uppercase text-muted-foreground">Current Password</label>
            <Input
              type="password"
              value={passwordForm.current_password}
              onChange={(e) => setPasswordForm({ ...passwordForm, current_password: e.target.value })}
              autoComplete="current-password"
            />
          </div>
          <div className="grid gap-2">
            <div className="flex items-center justify-between">
              <label className="text-xs font-bold uppercase text-muted-foreground">New Password</label>
              <span className={cn('text-[10px] font-bold px-2 py-0.5 rounded-full text-white', passwordStrength.color)}>
                {passwordStrength.label}
              </span>
            </div>
            <Input
              type="password"
              value={passwordForm.new_password}
              onChange={(e) => setPasswordForm({ ...passwordForm, new_password: e.target.value })}
              autoComplete="new-password"
            />
            <div className="h-1 w-full bg-muted rounded-full overflow-hidden">
              <div
                className={cn('h-full transition-all duration-300', passwordStrength.color)}
                style={{ width: `${passwordStrength.score}%` }}
              />
            </div>
            <div className="grid grid-cols-1 gap-1.5 mt-1">
              {passwordRules.map((rule) => (
                <div key={rule.id} className="flex items-center gap-2 text-[10px]">
                  {rule.met ? <Check size={12} className="text-emerald-500" /> : <X size={12} className="text-muted-foreground" />}
                  <span className={rule.met ? 'text-foreground font-medium' : 'text-muted-foreground'}>{rule.label}</span>
                </div>
              ))}
            </div>
          </div>
          <div className="grid gap-2">
            <label className="text-xs font-bold uppercase text-muted-foreground">Confirm New Password</label>
            <Input
              type="password"
              value={passwordForm.confirm_password}
              onChange={(e) => setPasswordForm({ ...passwordForm, confirm_password: e.target.value })}
              autoComplete="new-password"
            />
            {!passwordsMatch ? (
              <p className="text-[11px] text-destructive">Passwords do not match.</p>
            ) : passwordForm.confirm_password ? (
              <p className="text-[11px] text-emerald-600">Passwords match.</p>
            ) : null}
          </div>
        </div>
        <ModalFooter>
          <Button
            variant="outline"
            onClick={() => setIsPasswordModalOpen(false)}
            className="rounded-xl border-primary/40 bg-white text-primary hover:bg-primary hover:text-primary-foreground"
          >
            Cancel
          </Button>
          <Button
            variant="outline"
            onClick={handleChangePassword}
            disabled={isChangingPassword || !canSubmitPasswordChange}
            className="rounded-xl border-primary/40 bg-white text-primary hover:bg-primary hover:text-primary-foreground"
          >
            {isChangingPassword ? 'Updating...' : 'Update Password'}
          </Button>
        </ModalFooter>
      </ModalContent>
    </Modal>
    </>
  );
};
