import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { AlertCircle, Check, ChevronLeft, Download, FileUp, Search, Tag, X } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import bulkReceiveService, {
  labelErrorMessage,
  type BulkReceiveProduct,
  type BulkReceiveVariant,
  type BulkReceiveWarehouse,
} from '@/services/api/bulkReceive';
import { isColourName, swatchColour } from '@/lib/variantOptions';
import { parseStockCsv } from '@/lib/stockCsv';
import { LABEL_PAPERS, labelPaper, type LabelPaperKey } from '@/lib/labelPapers';

/** variant id → what's typed in its box ("" = nothing). */
type Quantities = Record<string, string>;

interface GridLayout {
  kind: 'grid';
  rowName: string;
  colName: string;
  rows: Array<{ label: string; hex?: string; swatch: boolean }>;
  cols: string[];
  cell: (row: string, col: string) => BulkReceiveVariant | undefined;
}
interface ListLayout {
  kind: 'list';
  rows: Array<{ label: string; hex?: string; swatch: boolean; variant: BulkReceiveVariant }>;
}
interface SingleLayout {
  kind: 'single';
  variant: BulkReceiveVariant;
}
type Layout = GridLayout | ListLayout | SingleLayout;

const norm = (v: string) => v.trim().toLowerCase();

/**
 * How a product's boxes are laid out:
 * two options (Color × Size) → grid, colour down the side;
 * one option → a list; none, or more than two → one box per variant.
 */
function layoutFor(product: BulkReceiveProduct): Layout {
  const variants = product.variants;
  if (variants.length === 1 && variants[0].options.length === 0) return { kind: 'single', variant: variants[0] };

  const used = new Map<string, Map<string, string | undefined>>();
  for (const v of variants) {
    for (const o of v.options) {
      const values = used.get(o.attribute) || new Map<string, string | undefined>();
      if (!values.has(norm(o.value))) values.set(norm(o.value), o.value);
      used.set(o.attribute, values);
    }
  }
  const attrMeta = (name: string) => product.attributes.find((a) => norm(a.name) === norm(name));
  const isSwatch = (name: string) => attrMeta(name)?.show_swatches ?? isColourName(name);
  const orderedValues = (name: string) => {
    const meta = attrMeta(name);
    const present = used.get(name) || new Map();
    const fromMeta = (meta?.values || []).filter((v) => present.has(norm(v.value)));
    const rest = Array.from(present.values()).filter((v) => !fromMeta.some((m) => norm(m.value) === norm(v || '')));
    return [
      ...fromMeta.map((v) => ({ label: v.value, hex: v.hex_code })),
      ...rest.map((v) => ({ label: v || '', hex: undefined as string | undefined })),
    ];
  };
  const names = Array.from(used.keys()).sort((a, b) => Number(isSwatch(b)) - Number(isSwatch(a)));

  if (names.length === 2) {
    const [rowName, colName] = names;
    const index = new Map<string, BulkReceiveVariant>();
    for (const v of variants) {
      const r = v.options.find((o) => o.attribute === rowName)?.value;
      const c = v.options.find((o) => o.attribute === colName)?.value;
      if (r && c) index.set(`${norm(r)}||${norm(c)}`, v);
    }
    return {
      kind: 'grid',
      rowName,
      colName,
      rows: orderedValues(rowName).map((v) => ({ ...v, swatch: isSwatch(rowName) })),
      cols: orderedValues(colName).map((v) => v.label),
      cell: (row, col) => index.get(`${norm(row)}||${norm(col)}`),
    };
  }

  if (names.length === 1) {
    const [name] = names;
    const byValue = new Map(variants.map((v) => [norm(v.options[0]?.value || v.sku), v]));
    const ordered = orderedValues(name)
      .map((v) => ({ ...v, swatch: isSwatch(name), variant: byValue.get(norm(v.label)) }))
      .filter((r): r is { label: string; hex: string | undefined; swatch: boolean; variant: BulkReceiveVariant } => Boolean(r.variant));
    return { kind: 'list', rows: ordered };
  }

  return {
    kind: 'list',
    rows: variants.map((v) => ({
      label: v.options.length ? v.options.map((o) => o.value).join(' / ') : v.name || v.sku,
      hex: undefined,
      swatch: false,
      variant: v,
    })),
  };
}

