import { useEffect, useMemo, useRef, useState } from 'react';

import posService, { type CatalogueRow } from '@/services/api/pos';

interface Props {
  onAdd: (row: CatalogueRow) => void;
  inCart: Record<string, number>;
  /**
   * Enter in the search box. A scanner aimed at the till while this box has
   * focus types the code here and presses Enter, so this is where most scans
   * arrive. Resolves true when the code matched something (added or refused
   * for stock), false when it matched nothing.
   */
  onScanCode?: (code: string) => Promise<boolean>;
  /** Opens the phone-camera scanner. The button is hidden when not given. */
  onOpenCamera?: () => void;
}

/** A label barcode at the end of whatever was already in the box. */
const TRAILING_BARCODE = /(\d{8})$/;

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
export function CatalogueGrid({ onAdd, inCart, onScanCode, onOpenCamera }: Props) {
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
      <div className="flex shrink-0 gap-2 border-b border-border p-3 md:p-4">
        <input
          ref={searchRef}
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={async (e) => {
            if (e.key !== 'Enter' || !onScanCode) return;
            // Read the box, not state: a scanner types faster than renders.
            const text = e.currentTarget.value.trim();
            if (!text) return;
            e.preventDefault();
            // The scanner types after whatever is already in the box, so
            // "ring10000123" is someone who searched, then scanned: look up
            // just the trailing barcode.
            const tail = text.match(TRAILING_BARCODE)?.[1];
            const code = tail && /\D/.test(text.slice(0, -8)) ? tail : text;
            const matched = await onScanCode(code);
            if (matched) setQuery('');
            searchRef.current?.focus();
          }}
          placeholder="Scan a barcode, or search name, SKU or stock ID…"
          // 16px on phones: iPhone Safari zooms the whole page into any
          // smaller text box on tap, which throws the counter off screen.
          className="min-w-0 flex-1 rounded-lg border border-border bg-background px-3 py-2 text-base outline-none focus:border-primary md:text-sm"
          aria-label="Search catalogue"
          enterKeyHint="search"
          autoComplete="off"
        />
        {onOpenCamera && (
          <button
            type="button"
            onClick={onOpenCamera}
            className="flex shrink-0 items-center gap-1.5 rounded-lg border border-border bg-card px-3 text-sm font-semibold text-foreground hover:border-primary"
            aria-label="Scan with camera"
            title="Scan a barcode with this device's camera"
          >
            <svg aria-hidden="true" viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
              <path d="M3 7V5a2 2 0 0 1 2-2h2M17 3h2a2 2 0 0 1 2 2v2M21 17v2a2 2 0 0 1-2 2h-2M7 21H5a2 2 0 0 1-2-2v-2" />
              <path d="M7 8v8M10 8v8M13 8v8M16 8v8" />
            </svg>
            <span className="hidden sm:inline">Camera</span>
          </button>
        )}
      </div>

      <div className="grid min-h-0 flex-1 auto-rows-min grid-cols-[repeat(auto-fill,minmax(140px,1fr))] gap-3 overflow-y-auto p-3 md:p-4">
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
              {/*
                Staff pick by sight, not by SKU. A jewellery stall carries forty
                variations of the same shape, and a text-only grid makes someone
                read every line to find the pair the customer is holding.

                Fixed aspect box so a missing image doesn't reflow the grid —
                tiles must not move under a finger that is already reaching for
                one. loading="lazy" keeps a long scroll cheap on 4G.
              */}
              <span className="mb-1 block aspect-square w-full overflow-hidden rounded-md bg-muted">
                {row.image ? (
                  <img
                    src={row.image}
                    alt=""
                    loading="lazy"
                    className="h-full w-full object-cover"
                  />
                ) : (
                  <span className="flex h-full w-full items-center justify-center text-[10px] text-muted-foreground">
                    no image
                  </span>
                )}
              </span>
              <span className="flex items-center gap-1.5 font-mono text-[10px] text-muted-foreground">
                <span>{row.sku}</span>
                {row.stock_id != null && (
                  <span className="rounded bg-muted px-1 py-0.5 font-semibold text-foreground/70">
                    #{row.stock_id}
                  </span>
                )}
              </span>
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
