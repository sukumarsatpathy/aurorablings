import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { AlertCircle, ChevronLeft, Download, PackageCheck, Search, X } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import bulkReceiveService, {
  labelErrorMessage,
  type BulkReceiveProduct,
  type BulkReceiveWarehouse,
} from '@/services/api/bulkReceive';
import { LabelPaperPicture } from '@/components/admin/LabelPaperPicture';
import { LABEL_PAPERS, labelPaper, type LabelPaperKey } from '@/lib/labelPapers';

/** variant id → copies typed ("" = none). */
type Copies = Record<string, string>;

const norm = (v: string) => v.trim().toLowerCase();
const MAX_LABELS = 5000;

const mrp = (price?: string) => {
  const n = Number(price || 0);
  return Number.isInteger(n) ? String(n) : n.toFixed(2);
};

/**
 * Barcode labels for stock that's already in.
 *
 * Printing labels never adds stock — that's what receiving is for (and Bulk
 * Receive offers labels for each delivery as it's saved). This page is for
 * everything else: labelling the shelf the first time, reprinting a faded or
 * torn sticker, or a price change.
 *
 * The file it downloads has one row per sticker (Barcode, Name, SKU, MRP);
 * import it into the label printer app and map those columns onto the
 * template once.
 *
 * Products are grouped by their category's label paper, with one download per
 * paper: only one roll is in the printer at a time, so a file is one roll.
 */
