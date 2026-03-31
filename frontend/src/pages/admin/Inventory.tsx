import React, { useEffect, useMemo, useState } from 'react';
import { useLocation } from 'react-router-dom';
import { Search, Plus, Edit, Trash2, PackagePlus, Shuffle, SlidersHorizontal, AlertCircle } from 'lucide-react';
import { DataTable, StatusBadge } from '@/components/admin/AdminTable';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Input } from '@/components/ui/Input';
import { Modal, ModalContent, ModalFooter, ModalHeader, ModalTitle } from '@/components/ui/Modal';
import inventoryService from '@/services/api/inventory';
import type { InventoryStockRecord, InventoryVariantOption, Warehouse, WarehouseType } from '@/types/inventory';

type StockFilter = '' | 'in' | 'low' | 'out';
type Ops = 'receive' | 'adjust' | 'transfer';

const WH_TYPES: WarehouseType[] = ['warehouse', 'store', 'virtual'];

export const Inventory: React.FC = () => {
  const location = useLocation();
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [status, setStatus] = useState<StockFilter>('');
  const [warehouseFilter, setWarehouseFilter] = useState('');
  const [stocks, setStocks] = useState<InventoryStockRecord[]>([]);
  const [warehouses, setWarehouses] = useState<Warehouse[]>([]);
  const [variants, setVariants] = useState<InventoryVariantOption[]>([]);

  const [warehouseOpen, setWarehouseOpen] = useState(false);
  const [warehouseDeleteOpen, setWarehouseDeleteOpen] = useState(false);
  const [warehouseEditing, setWarehouseEditing] = useState<Warehouse | null>(null);
  const [warehouseDeleteTarget, setWarehouseDeleteTarget] = useState<Warehouse | null>(null);
  const [warehouseForm, setWarehouseForm] = useState({ name: '', code: '', type: 'warehouse' as WarehouseType, address: '', is_active: true, is_default: false });

  const [opsOpen, setOpsOpen] = useState(false);
  const [opsMode, setOpsMode] = useState<Ops>('receive');
  const [opsVariantSearch, setOpsVariantSearch] = useState('');
  const [opsForm, setOpsForm] = useState({
    variant_id: '',
    warehouse_id: '',
    quantity: 1,
    quantity_delta: 0,
    reason: '',
    reference_id: '',
    notes: '',
    from_warehouse_id: '',
    to_warehouse_id: '',
  });

  const [thresholdOpen, setThresholdOpen] = useState(false);
  const [thresholdRecord, setThresholdRecord] = useState<InventoryStockRecord | null>(null);
  const [thresholdValue, setThresholdValue] = useState(0);

  const loadWarehouses = async () => {
    const response = await inventoryService.listWarehouses({ include_inactive: true });
    setWarehouses(Array.isArray(response.data) ? response.data : []);
  };

  const loadVariants = async () => {
    const response = await inventoryService.listVariants();
    setVariants(Array.isArray(response.data) ? response.data : []);
  };

  const loadStocks = async () => {
    setLoading(true);
    try {
      const response = await inventoryService.listStock({
        search: search || undefined,
        warehouse_id: warehouseFilter || undefined,
        status: status || undefined,
      });
      setStocks(Array.isArray(response.data) ? response.data : []);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    Promise.all([loadWarehouses(), loadVariants()]).catch(() => undefined);
  }, []);

  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const querySearch = params.get('search') || '';
    if (querySearch) {
      setSearch(querySearch);
    }
  }, [location.search]);

  useEffect(() => {
    const t = setTimeout(() => loadStocks().catch(() => undefined), 250);
    return () => clearTimeout(t);
  }, [search, status, warehouseFilter]);

  const summary = useMemo(() => ({
    low: stocks.filter((s) => s.available > 0 && s.available <= s.low_stock_threshold).length,
    out: stocks.filter((s) => s.available <= 0).length,
    total: stocks.length,
  }), [stocks]);

  const openWarehouseModal = (warehouse?: Warehouse) => {
    if (warehouse) {
      setWarehouseEditing(warehouse);
      setWarehouseForm({
        name: warehouse.name,
        code: warehouse.code,
        type: warehouse.type,
        address: warehouse.address || '',
        is_active: warehouse.is_active,
        is_default: warehouse.is_default,
      });
    } else {
      setWarehouseEditing(null);
      setWarehouseForm({ name: '', code: '', type: 'warehouse', address: '', is_active: true, is_default: false });
    }
    setWarehouseOpen(true);
  };

  const saveWarehouse = async () => {
    if (!warehouseForm.name.trim() || !warehouseForm.code.trim()) return alert('Name and code are required.');
    if (warehouseEditing) await inventoryService.updateWarehouse(warehouseEditing.id, warehouseForm);
    else await inventoryService.createWarehouse(warehouseForm);
    setWarehouseOpen(false);
    await Promise.all([loadWarehouses(), loadStocks()]);
  };

  const deleteWarehouse = async () => {
    if (!warehouseDeleteTarget) return;
    await inventoryService.deleteWarehouse(warehouseDeleteTarget.id);
    setWarehouseDeleteOpen(false);
    setWarehouseDeleteTarget(null);
    await Promise.all([loadWarehouses(), loadStocks()]);
  };

  const openOps = (mode: Ops) => {
    setOpsMode(mode);
    setOpsVariantSearch('');
    setOpsForm({ variant_id: '', warehouse_id: '', quantity: 1, quantity_delta: 0, reason: '', reference_id: '', notes: '', from_warehouse_id: '', to_warehouse_id: '' });
    setOpsOpen(true);
  };

  const submitOps = async () => {
    if (opsMode === 'receive') await inventoryService.receiveStock({ variant_id: opsForm.variant_id, warehouse_id: opsForm.warehouse_id, quantity: opsForm.quantity, notes: opsForm.notes, reference_id: opsForm.reference_id });
    if (opsMode === 'adjust') await inventoryService.adjustStock({ variant_id: opsForm.variant_id, warehouse_id: opsForm.warehouse_id, quantity_delta: opsForm.quantity_delta, reason: opsForm.reason });
    if (opsMode === 'transfer') await inventoryService.transferStock({ variant_id: opsForm.variant_id, from_warehouse_id: opsForm.from_warehouse_id, to_warehouse_id: opsForm.to_warehouse_id, quantity: opsForm.quantity, notes: opsForm.notes });
    setOpsOpen(false);
    await loadStocks();
  };

  const openThreshold = (record: InventoryStockRecord) => {
    setThresholdRecord(record);
    setThresholdValue(record.low_stock_threshold);
    setThresholdOpen(true);
  };

  const saveThreshold = async () => {
    if (!thresholdRecord) return;
    await inventoryService.updateStockThreshold(thresholdRecord.id, thresholdValue);
    setThresholdOpen(false);
    setThresholdRecord(null);
    await loadStocks();
  };

  const columns = [
    { header: 'SKU', accessorKey: 'sku', className: 'text-xs text-muted-foreground font-mono' },
    { header: 'Product / Variant', accessorKey: 'product_name', cell: (i: InventoryStockRecord) => <div><div className="font-bold">{i.product_name}</div><div className="text-[10px] text-muted-foreground">{i.variant_name || i.sku}</div></div> },
    { header: 'Warehouse', accessorKey: 'warehouse_name', cell: (i: InventoryStockRecord) => <div><div className="font-semibold">{i.warehouse_name}</div><div className="text-[10px] uppercase text-muted-foreground">{i.warehouse_code}</div></div> },
    { header: 'On Hand', accessorKey: 'on_hand', align: 'right' as const },
    { header: 'Reserved', accessorKey: 'reserved', align: 'right' as const, className: 'text-xs text-muted-foreground' },
    { header: 'Available', accessorKey: 'available', align: 'right' as const, cell: (i: InventoryStockRecord) => <span className={i.available <= 0 ? 'text-destructive font-bold' : i.is_low_stock ? 'text-[#b08850] font-bold' : 'font-semibold'}>{i.available}</span> },
    { header: 'Threshold', accessorKey: 'low_stock_threshold', align: 'right' as const, cell: (i: InventoryStockRecord) => <button onClick={() => openThreshold(i)} className="text-xs underline underline-offset-2">{i.low_stock_threshold}</button> },
    { header: 'Status', accessorKey: 'status', align: 'right' as const, cell: (i: InventoryStockRecord) => <StatusBadge status={i.available <= 0 ? 'Out of Stock' : i.is_low_stock ? 'Low Stock' : 'In Stock'} /> },
  ];

  const filteredOpsVariants = useMemo(() => {
    const q = opsVariantSearch.trim().toLowerCase();
    if (!q) return variants;
    return variants.filter((v) => {
      const sku = String(v.sku || '').toLowerCase();
      const product = String(v.product_name || '').toLowerCase();
      const variant = String(v.name || '').toLowerCase();
      return sku.includes(q) || product.includes(q) || variant.includes(q);
    });
  }, [variants, opsVariantSearch]);

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-foreground">Inventory</h1>
          <p className="text-xs text-muted-foreground mt-1">Stock records, warehouses and movement operations.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" className="h-10 gap-2 border-primary/40 bg-white text-primary hover:bg-primary hover:text-primary-foreground" onClick={() => openOps('receive')}><PackagePlus size={15} /> Receive</Button>
          <Button variant="outline" className="h-10 gap-2 border-primary/40 bg-white text-primary hover:bg-primary hover:text-primary-foreground" onClick={() => openOps('adjust')}><SlidersHorizontal size={15} /> Adjust</Button>
          <Button variant="outline" className="h-10 gap-2 border-primary/40 bg-white text-primary hover:bg-primary hover:text-primary-foreground" onClick={() => openOps('transfer')}><Shuffle size={15} /> Transfer</Button>
          <Button className="h-10 gap-2" onClick={() => openWarehouseModal()}><Plus size={15} /> Add Warehouse</Button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card className="p-4 rounded-[14px] bg-[#fdfaf5] border-[#f4e8d3] flex items-center gap-4"><div className="w-10 h-10 rounded-full bg-[#f4e8d3] flex items-center justify-center text-[#c8a97e]"><AlertCircle size={20} /></div><div><div className="text-xs font-bold text-[#b08850] uppercase tracking-wider">Low Stock Alerts</div><div className="text-xl font-bold text-[#8a6532]">{summary.low}</div></div></Card>
        <Card className="p-4 rounded-[14px] bg-white border-border shadow-sm"><div className="text-xs font-bold uppercase tracking-wider text-muted-foreground">Out of Stock</div><div className="text-xl font-bold text-destructive mt-1">{summary.out}</div></Card>
        <Card className="p-4 rounded-[14px] bg-white border-border shadow-sm"><div className="text-xs font-bold uppercase tracking-wider text-muted-foreground">Tracked Records</div><div className="text-xl font-bold text-foreground mt-1">{summary.total}</div></Card>
      </div>

      <div className="bg-white p-4 rounded-[14px] border border-border shadow-sm flex flex-col lg:flex-row gap-4">
        <div className="relative flex-1"><Search className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" size={16} /><Input placeholder="Search by SKU, variant, or product..." value={search} onChange={(e) => setSearch(e.target.value)} className="pl-9 h-10 shadow-none border-border/60 bg-muted/20" /></div>
        <select className="h-10 min-w-[180px] rounded-xl border border-border/60 bg-background px-3 text-sm" value={warehouseFilter} onChange={(e) => setWarehouseFilter(e.target.value)}><option value="">All Warehouses</option>{warehouses.map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}</select>
        <select className="h-10 min-w-[150px] rounded-xl border border-border/60 bg-background px-3 text-sm" value={status} onChange={(e) => setStatus(e.target.value as StockFilter)}><option value="">All Status</option><option value="in">In Stock</option><option value="low">Low Stock</option><option value="out">Out of Stock</option></select>
      </div>

      {loading ? <div className="text-center py-10 text-muted-foreground text-xs uppercase tracking-widest animate-pulse">Loading inventory...</div> : <DataTable data={stocks} columns={columns} />}

      <div className="bg-white rounded-[14px] border border-border shadow-sm p-4 space-y-2">
        <h3 className="text-sm font-bold uppercase tracking-wider text-muted-foreground">Warehouses</h3>
        {warehouses.map((w) => (
          <div key={w.id} className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 rounded-xl border border-border/70 px-3 py-2">
            <div><div className="font-semibold text-sm">{w.name} {w.is_default && <span className="text-[10px] text-primary ml-1">DEFAULT</span>} {!w.is_active && <span className="text-[10px] text-destructive ml-1">INACTIVE</span>}</div><div className="text-xs text-muted-foreground">{w.code} • {w.type}</div></div>
            <div className="flex gap-2">
              <Button variant="outline" size="sm" className="rounded-xl border-primary/40 bg-white text-primary hover:bg-primary hover:text-primary-foreground" onClick={() => openWarehouseModal(w)}><Edit size={13} className="mr-1" /> Edit</Button>
              <Button variant="outline" size="sm" className="rounded-xl border-red-300 bg-white text-red-600 hover:bg-red-600 hover:text-white" onClick={() => { setWarehouseDeleteTarget(w); setWarehouseDeleteOpen(true); }}><Trash2 size={13} className="mr-1" /> Delete</Button>
            </div>
          </div>
        ))}
      </div>

      <Modal open={warehouseOpen} onOpenChange={setWarehouseOpen}><ModalContent className="max-w-xl"><ModalHeader><ModalTitle>{warehouseEditing ? 'Edit Warehouse' : 'Add Warehouse'}</ModalTitle></ModalHeader><div className="grid grid-cols-1 md:grid-cols-2 gap-4 py-4"><div className="grid gap-2"><label className="text-xs font-bold uppercase text-muted-foreground">Name</label><Input value={warehouseForm.name} onChange={(e) => setWarehouseForm({ ...warehouseForm, name: e.target.value })} /></div><div className="grid gap-2"><label className="text-xs font-bold uppercase text-muted-foreground">Code</label><Input value={warehouseForm.code} onChange={(e) => setWarehouseForm({ ...warehouseForm, code: e.target.value })} /></div><div className="grid gap-2"><label className="text-xs font-bold uppercase text-muted-foreground">Type</label><select className="h-11 rounded-xl border border-border/60 bg-background px-3 text-sm" value={warehouseForm.type} onChange={(e) => setWarehouseForm({ ...warehouseForm, type: e.target.value as WarehouseType })}>{WH_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}</select></div><div className="grid gap-2"><label className="text-xs font-bold uppercase text-muted-foreground">Active</label><select className="h-11 rounded-xl border border-border/60 bg-background px-3 text-sm" value={warehouseForm.is_active ? 'yes' : 'no'} onChange={(e) => setWarehouseForm({ ...warehouseForm, is_active: e.target.value === 'yes' })}><option value="yes">Yes</option><option value="no">No</option></select></div><div className="grid gap-2 md:col-span-2"><label className="text-xs font-bold uppercase text-muted-foreground">Address</label><textarea rows={3} className="w-full rounded-xl border border-border/60 bg-background px-4 py-2 text-sm" value={warehouseForm.address} onChange={(e) => setWarehouseForm({ ...warehouseForm, address: e.target.value })} /></div><label className="md:col-span-2 flex items-center gap-2 text-sm"><input type="checkbox" checked={warehouseForm.is_default} onChange={(e) => setWarehouseForm({ ...warehouseForm, is_default: e.target.checked })} />Set as default</label></div><ModalFooter><Button variant="outline" onClick={() => setWarehouseOpen(false)} className="rounded-xl border-primary/40 bg-white text-primary hover:bg-primary hover:text-primary-foreground">Cancel</Button><Button variant="outline" onClick={saveWarehouse} className="rounded-xl border-primary/40 bg-white text-primary hover:bg-primary hover:text-primary-foreground">{warehouseEditing ? 'Update Warehouse' : 'Create Warehouse'}</Button></ModalFooter></ModalContent></Modal>

      <Modal open={warehouseDeleteOpen} onOpenChange={setWarehouseDeleteOpen}><ModalContent className="max-w-md"><ModalHeader><ModalTitle>Delete Warehouse</ModalTitle></ModalHeader><div className="space-y-2 py-2"><p className="text-sm text-muted-foreground">Are you sure you want to delete this warehouse?</p>{warehouseDeleteTarget && <div className="rounded-xl border border-border bg-muted/30 p-3 text-sm"><div className="font-semibold">{warehouseDeleteTarget.name}</div><div className="text-xs text-muted-foreground">{warehouseDeleteTarget.code}</div></div>}</div><ModalFooter><Button variant="outline" onClick={() => setWarehouseDeleteOpen(false)} className="rounded-xl border-primary/40 bg-white text-primary hover:bg-primary hover:text-primary-foreground">Cancel</Button><Button variant="outline" onClick={deleteWarehouse} className="rounded-xl border-red-300 bg-white text-red-600 hover:bg-red-600 hover:text-white">Confirm Delete</Button></ModalFooter></ModalContent></Modal>

      <Modal open={opsOpen} onOpenChange={setOpsOpen}><ModalContent className="max-w-2xl"><ModalHeader><ModalTitle>{opsMode === 'receive' ? 'Receive Stock' : opsMode === 'adjust' ? 'Adjust Stock' : 'Transfer Stock'}</ModalTitle></ModalHeader><div className="grid grid-cols-1 md:grid-cols-2 gap-4 py-4"><div className="grid gap-2 md:col-span-2"><label className="text-xs font-bold uppercase text-muted-foreground">Search Variant</label><Input placeholder="Search by SKU, product or variant..." value={opsVariantSearch} onChange={(e) => setOpsVariantSearch(e.target.value)} /></div><div className="grid gap-2 md:col-span-2"><label className="text-xs font-bold uppercase text-muted-foreground">Variant</label><select className="h-11 rounded-xl border border-border/60 bg-background px-3 text-sm" value={opsForm.variant_id} onChange={(e) => setOpsForm({ ...opsForm, variant_id: e.target.value })}><option value="">Select variant</option>{filteredOpsVariants.map((v) => <option key={v.id} value={v.id}>{v.sku} • {v.product_name}{v.name ? ` • ${v.name}` : ''}</option>)}</select></div>{opsMode !== 'transfer' && <div className="grid gap-2"><label className="text-xs font-bold uppercase text-muted-foreground">Warehouse</label><select className="h-11 rounded-xl border border-border/60 bg-background px-3 text-sm" value={opsForm.warehouse_id} onChange={(e) => setOpsForm({ ...opsForm, warehouse_id: e.target.value })}><option value="">Select warehouse</option>{warehouses.filter((w) => w.is_active).map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}</select></div>}{opsMode === 'transfer' && <div className="grid gap-2"><label className="text-xs font-bold uppercase text-muted-foreground">From</label><select className="h-11 rounded-xl border border-border/60 bg-background px-3 text-sm" value={opsForm.from_warehouse_id} onChange={(e) => setOpsForm({ ...opsForm, from_warehouse_id: e.target.value })}><option value="">Select source</option>{warehouses.filter((w) => w.is_active).map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}</select></div>}{opsMode === 'transfer' && <div className="grid gap-2"><label className="text-xs font-bold uppercase text-muted-foreground">To</label><select className="h-11 rounded-xl border border-border/60 bg-background px-3 text-sm" value={opsForm.to_warehouse_id} onChange={(e) => setOpsForm({ ...opsForm, to_warehouse_id: e.target.value })}><option value="">Select destination</option>{warehouses.filter((w) => w.is_active).map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}</select></div>}<div className="grid gap-2"><label className="text-xs font-bold uppercase text-muted-foreground">{opsMode === 'adjust' ? 'Quantity Delta (+/-)' : 'Quantity'}</label><Input type="number" value={opsMode === 'adjust' ? opsForm.quantity_delta : opsForm.quantity} onChange={(e) => setOpsForm({ ...opsForm, [opsMode === 'adjust' ? 'quantity_delta' : 'quantity']: Number(e.target.value || 0) })} /></div>{opsMode === 'adjust' && <div className="grid gap-2"><label className="text-xs font-bold uppercase text-muted-foreground">Reason</label><Input value={opsForm.reason} onChange={(e) => setOpsForm({ ...opsForm, reason: e.target.value })} /></div>}{opsMode === 'receive' && <div className="grid gap-2"><label className="text-xs font-bold uppercase text-muted-foreground">Reference</label><Input value={opsForm.reference_id} onChange={(e) => setOpsForm({ ...opsForm, reference_id: e.target.value })} /></div>}<div className="grid gap-2 md:col-span-2"><label className="text-xs font-bold uppercase text-muted-foreground">Notes</label><Input value={opsForm.notes} onChange={(e) => setOpsForm({ ...opsForm, notes: e.target.value })} /></div></div><ModalFooter><Button variant="outline" onClick={() => setOpsOpen(false)} className="rounded-xl border-primary/40 bg-white text-primary hover:bg-primary hover:text-primary-foreground">Cancel</Button><Button variant="outline" onClick={submitOps} className="rounded-xl border-primary/40 bg-white text-primary hover:bg-primary hover:text-primary-foreground">Apply</Button></ModalFooter></ModalContent></Modal>

      <Modal open={thresholdOpen} onOpenChange={setThresholdOpen}><ModalContent className="max-w-md"><ModalHeader><ModalTitle>Update Low Stock Threshold</ModalTitle></ModalHeader><div className="space-y-3 py-2">{thresholdRecord && <div className="rounded-xl border border-border bg-muted/30 p-3 text-sm"><div className="font-semibold">{thresholdRecord.sku}</div><div className="text-xs text-muted-foreground">{thresholdRecord.product_name}</div></div>}<div className="grid gap-2"><label className="text-xs font-bold uppercase text-muted-foreground">Threshold</label><Input type="number" min={0} value={thresholdValue} onChange={(e) => setThresholdValue(Number(e.target.value || 0))} /></div></div><ModalFooter><Button variant="outline" onClick={() => setThresholdOpen(false)} className="rounded-xl border-primary/40 bg-white text-primary hover:bg-primary hover:text-primary-foreground">Cancel</Button><Button variant="outline" onClick={saveThreshold} className="rounded-xl border-primary/40 bg-white text-primary hover:bg-primary hover:text-primary-foreground">Update</Button></ModalFooter></ModalContent></Modal>
    </div>
  );
};
