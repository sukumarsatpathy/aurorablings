import React, { useEffect, useMemo, useState } from 'react';
import { DataTable, StatusBadge } from '@/components/admin/AdminTable';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Search, CheckCircle, XCircle, Eye, Trash2, Plus } from 'lucide-react';
import {
  Modal,
  ModalContent,
  ModalHeader,
  ModalTitle,
  ModalFooter,
} from '@/components/ui/Modal';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';
import returnsService, {
  type ExchangeRequestRow,
  type ReturnRequestRow,
} from '@/services/api/returns';
import ordersService, { type AdminOrderDetail, type AdminOrderListRow } from '@/services/api/orders';
import inventoryService from '@/services/api/inventory';

const extractRows = (payload: any): any[] => {
  if (Array.isArray(payload?.data)) return payload.data;
  if (Array.isArray(payload?.data?.results)) return payload.data.results;
  if (Array.isArray(payload?.results)) return payload.results;
  if (Array.isArray(payload)) return payload;
  return [];
};

const toTitle = (value: string) => value.replace(/_/g, ' ').replace(/\b\w/g, (m) => m.toUpperCase());
const reasons = [
  'defective', 'damaged_transit', 'wrong_item', 'not_as_described', 'changed_mind',
  'size_issue', 'quality_issue', 'duplicate_order', 'late_delivery', 'other',
];

type Tab = 'returns' | 'exchanges';

