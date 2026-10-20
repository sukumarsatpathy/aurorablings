interface CookieBannerProps {
  onAcceptAll: () => void;
  onRejectAll: () => void;
  onManagePreferences: () => void;
}

export const CookieBanner = ({
  onAcceptAll,
  onRejectAll,
  onManagePreferences,
}: CookieBannerProps) => {
  return (
    <aside className="cookie-consent-banner" aria-live="polite" aria-label="Cookie consent banner">
      <div className="cookie-consent-content">
        <h2>We Respect Your Privacy</h2>
        <p>
          <span className="cookie-copy-full">
            Aurora Blings uses cookies to run essential services and, with your permission, improve analytics and personalized marketing.
          </span>
          <span className="cookie-copy-short">
            We use cookies to run the shop and, if you allow, for analytics and marketing.
          </span>
        </p>
      </div>
      <div className="cookie-consent-actions">
        <button type="button" className="cookie-btn cookie-btn-outline" onClick={onManagePreferences}>
          <span className="cookie-copy-full">Manage Preferences</span>
          <span className="cookie-copy-short">Settings</span>
        </button>
        <button type="button" className="cookie-btn cookie-btn-primary" onClick={onAcceptAll}>
          Accept All
        </button>
        <button type="button" className="cookie-btn cookie-btn-muted" onClick={onRejectAll}>
          Reject All
        </button>
      </div>
    </aside>
  );
};
