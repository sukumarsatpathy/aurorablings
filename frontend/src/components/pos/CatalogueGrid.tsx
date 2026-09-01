import { useEffect, useMemo, useRef, useState } from 'react';

import posService, { type CatalogueRow } from '@/services/api/pos';

interface Props {
  onAdd: (row: CatalogueRow) => void;
  inCart: Record<string, number>;
}

const money = (value: string | number) =>
  `₹${Number(value).toLocaleString('en-IN', { maximumFractionDigits: 0 })}`;

/**
 * Search and tap to add.
 *
 * Speed is the product here: the box is focused on mount, results come as you
 * type, and adding is one tap with no dialog to dismiss. A two-item sale should
 * take under thirty seconds from empty cart to paid, and this is where most of
 * that budget is either spent or saved.
 */
export function CatalogueGrid({ onAdd, inCart }: Props) {
  const [query, setQuery] = useState('');
  const [rows, setRows] = useState<CatalogueRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const searchRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    searchRef.current?.focus();
  }, []);

  useEffect(() => {
    let active = true;
    // Debounced: a stall on 4G should not fire a request per keystroke.
    const timer = window.setTimeout(async () => {
      setLoading(true);
      try {
        const results = await posService.catalogue(query);
        if (active) {
          setRows(results);
          setError('');
        }
      } catch {
        if (active) setError('Could not load the catalogue.');
      } finally {
        if (active) setLoading(false);
      }
    }, query ? 200 : 0);

    return () => {
      active = false;
      window.clearTimeout(timer);
    };
  }, [query]);

  const empty = useMemo(() => !loading && rows.length === 0, [loading, rows]);

  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-border p-4">
        <input
          ref={searchRef}
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search name or SKU…"
          className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none focus:border-primary"
          aria-label="Search catalogue"
        />
      </div>

      <div className="grid flex-1 auto-rows-min grid-cols-[repeat(auto-fill,minmax(150px,1fr))] gap-3 overflow-y-auto p-4">
        {rows.map((row) => {
          const taken = inCart[row.variant_id] || 0;
          const left = row.track_inventory ? row.stock - taken : Infinity;
          const soldOut = left <= 0;

          return (
            <button
              key={row.variant_id}
              type="button"
              disabled={soldOut}
              onClick={() => onAdd(row)}
              className="flex flex-col gap-1 rounded-lg border border-border bg-card p-3 text-left transition hover:border-primary disabled:cursor-not-allowed disabled:opacity-45"
            >
              <span className="font-mono text-[10px] text-muted-foreground">{row.sku}</span>
              <span className="text-sm font-semibold leading-tight">{row.product_name}</span>
              {row.variant_name && (
                <span className="text-xs text-muted-foreground">{row.variant_name}</span>
              )}
              <span className="mt-auto flex items-baseline justify-between pt-2">
                <span className="text-sm font-bold tabular-nums">{money(row.price)}</span>
                <span
                  className={
                    soldOut
                      ? 'rounded-full bg-destructive/10 px-2 py-0.5 text-[10px] font-semibold text-destructive'
                      : left <= 2
                        ? 'rounded-full bg-amber-500/10 px-2 py-0.5 text-[10px] font-semibold text-amber-600'
                        : 'rounded-full bg-emerald-500/10 px-2 py-0.5 text-[10px] font-semibold text-emerald-700'
                  }
                >
                  {!row.track_inventory
                    ? 'untracked'
                    : soldOut
                      ? 'out of stock'
                      : `${left} in stock`}
                </span>
              </span>
            </button>
          );
        })}

        {loading && rows.length === 0 && (
          <p className="col-span-full p-10 text-center text-sm text-muted-foreground">Loading…</p>
        )}
        {empty && (
          <p className="col-span-full p-10 text-center text-sm text-muted-foreground">
            {query ? `Nothing matches “${query}”.` : 'No active products found.'}
          </p>
        )}
        {error && <p className="col-span-full p-4 text-center text-sm text-destructive">{error}</p>}
      </div>
    </div>
  );
}
