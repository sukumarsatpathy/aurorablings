import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import settingsService from '@/services/api/settings';
import profileService, { type ProfileData } from '@/services/api/profile';
import type { AppSetting } from '@/types/setting';
import { SettingsSidebar } from './SettingsSidebar';
import { SettingsContent } from './SettingsContent';
import type { SettingsCategoryMenu, SettingsToast } from './types';

const extractRows = (payload: any): AppSetting[] => {
  if (Array.isArray(payload?.data)) return payload.data as AppSetting[];
  if (Array.isArray(payload?.data?.results)) return payload.data.results as AppSetting[];
  if (Array.isArray(payload?.results)) return payload.results as AppSetting[];
  if (Array.isArray(payload)) return payload as AppSetting[];
  return [];
};

export const SettingsPage: React.FC = () => {
  const [activeCategory, setActiveCategory] = useState<SettingsCategoryMenu>('general');
  const [settings, setSettings] = useState<AppSetting[]>([]);
  const [profile, setProfile] = useState<ProfileData | null>(null);
  const [loading, setLoading] = useState(true);
  const [toasts, setToasts] = useState<SettingsToast[]>([]);
  const pageRef = useRef<HTMLDivElement | null>(null);

  const canEdit = useMemo(() => {
    const role = (profile?.role || '').toLowerCase();
    return role === 'admin' || role === 'staff';
  }, [profile]);

  const pushToast = useCallback((variant: 'success' | 'error' | 'info', message: string) => {
    const id = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
    setToasts((prev) => [...prev, { id, variant, message }]);
    window.setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 2800);
  }, []);

  const loadSettings = useCallback(async () => {
    try {
      setLoading(true);
      const response = await settingsService.getAll();
      setSettings(extractRows(response));
    } catch (error: any) {
      pushToast('error', error?.response?.data?.message || 'Failed to load settings.');
    } finally {
      setLoading(false);
    }
  }, [pushToast]);

  useEffect(() => {
    loadSettings();
  }, [loadSettings]);

  useEffect(() => {
    (async () => {
      try {
        const res = await profileService.getProfile();
        if (res?.data) setProfile(res.data as ProfileData);
      } catch {
        setProfile(null);
      }
    })();
  }, []);

  useEffect(() => {
    const pageEl = pageRef.current;
    if (!pageEl) return;

    const scrollHost = pageEl.closest('.overflow-y-auto') as HTMLElement | null;
    if (!scrollHost) return;

    const onWheelCapture = (event: WheelEvent) => {
      const target = event.target as Node | null;
      if (target && !pageEl.contains(target)) return;
      if (Math.abs(event.deltaY) < 0.1) return;

      event.preventDefault();
      event.stopPropagation();
      scrollHost.scrollTop += event.deltaY;
    };

    window.addEventListener('wheel', onWheelCapture, { passive: false, capture: true });
    return () => {
      window.removeEventListener('wheel', onWheelCapture, { capture: true } as EventListenerOptions);
    };
  }, []);

  return (
    <div ref={pageRef} className="space-y-6 max-w-7xl">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-foreground">Settings</h1>
        <p className="text-xs text-muted-foreground mt-1">
          Schema-driven configuration panel with plugin-ready forms and guarded access.
        </p>
      </div>

      {!canEdit ? (
        <div className="rounded-xl border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-800">
          You have read-only access to settings. Contact an admin to edit configuration.
        </div>
      ) : null}

      {loading ? (
        <div className="rounded-2xl border border-border/70 bg-white p-8 text-center text-sm text-muted-foreground">
          Loading settings...
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-6 md:grid-cols-[260px_1fr]">
          <SettingsSidebar active={activeCategory} onChange={setActiveCategory} />
          <SettingsContent
            category={activeCategory}
            settings={settings}
            canEdit={canEdit}
            onRefresh={loadSettings}
            onToast={pushToast}
          />
        </div>
      )}

      <div className="pointer-events-none fixed right-5 top-5 z-50 space-y-2">
        {toasts.map((toast) => (
          <div
            key={toast.id}
            className={[
              'rounded-xl border bg-white px-4 py-3 text-sm shadow-lg',
              toast.variant === 'success' ? 'border-emerald-300 text-emerald-700' : '',
              toast.variant === 'error' ? 'border-destructive/40 text-destructive' : '',
              toast.variant === 'info' ? 'border-blue-300 text-blue-700' : '',
            ].join(' ')}
          >
            {toast.message}
          </div>
        ))}
      </div>
    </div>
  );
};
