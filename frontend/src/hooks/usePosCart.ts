import { useCallback, useEffect, useMemo, useState } from 'react';

import posService, { type CatalogueRow } from '@/services/api/pos';

export interface CartEntry {
  row: CatalogueRow;
  quantity: number;
}

const STORAGE_KEY = 'pos_cart_v1';
/** A cart older than this is yesterday's, not an interrupted sale. */
const MAX_AGE_MS = 4 * 60 * 60 * 1000;

interface Stored {
  savedAt: number;
  lines: Array<{ variant_id: string; quantity: number }>;
}

/**
 * The cart for one sale.
 *
 * It survives a refresh, because at a counter a reload is rarely deliberate — a
 * tablet sleeps, a browser is swiped away, someone's thumb finds the wrong
 * corner — and losing a built-up basket in front of a customer is unacceptable.
 *
 * What is *not* restored is any figure. Only variant ids and quantities are kept
 * in the browser; price and stock are re-read from the server on restore, and
 * quantities are capped to whatever is actually on the shelf now. A line whose
 * product has since been deactivated or sold out is dropped and reported, rather
 * than quietly sold at yesterday's price.
 *
 * The store is per-tab (sessionStorage): two tills open on one tablet should not
 * share a basket.
 */
export function usePosCart() {
  const [entries, setEntries] = useState<CartEntry[]>([]);
  const [restoring, setRestoring] = useState(true);
  const [restoreNote, setRestoreNote] = useState('');

  // ── restore ───────────────────────────────────────────────
  useEffect(() => {
    let active = true;

    (async () => {
      try {
        const raw = sessionStorage.getItem(STORAGE_KEY);
        if (!raw) return;

        const stored: Stored = JSON.parse(raw);
        if (!stored?.lines?.length || Date.now() - stored.savedAt > MAX_AGE_MS) {
          sessionStorage.removeItem(STORAGE_KEY);
          return;
        }

        const rows = await posService.catalogueByIds(stored.lines.map((l) => l.variant_id));
        if (!active) return;

        const rebuilt: CartEntry[] = [];
        let dropped = 0;
        let reduced = 0;

        for (const line of stored.lines) {
          const row = rows.find((r) => r.variant_id === line.variant_id);
          if (!row) {
            dropped += 1;
            continue;
          }
          const capped = row.track_inventory ? Math.min(line.quantity, row.stock) : line.quantity;
          if (capped <= 0) {
            dropped += 1;
            continue;
          }
          if (capped < line.quantity) reduced += 1;
          rebuilt.push({ row, quantity: capped });
        }

        setEntries(rebuilt);
        if (dropped || reduced) {
          setRestoreNote(
            [
              dropped ? `${dropped} item${dropped > 1 ? 's' : ''} no longer available` : '',
              reduced ? `${reduced} reduced to available stock` : '',
            ]
              .filter(Boolean)
              .join(' · '),
          );
        }
      } catch {
        sessionStorage.removeItem(STORAGE_KEY);
      } finally {
        if (active) setRestoring(false);
      }
    })();

    return () => {
      active = false;
    };
  }, []);

  // ── persist ───────────────────────────────────────────────
  useEffect(() => {
    if (restoring) return;
    try {
      if (!entries.length) {
        sessionStorage.removeItem(STORAGE_KEY);
        return;
      }
      const payload: Stored = {
        savedAt: Date.now(),
        lines: entries.map((e) => ({ variant_id: e.row.variant_id, quantity: e.quantity })),
      };
      sessionStorage.setItem(STORAGE_KEY, JSON.stringify(payload));
    } catch {
      // A full or blocked store must never break a sale.
    }
  }, [entries, restoring]);

  const add = useCallback((row: CatalogueRow) => {
    setEntries((current) => {
      const existing = current.find((e) => e.row.variant_id === row.variant_id);
      if (!existing) return [...current, { row, quantity: 1 }];
      if (row.track_inventory && existing.quantity >= row.stock) return current;
      return current.map((e) =>
        e.row.variant_id === row.variant_id ? { ...e, quantity: e.quantity + 1 } : e,
      );
    });
  }, []);

  const setQuantity = useCallback((variantId: string, quantity: number) => {
    setEntries((current) =>
      current
        .map((e) => {
          if (e.row.variant_id !== variantId) return e;
          const capped = e.row.track_inventory ? Math.min(quantity, e.row.stock) : quantity;
          return { ...e, quantity: capped };
        })
        .filter((e) => e.quantity > 0),
    );
  }, []);

  const remove = useCallback((variantId: string) => {
    setEntries((current) => current.filter((e) => e.row.variant_id !== variantId));
  }, []);

  const clear = useCallback(() => {
    setEntries([]);
    setRestoreNote('');
    try {
      sessionStorage.removeItem(STORAGE_KEY);
    } catch {
      /* ignore */
    }
  }, []);

  const itemCount = useMemo(
    () => entries.reduce((total, e) => total + e.quantity, 0),
    [entries],
  );

  /** Indicative only — the server prices the sale. */
  const indicativeSubtotal = useMemo(
    () => entries.reduce((total, e) => total + Number(e.row.price) * e.quantity, 0),
    [entries],
  );

  const lines = useMemo(
    () => entries.map((e) => ({ variant_id: e.row.variant_id, quantity: e.quantity })),
    [entries],
  );

  return {
    entries,
    lines,
    itemCount,
    indicativeSubtotal,
    restoring,
    restoreNote,
    dismissRestoreNote: () => setRestoreNote(''),
    add,
    setQuantity,
    remove,
    clear,
  };
}
