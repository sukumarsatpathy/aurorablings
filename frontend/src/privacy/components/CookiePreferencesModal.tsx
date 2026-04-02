import { useEffect, useMemo, useRef, useState } from 'react';
import type { ConsentCategories } from '../consentManager';

interface CookiePreferencesModalProps {
  open: boolean;
  initialCategories: ConsentCategories;
  onClose: () => void;
  onSave: (categories: ConsentCategories) => void;
}

export const CookiePreferencesModal = ({
  open,
  initialCategories,
  onClose,
  onSave,
}: CookiePreferencesModalProps) => {
  const [draft, setDraft] = useState<ConsentCategories>(initialCategories);
  const saveButtonRef = useRef<HTMLButtonElement | null>(null);

  useEffect(() => {
    if (!open) return;
    setDraft(initialCategories);
    window.setTimeout(() => {
      saveButtonRef.current?.focus();
    }, 0);
  }, [initialCategories, open]);

  useEffect(() => {
    if (!open) return;

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        onClose();
      }
    };

    window.addEventListener('keydown', onKeyDown);
    return () => {
      window.removeEventListener('keydown', onKeyDown);
    };
  }, [onClose, open]);

  const rows = useMemo(
    () => [
      {
        key: 'necessary' as const,
        title: 'Necessary',
        description: 'Required for core site functionality and security.',
        disabled: true,
      },
      {
        key: 'analytics' as const,
        title: 'Analytics',
        description: 'Helps us understand usage trends to improve performance.',
        disabled: false,
      },
      {
        key: 'marketing' as const,
        title: 'Marketing',
        description: 'Supports personalized campaigns and ad attribution.',
        disabled: false,
      },
      {
        key: 'preferences' as const,
        title: 'Preferences',
        description: 'Stores your UI and shopping experience preferences.',
        disabled: false,
      },
    ],
    [],
  );

  const updateCategory = (key: keyof ConsentCategories, value: boolean) => {
    if (key === 'necessary') return;
    setDraft((prev) => ({
      ...prev,
      [key]: value,
    }));
  };

  if (!open) return null;

  return (
    <div className="cookie-consent-modal-backdrop" role="presentation" onClick={onClose}>
      <div
        className="cookie-consent-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="cookie-settings-title"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="cookie-consent-modal-header">
          <h2 id="cookie-settings-title">Cookie Preferences</h2>
          <button type="button" className="cookie-consent-icon-btn" onClick={onClose} aria-label="Close cookie settings">
            x
          </button>
        </div>

        <p className="cookie-consent-copy">
          Control how optional technologies are used. Necessary cookies remain enabled for security and checkout integrity.
        </p>

        <div className="cookie-consent-rows">
          {rows.map((row) => (
            <div className="cookie-consent-row" key={row.key}>
              <div className="cookie-consent-row-text">
                <h3>{row.title}</h3>
                <p>{row.description}</p>
              </div>
              <label className="cookie-toggle" aria-label={`${row.title} cookies`}>
                <input
                  type="checkbox"
                  checked={Boolean(draft[row.key])}
                  disabled={row.disabled}
                  onChange={(event) => updateCategory(row.key, event.target.checked)}
                />
                <span className="cookie-toggle-slider" aria-hidden="true" />
              </label>
            </div>
          ))}
        </div>

        <div className="cookie-consent-modal-actions">
          <button type="button" className="cookie-btn cookie-btn-muted" onClick={onClose}>
            Cancel
          </button>
          <button
            ref={saveButtonRef}
            type="button"
            className="cookie-btn cookie-btn-primary"
            onClick={() => onSave({ ...draft, necessary: true })}
          >
            Save Preferences
          </button>
        </div>
      </div>
    </div>
  );
};