const QtyBox: React.FC<{
  variant: BulkReceiveVariant;
  value: string;
  onChange: (value: string) => void;
  label: string;
}> = ({ variant, value, onChange, label }) => {
  const filled = Boolean(value && Number(value) > 0);
  return (
    <div
      className={`relative h-10 rounded-xl border bg-white transition-colors ${
        filled ? 'border-primary bg-primary/5 ring-1 ring-inset ring-primary' : 'border-border/70 focus-within:border-primary/60'
      }`}
    >
      <input
        inputMode="numeric"
        pattern="[0-9]*"
        aria-label={`Quantity for ${label}`}
        value={value}
        placeholder="0"
        onChange={(e) => onChange(e.target.value.replace(/\D/g, '').slice(0, 6))}
        onFocus={(e) => e.target.select()}
        className="h-full w-full rounded-xl bg-transparent pr-12 pl-3 text-center text-[15px] font-semibold text-foreground outline-none placeholder:font-normal placeholder:text-muted-foreground/40"
      />
      <span
        className={`pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 text-[10.5px] ${
          variant.on_hand <= 0 ? 'text-orange-600' : 'text-muted-foreground/70'
        }`}
        title="Current stock in this warehouse"
      >
        now {variant.on_hand}
      </span>
    </div>
  );
};

const Dot: React.FC<{ label: string; hex?: string }> = ({ label, hex }) => {
  const colour = swatchColour(label, hex);
  if (!colour) return null;
  return <span aria-hidden="true" className="inline-block h-3.5 w-3.5 shrink-0 rounded-full border border-black/15" style={{ background: colour }} />;
};

