import React, { useEffect, useMemo, useState } from 'react';
import { DataTable, StatusBadge } from '@/components/admin/AdminTable';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { RefreshCw, Search } from 'lucide-react';
import shippingService from '@/services/api/shipping';

const extractRows = (payload: any): any[] => {
  if (Array.isArray(payload?.data)) return payload.data;
  if (Array.isArray(payload?.data?.results)) return payload.data.results;
  if (Array.isArray(payload?.results)) return payload.results;
  if (Array.isArray(payload)) return payload;
  return [];
};

const toTitle = (value: string) => value.replace(/_/g, ' ').replace(/\b\w/g, (m) => m.toUpperCase());

export const Shipments: React.FC = () => {
  const [rows, setRows] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');

  const loadRows = async () => {
    try {
      setLoading(true);
      const res = await shippingService.listShipments();
      setRows(extractRows(res));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadRows();
  }, []);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return rows;
    return rows.filter((r) => [r.order_number, r.awb_code, r.courier_name, r.status, r.provider].join(' ').toLowerCase().includes(q));
  }, [rows, search]);

  const columns = [
    { header: 'Order', accessorKey: 'order_number', cell: (r: any) => <span className="font-semibold">#{r.order_number}</span> },
    { header: 'Provider', accessorKey: 'provider', cell: (r: any) => toTitle(r.provider || '-') },
    { header: 'Status', accessorKey: 'status', cell: (r: any) => <StatusBadge status={toTitle(r.status || 'created')} type="order" /> },
    { header: 'AWB', accessorKey: 'awb_code', cell: (r: any) => r.awb_code || '-' },
    { header: 'Courier', accessorKey: 'courier_name', cell: (r: any) => r.courier_name || '-' },
    {
      header: 'Tracking',
      accessorKey: 'tracking_url',
      cell: (r: any) => r.tracking_url ? <a href={r.tracking_url} className="text-primary underline" target="_blank" rel="noreferrer">Open</a> : '-',
    },
    { header: 'Created', accessorKey: 'created_at', cell: (r: any) => new Date(r.created_at).toLocaleString() },
  ];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-foreground">Shipments</h1>
          <p className="text-xs text-muted-foreground mt-1">Operational shipment view across logistics providers.</p>
        </div>
        <Button variant="outline" onClick={loadRows} className="h-10 gap-2"><RefreshCw size={16} /> Refresh</Button>
      </div>

      <div className="bg-white p-4 rounded-[14px] border border-border shadow-sm">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" size={16} />
          <Input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search order/AWB/courier/status" className="pl-9 h-10" />
        </div>
      </div>

      {loading ? (
        <div className="rounded-[14px] border border-border bg-white p-8 text-center text-sm text-muted-foreground">Loading shipments...</div>
      ) : (
        <DataTable data={filtered} columns={columns} />
      )}
    </div>
  );
};