export const Returns: React.FC = () => {
  const [tab, setTab] = useState<Tab>('returns');
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [returnsRows, setReturnsRows] = useState<ReturnRequestRow[]>([]);
  const [exchangeRows, setExchangeRows] = useState<ExchangeRequestRow[]>([]);

  const [detailOpen, setDetailOpen] = useState(false);
  const [selectedReturn, setSelectedReturn] = useState<ReturnRequestRow | null>(null);
  const [selectedExchange, setSelectedExchange] = useState<ExchangeRequestRow | null>(null);
  const [detailNotes, setDetailNotes] = useState('');
  const [detailStaffNotes, setDetailStaffNotes] = useState('');

  const [rejectOpen, setRejectOpen] = useState(false);
  const [rejectTarget, setRejectTarget] = useState<{ type: Tab; id: string } | null>(null);
  const [rejectReason, setRejectReason] = useState('');

  const [deleteTarget, setDeleteTarget] = useState<{ type: Tab; id: string } | null>(null);

  const [createOpen, setCreateOpen] = useState(false);
  const [createType, setCreateType] = useState<Tab>('returns');
  const [saving, setSaving] = useState(false);
  const [orderSearch, setOrderSearch] = useState('');
  const [orderOptions, setOrderOptions] = useState<AdminOrderListRow[]>([]);
  const [selectedOrder, setSelectedOrder] = useState<AdminOrderDetail | null>(null);
  const [requestNotes, setRequestNotes] = useState('');

  const [returnItems, setReturnItems] = useState<Array<{
    order_item_id: string;
    sku: string;
    product_name: string;
    max_qty: number;
    selected: boolean;
    quantity: number;
    reason_code: string;
    reason_detail: string;
  }>>([]);

  const [exchangeItems, setExchangeItems] = useState<Array<{
    order_item_id: string;
    sku: string;
    product_name: string;
    max_qty: number;
    selected: boolean;
    quantity: number;
    reason_code: string;
    reason_detail: string;
    replacement_variant_id: string;
    replacement_search: string;
    replacement_options: Array<{ id: string; sku: string; product_name: string }>;
  }>>([]);

  const loadAll = async () => {
    try {
      setLoading(true);
      const [retRes, excRes] = await Promise.all([
        returnsService.listAdminReturns(),
        returnsService.listAdminExchanges(),
      ]);
      setReturnsRows(extractRows(retRes) as ReturnRequestRow[]);
      setExchangeRows(extractRows(excRes) as ExchangeRequestRow[]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadAll();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const q = orderSearch.trim();
    if (!createOpen || q.length < 2) {
      setOrderOptions([]);
      return;
    }
    (async () => {
      const res = await ordersService.listAdminOrders({ search: q });
      setOrderOptions(extractRows(res) as AdminOrderListRow[]);
    })();
  }, [orderSearch, createOpen]);

  const visibleRows = useMemo(() => {
    const q = searchTerm.trim().toLowerCase();
    const base = tab === 'returns' ? returnsRows : exchangeRows;
    if (!q) return base;
    return base.filter((row: any) => (
      [row.return_number || row.exchange_number, row.order_number, row.customer_name, row.customer_email]
        .join(' ')
        .toLowerCase()
        .includes(q)
    ));
  }, [tab, returnsRows, exchangeRows, searchTerm]);

  const openDetail = async (type: Tab, id: string) => {
    if (type === 'returns') {
      const res = await returnsService.getAdminReturn(id);
      const row = res?.data as ReturnRequestRow;
      setSelectedReturn(row);
      setSelectedExchange(null);
      setDetailNotes(row.notes || '');
      setDetailStaffNotes(row.staff_notes || '');
    } else {
      const res = await returnsService.getAdminExchange(id);
      const row = res?.data as ExchangeRequestRow;
      setSelectedExchange(row);
      setSelectedReturn(null);
      setDetailNotes(row.notes || '');
      setDetailStaffNotes(row.staff_notes || '');
    }
    setDetailOpen(true);
  };

  const saveDetail = async () => {
    if (selectedReturn) {
      await returnsService.updateAdminReturn(selectedReturn.id, {
        notes: detailNotes,
        staff_notes: detailStaffNotes,
      });
    }
    if (selectedExchange) {
      await returnsService.updateAdminExchange(selectedExchange.id, {
        notes: detailNotes,
        staff_notes: detailStaffNotes,
      });
    }
    setDetailOpen(false);
    await loadAll();
  };

  const openCreate = (type: Tab) => {
    setCreateType(type);
    setCreateOpen(true);
    setOrderSearch('');
    setOrderOptions([]);
    setSelectedOrder(null);
    setRequestNotes('');
    setReturnItems([]);
    setExchangeItems([]);
  };

  const pickOrder = async (id: string) => {
    const res = await ordersService.getAdminOrder(id);
    const detail = res?.data as AdminOrderDetail;
    setSelectedOrder(detail);
    const rItems = (detail.items || []).map((i) => ({
      order_item_id: i.id,
      sku: i.sku,
      product_name: i.product_name,
      max_qty: Number(i.quantity || 1),
      selected: false,
      quantity: 1,
      reason_code: 'other',
      reason_detail: '',
    }));
    setReturnItems(rItems);
    setExchangeItems(rItems.map((i) => ({
      ...i,
      replacement_variant_id: '',
      replacement_search: '',
      replacement_options: [],
    })));
    setOrderSearch(detail.order_number || '');
    setOrderOptions([]);
  };

  const searchReplacement = async (idx: number, term: string) => {
    setExchangeItems((prev) => prev.map((row, i) => i === idx ? { ...row, replacement_search: term } : row));
    if (term.trim().length < 2) {
      setExchangeItems((prev) => prev.map((row, i) => i === idx ? { ...row, replacement_options: [] } : row));
      return;
    }
    const res = await inventoryService.listVariants({ search: term, active_only: true });
    const options = extractRows(res).slice(0, 6).map((r: any) => ({
      id: String(r.id),
      sku: String(r.sku || ''),
      product_name: String(r.product_name || ''),
    }));
    setExchangeItems((prev) => prev.map((row, i) => i === idx ? { ...row, replacement_options: options } : row));
  };

  const submitCreate = async () => {
    if (!selectedOrder) {
      alert('Select an order first.');
      return;
    }
    setSaving(true);
    try {
      if (createType === 'returns') {
        const items = returnItems
          .filter((i) => i.selected)
          .map((i) => ({
            order_item_id: i.order_item_id,
            quantity: i.quantity,
            reason_code: i.reason_code,
            reason_detail: i.reason_detail,
          }));
        if (items.length === 0) {
          alert('Select at least one item for return.');
          return;
        }
        await returnsService.createAdminReturn({
          order_id: selectedOrder.id,
          notes: requestNotes,
          items,
        });
      } else {
        const items = exchangeItems
          .filter((i) => i.selected)
          .map((i) => ({
            order_item_id: i.order_item_id,
            replacement_variant_id: i.replacement_variant_id,
            quantity: i.quantity,
            reason_code: i.reason_code,
            reason_detail: i.reason_detail,
          }));
        if (items.length === 0) {
          alert('Select at least one item for exchange.');
          return;
        }
        if (items.some((i) => !i.replacement_variant_id)) {
          alert('Pick replacement variant for all selected exchange items.');
          return;
        }
        await returnsService.createAdminExchange({
          order_id: selectedOrder.id,
          notes: requestNotes,
          items,
        });
      }
      setCreateOpen(false);
      await loadAll();
    } catch (error: any) {
      alert(error?.response?.data?.message || 'Failed to create request.');
    } finally {
      setSaving(false);
    }
  };

  const approveRow = async (type: Tab, id: string) => {
    if (type === 'returns') await returnsService.approveReturn(id);
    else await returnsService.approveExchange(id);
    await loadAll();
  };

  const rejectRow = async () => {
    if (!rejectTarget || !rejectReason.trim()) return;
    if (rejectTarget.type === 'returns') await returnsService.rejectReturn(rejectTarget.id, rejectReason.trim());
    else await returnsService.rejectExchange(rejectTarget.id, rejectReason.trim());
    setRejectOpen(false);
    setRejectTarget(null);
    setRejectReason('');
    await loadAll();
  };

  const deleteRow = async () => {
    if (!deleteTarget) return;
    if (deleteTarget.type === 'returns') await returnsService.deleteAdminReturn(deleteTarget.id);
    else await returnsService.deleteAdminExchange(deleteTarget.id);
    setDeleteTarget(null);
    await loadAll();
  };

  const columns = [
    { header: 'Request', accessorKey: 'request', className: 'font-semibold', cell: (row: any) => row.return_number || row.exchange_number },
    { header: 'Order', accessorKey: 'order_number', className: 'text-muted-foreground', cell: (row: any) => row.order_number || '-' },
    { header: 'Customer', accessorKey: 'customer_name', cell: (row: any) => (
      <div className="flex flex-col">
        <span className="font-medium">{row.customer_name || 'Guest'}</span>
        <span className="text-xs text-muted-foreground">{row.customer_email || '-'}</span>
      </div>
    ) },
    { header: 'Items', accessorKey: 'items', align: 'right' as const, cell: (row: any) => Number(row.items?.length || 0) },
    { header: 'Status', accessorKey: 'status', align: 'right' as const, cell: (row: any) => <StatusBadge status={toTitle(row.status || '')} /> },
  ];

  const actions = (row: any) => {
    const status = String(row.status || '');
    const canApprove = status === 'submitted' || status === 'under_review';
    const canDelete = status === 'submitted' || status === 'under_review' || status === 'rejected';
    return (
      <div className="flex justify-end gap-2">
        <Button variant="outline" size="sm" className="h-8 gap-1" onClick={() => openDetail(tab, row.id)}>
          <Eye size={14} /> View
        </Button>
        {canApprove ? (
          <>
            <Button
              variant="outline"
              size="sm"
              className="h-8 gap-1 text-destructive border-destructive/40 hover:bg-destructive/10"
              onClick={() => {
                setRejectTarget({ type: tab, id: row.id });
                setRejectReason('');
                setRejectOpen(true);
              }}
            >
              <XCircle size={14} /> Reject
            </Button>
            <Button size="sm" className="h-8 gap-1" onClick={() => approveRow(tab, row.id)}>
              <CheckCircle size={14} /> Approve
            </Button>
          </>
        ) : null}
        {canDelete ? (
          <Button variant="outline" size="sm" className="h-8 gap-1 text-destructive border-destructive/40 hover:bg-destructive/10" onClick={() => setDeleteTarget({ type: tab, id: row.id })}>
            <Trash2 size={14} /> Delete
          </Button>
        ) : null}
      </div>
    );
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-foreground">Returns & Exchanges</h1>
          <p className="text-xs text-muted-foreground mt-1">DB-backed requests with admin approval workflow.</p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" onClick={() => openCreate('returns')} className="h-10"><Plus size={14} className="mr-1" /> New Return</Button>
          <Button onClick={() => openCreate('exchanges')} className="h-10"><Plus size={14} className="mr-1" /> New Exchange</Button>
        </div>
      </div>

      <div className="flex items-center gap-2">
        <Button variant={tab === 'returns' ? 'default' : 'outline'} onClick={() => setTab('returns')} className="h-9">Returns</Button>
        <Button variant={tab === 'exchanges' ? 'default' : 'outline'} onClick={() => setTab('exchanges')} className="h-9">Exchanges</Button>
      </div>

      <div className="bg-white p-4 rounded-[14px] border border-border shadow-sm">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" size={16} />
          <Input
            placeholder="Search by request, order, customer or email..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="pl-9 h-10 shadow-none border-border/60 bg-muted/20"
          />
        </div>
      </div>

      {loading ? (
        <div className="rounded-[14px] border border-border bg-white p-8 text-center text-sm text-muted-foreground">Loading...</div>
      ) : (
        <DataTable data={visibleRows as any[]} columns={columns} actions={actions} />
      )}

      <Modal open={createOpen} onOpenChange={setCreateOpen}>
        <ModalContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
          <ModalHeader>
            <ModalTitle>{createType === 'returns' ? 'Create Return Request' : 'Create Exchange Request'}</ModalTitle>
          </ModalHeader>

          <div className="space-y-4 py-3">
            <div className="grid gap-2">
              <label className="text-xs font-bold uppercase text-muted-foreground">Find Order</label>
              <Input value={orderSearch} onChange={(e) => setOrderSearch(e.target.value)} placeholder="Search order number, customer, email" />
              {orderOptions.length > 0 ? (
                <div className="rounded-lg border border-border/70 bg-white max-h-44 overflow-y-auto">
                  {orderOptions.slice(0, 8).map((o) => (
                    <button key={o.id} type="button" className="w-full text-left px-3 py-2 border-b border-border/50 last:border-b-0 hover:bg-muted/20" onClick={() => pickOrder(o.id)}>
                      <p className="text-sm font-semibold">#{o.order_number}</p>
                      <p className="text-xs text-muted-foreground">{o.customer_name} • {o.customer_email}</p>
                    </button>
                  ))}
                </div>
              ) : null}
            </div>

            {selectedOrder ? (
              <div className="rounded-xl border border-border p-3 space-y-3">
                <p className="text-sm font-semibold">Selected Order: #{selectedOrder.order_number}</p>
                <p className="text-xs text-muted-foreground">{selectedOrder.customer_name} • {selectedOrder.customer_email || selectedOrder.guest_email || '-'}</p>

                {createType === 'returns' ? (
                  <div className="space-y-2">
                    {returnItems.map((item, idx) => (
                      <div key={item.order_item_id} className="grid grid-cols-12 gap-2 items-center rounded-lg border border-border/70 bg-white p-2">
                        <input type="checkbox" checked={item.selected} onChange={(e) => setReturnItems((prev) => prev.map((x, i) => i === idx ? { ...x, selected: e.target.checked } : x))} />
                        <div className="col-span-4 text-xs">
                          <p className="font-semibold">{item.product_name}</p>
                          <p className="text-muted-foreground">{item.sku} (max {item.max_qty})</p>
                        </div>
                        <Input type="number" className="col-span-1 h-8" min={1} max={item.max_qty} value={item.quantity} onChange={(e) => setReturnItems((prev) => prev.map((x, i) => i === idx ? { ...x, quantity: Math.max(1, Math.min(item.max_qty, Number(e.target.value || 1))) } : x))} />
                        <select className="col-span-3 h-8 rounded-md border border-border/60 px-2 text-xs" value={item.reason_code} onChange={(e) => setReturnItems((prev) => prev.map((x, i) => i === idx ? { ...x, reason_code: e.target.value } : x))}>
                          {reasons.map((r) => <option key={r} value={r}>{toTitle(r)}</option>)}
                        </select>
                        <Input className="col-span-3 h-8" placeholder="Reason detail" value={item.reason_detail} onChange={(e) => setReturnItems((prev) => prev.map((x, i) => i === idx ? { ...x, reason_detail: e.target.value } : x))} />
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="space-y-2">
                    {exchangeItems.map((item, idx) => (
                      <div key={item.order_item_id} className="space-y-2 rounded-lg border border-border/70 bg-white p-2">
                        <div className="grid grid-cols-12 gap-2 items-center">
                          <input type="checkbox" checked={item.selected} onChange={(e) => setExchangeItems((prev) => prev.map((x, i) => i === idx ? { ...x, selected: e.target.checked } : x))} />
                          <div className="col-span-4 text-xs">
                            <p className="font-semibold">{item.product_name}</p>
                            <p className="text-muted-foreground">{item.sku} (max {item.max_qty})</p>
                          </div>
                          <Input type="number" className="col-span-1 h-8" min={1} max={item.max_qty} value={item.quantity} onChange={(e) => setExchangeItems((prev) => prev.map((x, i) => i === idx ? { ...x, quantity: Math.max(1, Math.min(item.max_qty, Number(e.target.value || 1))) } : x))} />
                          <select className="col-span-3 h-8 rounded-md border border-border/60 px-2 text-xs" value={item.reason_code} onChange={(e) => setExchangeItems((prev) => prev.map((x, i) => i === idx ? { ...x, reason_code: e.target.value } : x))}>
                            {reasons.map((r) => <option key={r} value={r}>{toTitle(r)}</option>)}
                          </select>
                          <Input className="col-span-3 h-8" placeholder="Reason detail" value={item.reason_detail} onChange={(e) => setExchangeItems((prev) => prev.map((x, i) => i === idx ? { ...x, reason_detail: e.target.value } : x))} />
                        </div>
                        <div className="grid grid-cols-1 gap-2 pl-6">
                          <Input value={item.replacement_search} onChange={(e) => searchReplacement(idx, e.target.value)} placeholder="Search replacement variant (SKU or name)" className="h-8" />
                          {item.replacement_options.length > 0 ? (
                            <div className="rounded-lg border border-border/70 bg-white max-h-36 overflow-y-auto">
                              {item.replacement_options.map((op) => (
                                <button key={op.id} type="button" className="w-full text-left px-3 py-2 border-b border-border/50 last:border-b-0 hover:bg-muted/20" onClick={() => setExchangeItems((prev) => prev.map((x, i) => i === idx ? { ...x, replacement_variant_id: op.id, replacement_search: `${op.sku} - ${op.product_name}`, replacement_options: [] } : x))}>
                                  <p className="text-xs font-semibold">{op.sku}</p>
                                  <p className="text-[11px] text-muted-foreground">{op.product_name}</p>
                                </button>
                              ))}
                            </div>
                          ) : null}
                        </div>
                      </div>
                    ))}
                  </div>
                )}

                <div className="grid gap-2">
                  <label className="text-xs font-bold uppercase text-muted-foreground">Notes</label>
                  <Input value={requestNotes} onChange={(e) => setRequestNotes(e.target.value)} />
                </div>
              </div>
            ) : null}
          </div>

          <ModalFooter>
            <Button variant="outline" onClick={() => setCreateOpen(false)} disabled={saving}>Cancel</Button>
            <Button onClick={submitCreate} disabled={saving}>{saving ? 'Saving...' : 'Create Request'}</Button>
          </ModalFooter>
        </ModalContent>
      </Modal>

      <Modal open={detailOpen} onOpenChange={setDetailOpen}>
        <ModalContent className="max-w-2xl">
          <ModalHeader>
            <ModalTitle>{selectedReturn ? selectedReturn.return_number : selectedExchange?.exchange_number}</ModalTitle>
          </ModalHeader>
          <div className="space-y-3 py-2">
            <div className="grid gap-2">
              <label className="text-xs font-bold uppercase text-muted-foreground">Customer</label>
              <Input value={selectedReturn?.customer_email || selectedExchange?.customer_email || ''} readOnly />
            </div>
            <div className="grid gap-2">
              <label className="text-xs font-bold uppercase text-muted-foreground">Notes</label>
              <Input value={detailNotes} onChange={(e) => setDetailNotes(e.target.value)} />
            </div>
            <div className="grid gap-2">
              <label className="text-xs font-bold uppercase text-muted-foreground">Staff Notes</label>
              <Input value={detailStaffNotes} onChange={(e) => setDetailStaffNotes(e.target.value)} />
            </div>
          </div>
          <ModalFooter>
            <Button variant="outline" onClick={() => setDetailOpen(false)}>Close</Button>
            <Button onClick={saveDetail}>Save</Button>
          </ModalFooter>
        </ModalContent>
      </Modal>

      <Modal open={rejectOpen} onOpenChange={setRejectOpen}>
        <ModalContent className="max-w-md">
          <ModalHeader><ModalTitle>Reject Request</ModalTitle></ModalHeader>
          <div className="py-2 grid gap-2">
            <label className="text-xs font-bold uppercase text-muted-foreground">Reason</label>
            <Input value={rejectReason} onChange={(e) => setRejectReason(e.target.value)} placeholder="Enter rejection reason" />
          </div>
          <ModalFooter>
            <Button variant="outline" onClick={() => setRejectOpen(false)}>Cancel</Button>
            <Button className="bg-destructive hover:bg-destructive/90 text-white" onClick={rejectRow}>Reject</Button>
          </ModalFooter>
        </ModalContent>
      </Modal>

      <ConfirmDialog
        open={Boolean(deleteTarget)}
        onOpenChange={(open) => { if (!open) setDeleteTarget(null); }}
        title={`Delete ${deleteTarget?.type === 'returns' ? 'Return' : 'Exchange'} Request`}
        description="This will permanently delete this request if it is still in a deletable status."
        confirmLabel="Delete"
        variant="destructive"
        onConfirm={deleteRow}
      />
    </div>
  );
};