export const BulkReceive: React.FC = () => {
  const navigate = useNavigate();
  const [warehouses, setWarehouses] = useState<BulkReceiveWarehouse[]>([]);
  const [warehouseId, setWarehouseId] = useState('');
  const [reference, setReference] = useState('');
  const [notes, setNotes] = useState('');
  const [catalog, setCatalog] = useState<BulkReceiveProduct[]>([]);
  const [loadingCatalog, setLoadingCatalog] = useState(true);
  const [loadError, setLoadError] = useState('');
  const [productIds, setProductIds] = useState<string[]>([]);
  const [quantities, setQuantities] = useState<Quantities>({});
  const [fillValues, setFillValues] = useState<Record<string, string>>({});
  const [search, setSearch] = useState('');
  const [searchOpen, setSearchOpen] = useState(false);
  const [csvReport, setCsvReport] = useState<null | {
    file: string;
    matched: number;
    pieces: number;
    unknown: string[];
    problems: Array<{ line: number; reason: string }>;
  }>(null);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState('');
  const [saved, setSaved] = useState<null | {
    message: string;
    /** What was received, by label paper: one label download per roll. */
    labels: Array<{ paper: LabelPaperKey; items: Array<{ variant_id: string; copies: number }>; count: number }>;
  }>(null);
  const [labelBusy, setLabelBusy] = useState<LabelPaperKey | null>(null);
  const [labelError, setLabelError] = useState('');
  const fileRef = useRef<HTMLInputElement>(null);
  const searchBoxRef = useRef<HTMLDivElement>(null);
  const topRef = useRef<HTMLDivElement>(null);

  // Warehouses: default one preselected.
  useEffect(() => {
    bulkReceiveService
      .listWarehouses()
      .then((rows) => {
        const active = rows.filter((w) => w.is_active);
        setWarehouses(active);
        setWarehouseId((current) => current || (active.find((w) => w.is_default) || active[0])?.id || '');
        if (!active.length) setLoadingCatalog(false);
      })
      .catch(() => {
        setLoadError('Could not load warehouses.');
        setLoadingCatalog(false);
      });
  }, []);

  // Products (with stock in the chosen warehouse). Typed quantities are kept when switching.
  const loadCatalog = useCallback(async (id: string) => {
    if (!id) return;
    setLoadingCatalog(true);
    try {
      setCatalog(await bulkReceiveService.catalog(id));
      setLoadError('');
    } catch {
      setLoadError('Could not load products. Check your connection and reload.');
    } finally {
      setLoadingCatalog(false);
    }
  }, []);

  useEffect(() => {
    void loadCatalog(warehouseId);
  }, [warehouseId, loadCatalog]);

  const byId = useMemo(() => new Map(catalog.map((p) => [p.id, p])), [catalog]);
  const bySku = useMemo(() => {
    const map = new Map<string, { product: BulkReceiveProduct; variant: BulkReceiveVariant }>();
    for (const product of catalog) for (const variant of product.variants) map.set(norm(variant.sku), { product, variant });
    return map;
  }, [catalog]);
  const added = useMemo(() => productIds.map((id) => byId.get(id)).filter((p): p is BulkReceiveProduct => Boolean(p)), [productIds, byId]);

  const matches = useMemo(() => {
    const q = norm(search);
    if (!q) return [] as BulkReceiveProduct[];
    return catalog
      .filter((p) => !productIds.includes(p.id))
      .filter(
        (p) =>
          norm(p.name).includes(q) ||
          String(p.stock_id ?? '') === q ||
          p.variants.some((v) => norm(v.sku).includes(q)),
      )
      .slice(0, 8);
  }, [search, catalog, productIds]);

  useEffect(() => {
    const close = (e: MouseEvent) => {
      if (searchBoxRef.current && !searchBoxRef.current.contains(e.target as Node)) setSearchOpen(false);
    };
    document.addEventListener('mousedown', close);
    return () => document.removeEventListener('mousedown', close);
  }, []);

  const lines = useMemo(
    () =>
      added.flatMap((p) =>
        p.variants
          .map((v) => ({ product: p, variant: v, quantity: Number(quantities[v.id] || 0) }))
          .filter((l) => l.quantity > 0),
      ),
    [added, quantities],
  );
  const totalPieces = lines.reduce((sum, l) => sum + l.quantity, 0);
  const productsWithLines = new Set(lines.map((l) => l.product.id)).size;
  const hasUnsaved = totalPieces > 0;

  useEffect(() => {
    if (!hasUnsaved) return undefined;
    const warn = (e: BeforeUnloadEvent) => {
      e.preventDefault();
      e.returnValue = '';
    };
    window.addEventListener('beforeunload', warn);
    return () => window.removeEventListener('beforeunload', warn);
  }, [hasUnsaved]);

  const addProduct = (id: string) => {
    setProductIds((prev) => (prev.includes(id) ? prev : [...prev, id]));
    setSearch('');
    setSearchOpen(false);
    setSaved(null);
  };

  const removeProduct = (product: BulkReceiveProduct) => {
    setProductIds((prev) => prev.filter((id) => id !== product.id));
    setQuantities((prev) => {
      const next = { ...prev };
      for (const v of product.variants) delete next[v.id];
      return next;
    });
  };

  const setQty = (variantId: string, value: string) => {
    setSaved(null);
    setQuantities((prev) => ({ ...prev, [variantId]: value }));
  };

  const fillEmpty = (product: BulkReceiveProduct) => {
    const value = (fillValues[product.id] || '').replace(/\D/g, '');
    if (!value || Number(value) <= 0) return;
    setQuantities((prev) => {
      const next = { ...prev };
      for (const v of product.variants) if (!next[v.id]) next[v.id] = value;
      return next;
    });
  };

  const clearProduct = (product: BulkReceiveProduct) => {
    setQuantities((prev) => {
      const next = { ...prev };
      for (const v of product.variants) delete next[v.id];
      return next;
    });
  };

  const onCsv = async (file: File | undefined) => {
    if (!file) return;
    const text = await file.text();
    const parsed = parseStockCsv(text);
    const unknown: string[] = [];
    const sums = new Map<string, number>();
    const newProducts: string[] = [];
    for (const line of parsed.lines) {
      const hit = bySku.get(norm(line.sku));
      if (!hit) {
        if (!unknown.includes(line.sku)) unknown.push(line.sku);
        continue;
      }
      sums.set(hit.variant.id, (sums.get(hit.variant.id) || 0) + line.quantity);
      if (!newProducts.includes(hit.product.id)) newProducts.push(hit.product.id);
    }
    setProductIds((prev) => [...prev, ...newProducts.filter((id) => !prev.includes(id))]);
    setQuantities((prev) => {
      const next = { ...prev };
      sums.forEach((qty, id) => {
        next[id] = String(qty);
      });
      return next;
    });
    setCsvReport({
      file: file.name,
      matched: sums.size,
      pieces: Array.from(sums.values()).reduce((a, b) => a + b, 0),
      unknown,
      problems: parsed.problems.map((p) => ({ line: p.line, reason: p.reason })),
    });
    setSaved(null);
    if (fileRef.current) fileRef.current.value = '';
  };

  const downloadSample = () => {
    const examples = catalog.flatMap((p) => p.variants).slice(0, 3);
    const body = ['sku,quantity', ...(examples.length ? examples.map((v, i) => `${v.sku},${i + 2}`) : ['YOUR-SKU-1,5', 'YOUR-SKU-2,3'])].join('\n');
    const url = URL.createObjectURL(new Blob([body + '\n'], { type: 'text/csv' }));
    const a = document.createElement('a');
    a.href = url;
    a.download = 'bulk-receive-sample.csv';
    a.click();
    URL.revokeObjectURL(url);
  };

  const submit = async () => {
    if (!warehouseId || !lines.length || saving) return;
    setSaving(true);
    setSaveError('');
    try {
      const result = await bulkReceiveService.receive({
        warehouse_id: warehouseId,
        reference_id: reference.trim(),
        notes: notes.trim(),
        items: lines.map((l) => ({ variant_id: l.variant.id, quantity: l.quantity })),
      });
      const r = result.data;
      setSaved({
        message:
          result.message ||
          `Received ${r.total_quantity} pieces across ${r.variants} items.`,
        labels: LABEL_PAPERS.map((paper) => {
          const items = lines
            .filter((l) => labelPaper(l.product.label_paper).key === paper.key)
            .map((l) => ({ variant_id: l.variant.id, copies: l.quantity }));
          return { paper: paper.key, items, count: items.reduce((n, i) => n + i.copies, 0) };
        }).filter((g) => g.items.length > 0),
      });
      setLabelError('');
      setQuantities({});
      setProductIds([]);
      setCsvReport(null);
      setReference('');
      setNotes('');
      await loadCatalog(warehouseId);
      topRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    } catch (error: unknown) {
      const data = (error as { response?: { data?: { message?: string; errors?: unknown } } })?.response?.data;
      setSaveError(data?.message || 'Could not save. Nothing was received — please try again.');
    } finally {
      setSaving(false);
    }
  };

  const warehouse = warehouses.find((w) => w.id === warehouseId);

  return (
    <div ref={topRef} className="space-y-5">
      <div>
        <Link to="/admin/inventory" className="inline-flex items-center gap-1 text-xs font-medium text-muted-foreground hover:text-primary">
          <ChevronLeft size={14} /> Inventory
        </Link>
        <h1 className="mt-1 text-2xl font-bold tracking-tight text-foreground">Bulk Receive</h1>
        <p className="mt-1 text-xs text-muted-foreground">
          Record a whole delivery in one go. Nothing is saved until you press <strong>Receive stock</strong>.
        </p>
      </div>

      {saved ? (
        <div role="status" className="flex items-center gap-3 rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
          <Check size={18} className="shrink-0" />
          <span className="flex-1">
            {saved.message}
            {labelError ? <span className="mt-1 block text-red-700">{labelError}</span> : null}
          </span>
          {/*
            Stock is already in; these only print labels for it, one per piece
            received. One button per label paper (from each product's
            category), because each file is printed with its own roll loaded.
          */}
          {saved.labels.map((group) => {
            const paper = labelPaper(group.paper);
            return (
              <Button
                key={group.paper}
                type="button"
                size="sm"
                className="gap-1.5"
                disabled={labelBusy !== null}
                title={`${paper.size} · ${paper.material}`}
                onClick={async () => {
                  setLabelBusy(group.paper);
                  setLabelError('');
                  try {
                    await bulkReceiveService.downloadLabels(group.items, 'xls', group.paper);
                  } catch (error) {
                    setLabelError(await labelErrorMessage(error));
                  } finally {
                    setLabelBusy(null);
                  }
                }}
              >
                <Tag size={14} /> {labelBusy === group.paper ? 'Preparing…' : `${paper.name}s (${group.count})`}
              </Button>
            );
          })}
          <Link to="/admin/inventory" className="font-semibold underline">Back to Inventory</Link>
        </div>
      ) : null}

      <div className="grid gap-4 rounded-[14px] border border-border bg-white p-4 shadow-sm md:grid-cols-[1.1fr_1fr_1.6fr]">
        <div className="grid gap-1.5">
          <label htmlFor="br-warehouse" className="text-xs font-bold uppercase text-muted-foreground">Warehouse</label>
          <select
            id="br-warehouse"
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
        <div className="grid gap-1.5">
          <label htmlFor="br-ref" className="text-xs font-bold uppercase text-muted-foreground">Reference (optional)</label>
          <Input id="br-ref" value={reference} onChange={(e) => setReference(e.target.value)} placeholder="e.g. Bill #AB-2291" maxLength={100} />
        </div>
        <div className="grid gap-1.5">
          <label htmlFor="br-notes" className="text-xs font-bold uppercase text-muted-foreground">Notes (optional)</label>
          <Input id="br-notes" value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="e.g. Diwali restock from Jaipur supplier" maxLength={500} />
        </div>
      </div>

      <div className="flex flex-col gap-3 md:flex-row">
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
                addProduct(matches[0].id);
              }
              if (e.key === 'Escape') setSearchOpen(false);
            }}
            placeholder={loadingCatalog ? 'Loading products…' : 'Add a product — search by name, SKU or Stock ID…'}
            className="h-11 pl-9"
            aria-label="Add a product"
            disabled={loadingCatalog || !warehouseId}
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
                    onClick={() => addProduct(p.id)}
                    className="flex w-full items-center gap-3 rounded-xl px-3 py-2 text-left hover:bg-muted/40"
                  >
                    {p.image ? <img src={p.image} alt="" className="h-10 w-10 rounded-md border border-border/50 object-cover" /> : <span className="h-10 w-10 rounded-md bg-muted" />}
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-sm font-semibold text-foreground">{p.name}</span>
                      <span className="block text-xs text-muted-foreground">
                        {p.stock_id ? `Stock ID ${p.stock_id} · ` : ''}{p.category}{p.variants.length > 1 ? ` · ${p.variants.length} variations` : ''}
                        {!p.is_active ? ' · Draft' : ''}
                      </span>
                    </span>
                  </button>
                ))
              )}
            </div>
          ) : null}
        </div>
        <input ref={fileRef} type="file" accept=".csv,.tsv,.txt,text/csv" className="hidden" onChange={(e) => void onCsv(e.target.files?.[0])} />
        <Button type="button" variant="outline" className="h-11 gap-2 border-primary/40 bg-white text-primary hover:bg-primary hover:text-primary-foreground" onClick={() => fileRef.current?.click()} disabled={loadingCatalog || !warehouseId}>
          <FileUp size={16} /> Upload CSV (SKU, qty)
        </Button>
        <Button type="button" variant="ghost" className="h-11 gap-2 text-muted-foreground" onClick={downloadSample} disabled={loadingCatalog}>
          <Download size={16} /> Sample CSV
        </Button>
      </div>

      {loadError ? (
        <div className="flex items-center gap-2 rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700"><AlertCircle size={16} /> {loadError}</div>
      ) : null}

      {csvReport ? (
        <div className={`rounded-2xl border px-4 py-3 text-sm ${csvReport.unknown.length || csvReport.problems.length ? 'border-amber-200 bg-amber-50 text-amber-900' : 'border-emerald-200 bg-emerald-50 text-emerald-800'}`}>
          <div className="flex items-start gap-3">
            <div className="flex-1">
              <p>
                <strong>{csvReport.file}</strong>: filled {csvReport.matched} item{csvReport.matched === 1 ? '' : 's'} ({csvReport.pieces} pieces). Check the boxes below, then press Receive stock.
              </p>
              {csvReport.unknown.length ? (
                <p className="mt-1">
                  Skipped {csvReport.unknown.length} unknown SKU{csvReport.unknown.length === 1 ? '' : 's'}: {csvReport.unknown.slice(0, 12).join(', ')}
                  {csvReport.unknown.length > 12 ? ` and ${csvReport.unknown.length - 12} more` : ''}
                </p>
              ) : null}
              {csvReport.problems.length ? (
                <p className="mt-1">
                  Skipped {csvReport.problems.length} line{csvReport.problems.length === 1 ? '' : 's'}:{' '}
                  {csvReport.problems.slice(0, 6).map((p) => `line ${p.line} (${p.reason})`).join('; ')}
                  {csvReport.problems.length > 6 ? '…' : ''}
                </p>
              ) : null}
            </div>
            <button type="button" aria-label="Dismiss" onClick={() => setCsvReport(null)} className="rounded p-1 hover:bg-black/5"><X size={14} /></button>
          </div>
        </div>
      ) : null}

      {added.length === 0 && !loadingCatalog ? (
        <div className="rounded-[14px] border border-dashed border-border bg-white/60 p-10 text-center text-sm text-muted-foreground">
          Search for a product above, or upload a CSV with <span className="font-mono">sku,quantity</span> columns.
        </div>
      ) : null}

      {added.map((product) => {
        const layout = layoutFor(product);
        const productPieces = product.variants.reduce((s, v) => s + Number(quantities[v.id] || 0), 0);
        return (
          <section key={product.id} className="rounded-[14px] border border-border bg-white shadow-sm" aria-label={product.name}>
            <div className="flex flex-wrap items-center gap-3 border-b border-border/60 px-4 py-3">
              {product.image ? <img src={product.image} alt="" className="h-12 w-12 rounded-lg border border-border/50 object-cover" /> : <span className="h-12 w-12 rounded-lg bg-muted" />}
              <div className="min-w-0">
                <div className="truncate font-bold text-foreground">{product.name}</div>
                <div className="text-xs text-muted-foreground">
                  {product.stock_id ? `Stock ID ${product.stock_id} · ` : ''}{product.category}
                  {product.variants.length > 1 ? ` · ${product.variants.length} variations` : ' · no variations'}
                  {!product.is_active ? ' · Draft' : ''}
                </div>
              </div>
              {productPieces > 0 ? <span className="rounded-full bg-primary/10 px-2.5 py-1 text-xs font-semibold text-primary">{productPieces} pieces</span> : null}
              <div className="ml-auto flex items-center gap-2">
                {layout.kind !== 'single' ? (
                  <>
                    <span className="hidden text-xs text-muted-foreground sm:inline">Fill empty boxes with</span>
                    <input
                      inputMode="numeric"
                      aria-label={`Fill empty boxes of ${product.name} with`}
                      value={fillValues[product.id] || ''}
                      onChange={(e) => setFillValues((prev) => ({ ...prev, [product.id]: e.target.value.replace(/\D/g, '').slice(0, 5) }))}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') fillEmpty(product);
                      }}
                      placeholder="2"
                      className="h-8 w-14 rounded-lg border border-border/70 text-center text-sm"
                    />
                    <Button type="button" variant="outline" size="sm" className="h-8" onClick={() => fillEmpty(product)}>Fill</Button>
                    <Button type="button" variant="ghost" size="sm" className="h-8 text-muted-foreground" onClick={() => clearProduct(product)}>Clear</Button>
                  </>
                ) : null}
                <button type="button" aria-label={`Remove ${product.name}`} onClick={() => removeProduct(product)} className="flex h-8 w-8 items-center justify-center rounded-lg border border-red-200 text-red-600 hover:bg-red-50">
                  <X size={14} />
                </button>
              </div>
            </div>

            {layout.kind === 'single' ? (
              <div className="flex items-center gap-4 px-4 py-4">
                <span className="w-20 text-sm text-muted-foreground">Quantity</span>
                <div className="w-32"><QtyBox variant={layout.variant} value={quantities[layout.variant.id] || ''} onChange={(v) => setQty(layout.variant.id, v)} label={product.name} /></div>
                <span className="font-mono text-xs text-muted-foreground">{layout.variant.sku}</span>
              </div>
            ) : null}

            {layout.kind === 'list' ? (
              <div className="divide-y divide-border/40 px-4 py-2">
                {layout.rows.map((row) => (
                  <div key={row.variant.id} className="flex items-center gap-3 py-1.5">
                    <div className="flex min-w-0 flex-1 items-center gap-2.5 text-sm">
                      {row.swatch ? <Dot label={row.label} hex={row.hex} /> : null}
                      <span className="truncate">{row.label}</span>
                      <span className="hidden font-mono text-[11px] text-muted-foreground sm:inline">{row.variant.sku}</span>
                    </div>
                    <div className="w-32"><QtyBox variant={row.variant} value={quantities[row.variant.id] || ''} onChange={(v) => setQty(row.variant.id, v)} label={`${product.name} ${row.label}`} /></div>
                  </div>
                ))}
              </div>
            ) : null}

            {layout.kind === 'grid' ? (
              <div className="overflow-x-auto px-4 pb-4 pt-1">
                <table className="w-full border-separate border-spacing-x-1.5 border-spacing-y-1">
                  <thead>
                    <tr className="text-[11px] font-bold uppercase tracking-wider text-muted-foreground">
                      <th className="py-2 text-left font-bold">{layout.rowName} \ {layout.colName}</th>
                      {layout.cols.map((c) => <th key={c} className="min-w-[110px] py-2 text-center font-bold">{c}</th>)}
                      <th className="w-16 py-2 text-center font-bold">Total</th>
                    </tr>
                  </thead>
                  <tbody>
                    {layout.rows.map((row) => {
                      const rowTotal = layout.cols.reduce((s, c) => {
                        const v = layout.cell(row.label, c);
                        return s + (v ? Number(quantities[v.id] || 0) : 0);
                      }, 0);
                      return (
                        <tr key={row.label}>
                          <th scope="row" className="whitespace-nowrap pr-3 text-left text-sm font-medium text-foreground">
                            <span className="inline-flex items-center gap-2.5">{row.swatch ? <Dot label={row.label} hex={row.hex} /> : null}{row.label}</span>
                          </th>
                          {layout.cols.map((c) => {
                            const v = layout.cell(row.label, c);
                            return (
                              <td key={c}>
                                {v ? (
                                  <QtyBox variant={v} value={quantities[v.id] || ''} onChange={(val) => setQty(v.id, val)} label={`${product.name} ${row.label} ${c}`} />
                                ) : (
                                  <div className="flex h-10 items-center justify-center rounded-xl border border-dashed border-border/70 bg-[repeating-linear-gradient(135deg,#f6f7f4,#f6f7f4_6px,#eef1ea_6px,#eef1ea_12px)] text-xs text-muted-foreground/70">
                                    Not made
                                  </div>
                                )}
                              </td>
                            );
                          })}
                          <td className="text-center text-sm font-bold text-primary">{rowTotal || '–'}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                  <tfoot>
                    <tr>
                      <th className="pt-2 text-left text-sm font-semibold text-muted-foreground">Total</th>
                      {layout.cols.map((c) => (
                        <td key={c} className="pt-2 text-center text-sm font-bold text-primary">
                          {layout.rows.reduce((s, r) => {
                            const v = layout.cell(r.label, c);
                            return s + (v ? Number(quantities[v.id] || 0) : 0);
                          }, 0) || '–'}
                        </td>
                      ))}
                      <td className="pt-2 text-center text-sm font-bold text-primary">{productPieces || '–'}</td>
                    </tr>
                  </tfoot>
                </table>
                <p className="mt-2 text-xs text-muted-foreground">
                  “now 1” = current stock in {warehouse?.name || 'this warehouse'}. <span className="text-orange-600">Orange</span> = out of stock. Tab moves to the next box.
                </p>
              </div>
            ) : null}
          </section>
        );
      })}

      {/* Sticks to the bottom of the admin content area while scrolling. */}
      <div className="sticky bottom-0 z-30 -mx-6 border-t border-border bg-white/95 px-6 py-3 shadow-[0_-8px_24px_rgba(0,0,0,0.05)] backdrop-blur md:-mx-8 md:px-8">
        <div className="flex flex-wrap items-center gap-3">
          <div>
            <span className="text-lg font-bold text-foreground">{totalPieces} pieces</span>
            <span className="ml-2 text-sm text-muted-foreground">
              across {productsWithLines} product{productsWithLines === 1 ? '' : 's'} · {lines.length} item{lines.length === 1 ? '' : 's'}
            </span>
          </div>
          {saveError ? <span className="flex items-center gap-1.5 text-sm text-red-600"><AlertCircle size={15} /> {saveError}</span> : null}
          <span className="ml-auto hidden text-xs text-muted-foreground lg:inline">Saved together — if any line fails, nothing is saved.</span>
          <Button
            type="button"
            variant="outline"
            onClick={() => {
              if (!hasUnsaved || window.confirm('Leave without saving? The quantities you typed will be lost.')) navigate('/admin/inventory');
            }}
          >
            Cancel
          </Button>
          <Button type="button" onClick={() => void submit()} disabled={!lines.length || !warehouseId || saving} className="gap-2">
            <Check size={16} /> {saving ? 'Saving…' : 'Receive stock'}
          </Button>
        </div>
      </div>
    </div>
  );
};

export default BulkReceive;
