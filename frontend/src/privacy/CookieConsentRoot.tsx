import { useEffect, useMemo, useState } from 'react';
import './cookie-consent.css';
import {
  canLoadAnalytics,
  canLoadMarketing,
  createConsentPayload,
  getDefaultCategories,
  getStoredConsent,
  saveConsent,
  subscribeToConsent,
  type ConsentCategories,
  type ConsentPayload,
} from './consentManager';
import { applyConsentSideEffects, loadDeferredScripts } from './scriptLoader';
import { CookieBanner } from './components/CookieBanner';
import { CookiePreferencesModal } from './components/CookiePreferencesModal';

const toStatusFromCategories = (categories: ConsentCategories): 'accepted_all' | 'rejected_all' | 'customized' => {
  const allOptionalOn = categories.analytics && categories.marketing && categories.preferences;
  const allOptionalOff = !categories.analytics && !categories.marketing && !categories.preferences;
  if (allOptionalOn) return 'accepted_all';
  if (allOptionalOff) return 'rejected_all';
  return 'customized';
};

export const CookieConsentRoot = () => {
  const [consent, setConsent] = useState<ConsentPayload | null>(() => getStoredConsent());
  const [isModalOpen, setModalOpen] = useState(false);

  const shouldShowBanner = !consent;

  const initialModalCategories = useMemo<ConsentCategories>(() => {
    return consent?.categories ?? getDefaultCategories();
  }, [consent]);

  useEffect(() => {
    const current = getStoredConsent();
    if (current) {
      loadDeferredScripts(current);
    }

    const unsubscribe = subscribeToConsent((next) => {
      setConsent((previous) => {
        applyConsentSideEffects(next, previous);
        return next;
      });
    });

    const openSettingsHandler = () => setModalOpen(true);
    window.addEventListener('aurora:open-cookie-settings', openSettingsHandler);

    return () => {
      unsubscribe();
      window.removeEventListener('aurora:open-cookie-settings', openSettingsHandler);
    };
  }, []);

  useEffect(() => {
    (window as unknown as Record<string, unknown>).AuroraCookieConsent = {
      hasConsent: (category: 'analytics' | 'marketing' | 'preferences' | 'necessary') => {
        if (category === 'analytics') return canLoadAnalytics();
        if (category === 'marketing') return canLoadMarketing();
        if (category === 'preferences') return Boolean(getStoredConsent()?.categories.preferences);
        return true;
      },
      openSettings: () => setModalOpen(true),
      getConsent: () => getStoredConsent(),
    };
  }, []);

  const persistConsent = async (
    categories: ConsentCategories,
    source: 'banner' | 'settings_modal',
    forcedStatus?: 'accepted_all' | 'rejected_all' | 'customized',
  ) => {
    const status = forcedStatus ?? toStatusFromCategories(categories);
    const payload = createConsentPayload(status, categories, source);
    await saveConsent(payload);
    setModalOpen(false);
  };

  const acceptAll = async () => {
    await persistConsent(
      {
        necessary: true,
        analytics: true,
        marketing: true,
        preferences: true,
      },
      'banner',
      'accepted_all',
    );
  };

  const rejectAll = async () => {
    await persistConsent(
      {
        necessary: true,
        analytics: false,
        marketing: false,
        preferences: false,
      },
      'banner',
      'rejected_all',
    );
  };

  const savePreferences = async (categories: ConsentCategories) => {
    await persistConsent(categories, 'settings_modal');
  };

  return (
    <>
      {shouldShowBanner ? (
        <CookieBanner
          onAcceptAll={() => void acceptAll()}
          onRejectAll={() => void rejectAll()}
          onManagePreferences={() => setModalOpen(true)}
        />
      ) : null}
      <CookiePreferencesModal
        open={isModalOpen}
        initialCategories={initialModalCategories}
        onClose={() => setModalOpen(false)}
        onSave={(categories) => void savePreferences(categories)}
      />
    </>
  );
};
