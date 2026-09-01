import { useCallback, useMemo, useState } from 'react';

import type { CatalogueRow } from '@/services/api/pos';

export interface CartEntry {
  row: CatalogueRow;
  quantity: number;
}

/**
 * The cart, held in memory for the length of one sale.
 *
 * Deliberately not persisted: a half-built cart restored from yesterday, priced
 * at yesterday's prices, against stock that has since sold online, is worse than
 * an empty one. The sale becomes durable at the moment an order is created on
 * the server, which is also the moment stock is reserved.
 *
 * The totals here are for display while the customer is still deciding. Nothing
 * computed in this file is ever sent to the server or used to take money.
 */
export function usePosCart() {
  const [entries, setEntries] = useState<CartEntry[]>([]);

  const add = useCallback((row: CatalogueRow) => {
    setEntries((current) => {
      const existing = current.find((e) => e.row.variant_id === row.variant_id);
      if (!existing) return [...current, { row, quantity: 1 }];

      // Never let the till put more in the basket than the shelf holds. The
      // server checks again at order creation — this is only to stop staff
      // promising a piece that isn't there.
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
          const capped =
            e.row.track_inventory ? Math.min(quantity, e.row.stock) : quantity;
          return { ...e, quantity: capped };
        })
        .filter((e) => e.quantity > 0),
    );
  }, []);

  const remove = useCallback((variantId: string) => {
    setEntries((current) => current.filter((e) => e.row.variant_id !== variantId));
  }, []);

  const clear = useCallback(() => setEntries([]), []);

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
    add,
    setQuantity,
    remove,
    clear,
  };
}
