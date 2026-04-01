import React, { useEffect, useMemo, useRef, useState } from 'react';
import styles from './ColorPicker.module.css';

const PRESET_COLORS = [
  '#FFFFFF', '#F8FAFC', '#E2E8F0', '#CBD5E1', '#94A3B8', '#475569', '#1E293B', '#0F172A',
  '#FEE2E2', '#FCA5A5', '#F87171', '#EF4444', '#DC2626', '#B91C1C', '#7F1D1D', '#450A0A',
  '#FEF3C7', '#FCD34D', '#F59E0B', '#D97706', '#B45309', '#92400E', '#78350F', '#451A03',
  '#DCFCE7', '#86EFAC', '#4ADE80', '#22C55E', '#16A34A', '#15803D', '#166534', '#052E16',
  '#DBEAFE', '#93C5FD', '#60A5FA', '#3B82F6', '#2563EB', '#1D4ED8', '#1E40AF', '#172554',
  '#F3E8FF', '#D8B4FE', '#C084FC', '#A855F7', '#9333EA', '#7E22CE', '#6B21A8', '#3B0764',
];

const normalizeHex = (input, fallback = '#1A1A1A') => {
  const value = String(input || '').trim().toUpperCase();
  const clean = value.startsWith('#') ? value.slice(1) : value;
  if (/^[0-9A-F]{3}$/.test(clean)) {
    return `#${clean.split('').map((c) => `${c}${c}`).join('')}`;
  }
  if (/^[0-9A-F]{6}$/.test(clean)) {
    return `#${clean}`;
  }
  return fallback;
};

const ColorPicker = ({ value, onChange }) => {
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState(normalizeHex(value || '#1A1A1A'));
  const rootRef = useRef(null);

  const safeValue = useMemo(() => normalizeHex(value || draft || '#1A1A1A'), [value, draft]);

  useEffect(() => {
    if (!open) return undefined;
    const handleOutside = (event) => {
      if (!rootRef.current) return;
      if (!rootRef.current.contains(event.target)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', handleOutside);
    return () => document.removeEventListener('mousedown', handleOutside);
  }, [open]);

  const apply = (hex) => {
    const normalized = normalizeHex(hex, safeValue);
    setDraft(normalized);
    onChange(normalized);
  };

  const onDraftChange = (next) => {
    setDraft(next.toUpperCase());
    if (/^#?[0-9A-Fa-f]{3}$/.test(next) || /^#?[0-9A-Fa-f]{6}$/.test(next)) {
      apply(next);
    }
  };

  return (
    <div className={styles.root} ref={rootRef}>
      <div className={styles.triggerRow}>
        <button
          type="button"
          className={styles.swatchButton}
          style={{ backgroundColor: safeValue }}
          onClick={() => setOpen((prev) => !prev)}
          aria-label="Open color palette"
        />
        <input
          type="text"
          value={draft}
          onChange={(e) => onDraftChange(e.target.value)}
          onBlur={() => apply(draft)}
          className={styles.hexInput}
          placeholder="#1A1A1A"
        />
      </div>

      {open && (
        <div className={styles.popover}>
          <div className={styles.popoverHeader}>
            <span className={styles.popoverTitle}>Pick Color (HEX)</span>
            <button
              type="button"
              className={styles.closeButton}
              onClick={() => setOpen(false)}
              aria-label="Close color palette"
            >
              x
            </button>
          </div>
          <div className={styles.presets}>
            {PRESET_COLORS.map((hex) => (
              <button
                key={hex}
                type="button"
                className={`${styles.preset} ${normalizeHex(hex) === safeValue ? styles.activePreset : ''}`}
                style={{ backgroundColor: hex }}
                onClick={() => apply(hex)}
                title={hex}
              />
            ))}
          </div>
          <div className={styles.help}>Tip: Enter HEX directly like `#F5F0EB`.</div>
        </div>
      )}
    </div>
  );
};

export default ColorPicker;