export const PrintLabels: React.FC = () => {
  const [warehouses, setWarehouses] = useState<BulkReceiveWarehouse[]>([]);
  const [warehouseId, setWarehouseId] = useState('');
  const [catalog, setCatalog] = useState<BulkReceiveProduct[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState('');
  const [productIds, setProductIds] = useState<string[]>([]);
  const [copies, setCopies] = useState<Copies>({});
  const [search, setSearch] = useState('');
  const [searchOpen, setSearchOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [busyPaper, setBusyPaper] = useState<LabelPaperKey | null>(null);
  const [error, setError] = useState('');
  const [done, setDone] = useState('');
  const searchBoxRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bulkReceiveService
      .listWarehouses()
      .then((rows) => {
        const active = rows.filter((w) => w.is_active);
        setWarehouses(active);
        setWarehouseId((current) => current || (active.find((w) => w.is_default) || active[0])?.id || '');
        if (!active.length) setLoading(false);
      })
      .catch(() => {
        setLoadError('Could not load warehouses.');
        setLoading(false);
      });
  }, []);

  useEffect(() => {
    if (!warehouseId) return;
    let active = true;
    setLoading(true);
    bulkReceiveService
      .catalog(warehouseId)
      .then((rows) => {
        if (!active) return;
        setCatalog(rows);
        setLoadError('');
      })
      .catch(() => active && setLoadError('Could not load products. Check your connection and reload.'))
      .finally(() => active && setLoading(false));
    return () => {
      active = false;
    };
  }, [warehouseId]);

  useEffect(() => {
    const close = (e: MouseEvent) => {
      if (searchBoxRef.current && !searchBoxRef.current.contains(e.target as Node)) setSearchOpen(false);
    };
    document.addEventListener('mousedown', close);
    return () => document.removeEventListener('mousedown', close);
  }, []);

  const byId = useMemo(() => new Map(catalog.map((p) => [p.id, p])), [catalog]);
  const added = useMemo(
    () => productIds.map((id) => byId.get(id)).filter((p): p is BulkReceiveProduct => Boolean(p)),
    [productIds, byId],
  );

  const matches = useMemo(() => {
    const q = norm(search);
    if (!q) return [] as BulkReceiveProduct[];
    return catalog
      .filter((p) => !productIds.includes(p.id))
      .filter(
        (p) =>
          norm(p.name).includes(q) ||
          String(p.stock_id ?? '') === q ||
          p.variants.some((v) => norm(v.sku).includes(q) || (v.barcode || '') === q),
      )
      .slice(0, 8);
  }, [search, catalog, productIds]);

  /** Add a product, one label per piece on hand (at least one). */
  const addProduct = (product: BulkReceiveProduct) => {
    setProductIds((prev) => (prev.includes(product.id) ? prev : [...prev, product.id]));
    setCopies((prev) => {
      const next = { ...prev };
      for (const v of product.variants) {
        if (next[v.id] === undefined) next[v.id] = String(Math.max(v.on_hand, product.variants.length === 1 ? 1 : 0) || '');
      }
      return next;
    });
    setSearch('');
    setSearchOpen(false);
    setDone('');
  };

  /** Labelling the shelf for the first time: everything with stock, one per piece. */
  const addAllInStock = () => {
    const withStock = catalog.filter((p) => p.variants.some((v) => v.on_hand > 0));
    setProductIds(withStock.map((p) => p.id));
    const next: Copies = {};
    for (const p of withStock) for (const v of p.variants) next[v.id] = v.on_hand > 0 ? String(v.on_hand) : '';
    setCopies(next);
    setDone('');
  };

  const removeProduct = (product: BulkReceiveProduct) => {
    setProductIds((prev) => prev.filter((id) => id !== product.id));
    setCopies((prev) => {
      const next = { ...prev };
      for (const v of product.variants) delete next[v.id];
      return next;
    });
  };

  /** The products added, grouped by label paper, in the papers' fixed order. */
  const groups = useMemo(
    () =>
      LABEL_PAPERS.map((paper) => {
        const products = added.filter((p) => labelPaper(p.label_paper).key === paper.key);
        const items = products.flatMap((p) =>
          p.variants
            .map((v) => ({ variant_id: v.id, copies: Number(copies[v.id] || 0) }))
            .filter((i) => i.copies > 0),
        );
        return { paper, products, items, total: items.reduce((s, i) => s + i.copies, 0) };
      }).filter((g) => g.products.length > 0),
    [added, copies],
  );
  const total = groups.reduce((s, g) => s + g.total, 0);

  const download = async (paper: LabelPaperKey, format: 'xlsx' | 'csv') => {
    const group = groups.find((g) => g.paper.key === paper);
    if (!group || !group.items.length || busy) return;
    setBusy(true);
    setBusyPaper(paper);
    setError('');
    setDone('');
    try {
      const count = (await bulkReceiveService.downloadLabels(group.items, format, paper)) || group.total;
      setDone(
        `Downloaded ${count} ${group.paper.name.toLowerCase()} label${count === 1 ? '' : 's'}. ` +
          `Load the ${group.paper.size.split(' ·')[0]} roll and print it from the label printer app.`,
      );
    } catch (e) {
      setError(await labelErrorMessage(e));
    } finally {
      setBusy(false);
      setBusyPaper(null);
    }
  };

  return (
    <div className="space-y-5">
      <div>
        <Link to="/admin/inventory" className="inline-flex items-center gap-1 text-xs font-medium text-muted-foreground hover:text-primary">
          <ChevronLeft size={14} /> Inventory
        </Link>
        <h1 className="mt-1 text-2xl font-bold tracking-tight text-foreground">Barcode Labels</h1>
        <p className="mt-1 text-xs text-muted-foreground">
          Download a label sheet for the printer app: one row per label with barcode, name, SKU and MRP.
          Each category prints on its own paper (set in Categories), so there is one file per paper.
          Printing labels never changes stock — new stock is added with Receive or Bulk Receive.
        </p>
      </div>

      <div className="flex flex-col gap-3 rounded-[14px] border border-border bg-white p-4 shadow-sm md:flex-row md:items-end">
        <div className="grid gap-1.5 md:w-64">
          <label htmlFor="pl-warehouse" className="text-xs font-bold uppercase text-muted-foreground">Stock from</label>
          <select
            id="pl-warehouse"
            className="h-11 rounded-xl border border-border/60 bg-background px-3 text-sm"
            value={warehouseId}
            onChange={(e) => setWarehouseId(e.target.value)}
          >
            {warehouses.length === 0 ? <option value="">No active warehouse</option> : null}
            {warehouses.map((w) => (
              <option key={w.id} value={w.id}>{w.name} · {w.code.toUpperCase()}</option>
            ))}
          </select>
        </div>
        <div ref={searchBoxRef} className="relative flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" size={16} />
          <Input
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setSearchOpen(true);
            }}
            onFocus={() => setSearchOpen(true)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && matches[0]) {
                e.preventDefault();
                addProduct(matches[0]);
              }
              if (e.key === 'Escape') setSearchOpen(false);
            }}
            placeholder={loading ? 'Loading products…' : 'Add a product — name, SKU, stock ID or barcode…'}
            className="h-11 pl-9"
            aria-label="Add a product"
            disabled={loading || !warehouseId}
          />
          {searchOpen && search.trim() ? (
            <div className="absolute z-20 mt-2 max-h-[360px] w-full overflow-y-auto rounded-2xl border border-border bg-white p-1 shadow-lg">
              {matches.length === 0 ? (
                <p className="px-3 py-3 text-sm text-muted-foreground">No products match “{search.trim()}”.</p>
              ) : (
                matches.map((p) => (
                  <button
                    key={p.id}
                    type="button"
                    onClick={() => addProduct(p)}
                    className="flex w-full items-center gap-3 rounded-xl px-3 py-2 text-left hover:bg-muted/40"
                  >
                    {p.image ? <img src={p.image} alt="" className="h-10 w-10 rounded-md border border-border/50 object-cover" /> : <span className="h-10 w-10 rounded-md bg-muted" />}
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-sm font-semibold text-foreground">{p.name}</span>
                      <span className="block text-xs text-muted-foreground">
                        {p.stock_id ? `Stock ID ${p.stock_id} · ` : ''}{p.category}
                        {p.variants.length > 1 ? ` · ${p.variants.length} variations` : ''}
                      </span>
                    </span>
                  </button>
                ))
              )}
            </div>
          ) : null}
        </div>
        <Button
          type="button"
          variant="outline"
          className="h-11 gap-2 border-primary/40 bg-white text-primary hover:bg-primary hover:text-primary-foreground"
          onClick={addAllInStock}
          disabled={loading || !catalog.length}
          title="Add every product with stock here, one label per piece"
        >
          <PackageCheck size={16} /> Everything in stock
        </Button>
      </div>

      {loadError ? (
        <div className="flex items-center gap-2 rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700"><AlertCircle size={16} /> {loadError}</div>
      ) : null}

      {added.length === 0 && !loading ? (
        <div className="rounded-[14px] border border-dashed border-border bg-white/60 p-10 text-center text-sm text-muted-foreground">
          Search for a product above, or press <strong>Everything in stock</strong> to label the whole shelf.
        </div>
      ) : null}

      {groups.map((group) => (
        <div key={group.paper.key} className="space-y-3">
          <div className="flex flex-wrap items-center gap-4 rounded-[14px] border border-primary/20 bg-primary/5 px-4 py-3">
            <LabelPaperPicture paper={group.paper.key} className="h-14 w-auto max-w-[260px] shrink-0" />
            <div className="min-w-0 flex-1">
              <div className="font-bold text-foreground">
                {group.paper.name} <span className="font-medium text-primary">· {group.paper.size}</span>
              </div>
              <div className="text-xs text-muted-foreground">
                {group.paper.material} · {group.products.length} product{group.products.length === 1 ? '' : 's'} · {group.total} label{group.total === 1 ? '' : 's'}
              </div>
            </div>
            <Button type="button" variant="outline" size="sm" onClick={() => void download(group.paper.key, 'csv')} disabled={!group.items.length || busy || group.total > MAX_LABELS}>
              CSV
            </Button>
            <Button type="button" size="sm" onClick={() => void download(group.paper.key, 'xlsx')} disabled={!group.items.length || busy || group.total > MAX_LABELS} className="gap-1.5">
              <Download size={14} /> {busyPaper === group.paper.key ? 'Preparing…' : `Download ${group.paper.name.toLowerCase()}s`}
            </Button>
          </div>
      {group.products.map((product) => (
        <section key={product.id} className="rounded-[14px] border border-border bg-white shadow-sm" aria-label={product.name}>
          <div className="flex items-center gap-3 border-b border-border/60 px-4 py-3">
            {product.image ? <img src={product.image} alt="" className="h-10 w-10 rounded-lg border border-border/50 object-cover" /> : <span className="h-10 w-10 rounded-lg bg-muted" />}
            <div className="min-w-0 flex-1">
              <div className="truncate font-bold text-foreground">{product.name}</div>
              <div className="text-xs text-muted-foreground">{product.category}</div>
            </div>
            <button
              type="button"
              aria-label={`Remove ${product.name}`}
              onClick={() => removeProduct(product)}
              className="flex h-8 w-8 items-center justify-center rounded-lg border border-red-200 text-red-600 hover:bg-red-50"
            >
              <X size={14} />
            </button>
          </div>
          <div className="divide-y divide-border/40 px-4 py-1">
            {product.variants.map((v) => (
              <div key={v.id} className="flex flex-wrap items-center gap-3 py-2">
                {/* What the sticker will say, roughly as laid out on 40 × 15 mm. */}
                <div className="flex w-[260px] shrink-0 items-stretch gap-2 rounded-md border border-dashed border-border px-2 py-1">
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-[11px] font-semibold text-foreground">{v.label_text || v.name || v.sku}</div>
                    <div className="font-mono text-[11px] tracking-[0.2em] text-muted-foreground">{v.barcode || '—'}</div>
                  </div>
                  <div className="flex flex-col items-end justify-center text-right">
                    <span className="text-[9px] uppercase text-muted-foreground">MRP</span>
                    <span className="text-xs font-bold tabular-nums">₹{mrp(v.price)}</span>
                  </div>
                </div>
                <div className="min-w-0 flex-1 text-xs text-muted-foreground">
                  <span className="font-mono">{v.sku}</span>
                  {v.options.length ? <span> · {v.options.map((o) => o.value).join(' / ')}</span> : null}
                  <span className={v.on_hand > 0 ? '' : 'text-orange-600'}> · {v.on_hand} on hand</span>
                </div>
                <label className="flex items-center gap-2 text-xs text-muted-foreground">
                  Labels
                  <input
                    inputMode="numeric"
                    aria-label={`Labels for ${product.name} ${v.sku}`}
                    value={copies[v.id] ?? ''}
                    placeholder="0"
                    onChange={(e) => setCopies((prev) => ({ ...prev, [v.id]: e.target.value.replace(/\D/g, '').slice(0, 4) }))}
                    onFocus={(e) => e.target.select()}
                    className="h-9 w-20 rounded-lg border border-border/70 text-center text-sm font-semibold text-foreground"
                  />
                </label>
              </div>
            ))}
          </div>
        </section>
      ))}
        </div>
      ))}

      <div className="sticky bottom-0 z-30 -mx-6 border-t border-border bg-white/95 px-6 py-3 shadow-[0_-8px_24px_rgba(0,0,0,0.05)] backdrop-blur md:-mx-8 md:px-8">
        <div className="flex flex-wrap items-center gap-3">
          <span className="text-lg font-bold text-foreground">{total} label{total === 1 ? '' : 's'}</span>
          <span className="text-sm text-muted-foreground">
            {groups.map((g) => `${g.total} ${g.paper.name.toLowerCase()}`).join(' · ')}
          </span>
          {groups.some((g) => g.total > MAX_LABELS) ? (
            <span className="text-sm text-red-600">Up to {MAX_LABELS} per file — print in smaller batches.</span>
          ) : null}
          {error ? <span className="flex items-center gap-1.5 text-sm text-red-600"><AlertCircle size={15} /> {error}</span> : null}
          {done ? <span className="text-sm text-emerald-700">{done}</span> : null}
          <span className="ml-auto hidden text-xs text-muted-foreground md:inline">One file per paper — download each, then print it with that roll loaded.</span>
        </div>
      </div>
    </div>
  );
};

export default PrintLabels;
