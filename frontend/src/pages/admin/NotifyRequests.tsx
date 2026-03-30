import React, { useEffect, useMemo, useState } from 'react';
import { DataTable, StatusBadge } from '@/components/admin/AdminTable';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Search, RefreshCw, Download } from 'lucide-react';
import notifyService from '@/services/api/notify';

interface NotifyRequestRow {
  id: string;
  product: string;
  product_name: string;
  user_email: string;
  email: string;
  phone: string;
  status: 'Pending' | 'Notified';
  is_notified: boolean;
  created_at: string;
}

const extractRows = (payload: any): NotifyRequestRow[] => {
  if (Array.isArray(payload?.data)) return payload.data as NotifyRequestRow[];
  return [];
};

export const NotifyRequests: React.FC = () => {
  const [rows, setRows] = useState<NotifyRequestRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [search, setSearch] = useState('');
  const [isNotified, setIsNotified] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [selectedIds, setSelectedIds] = useState<string[]>([]);

  const loadRows = async () => {
    try {
      setLoading(true);
      const data = await notifyService.listAdmin({
        search: search.trim() || undefined,
        is_notified: isNotified === '' ? undefined : (isNotified as 'true' | 'false'),
        date_from: dateFrom || undefined,
        date_to: dateTo || undefined,
      });
      setRows(extractRows(data));
      setSelectedIds([]);
    } catch (error) {
      console.error('Failed to load notify subscriptions:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadRows();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const allSelected = rows.length > 0 && selectedIds.length === rows.length;

  const toggleSelectAll = () => {
    if (allSelected) {
      setSelectedIds([]);
      return;
    }
    setSelectedIds(rows.map((r) => r.id));
  };

  const toggleSelectRow = (id: string) => {
    setSelectedIds((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));
  };

  const markSelectedAsNotified = async () => {
    if (selectedIds.length === 0) return;
    try {
      await notifyService.markNotified(selectedIds);
      await loadRows();
    } catch (error) {
      console.error('Failed to mark selected notify requests:', error);
      alert('Failed to mark selected requests as notified.');
    }
  };

  const markAllAsNotified = async () => {
    try {
      await notifyService.markAllNotified();
      await loadRows();
    } catch (error) {
      console.error('Failed to mark all notify requests:', error);
      alert('Failed to mark all requests as notified.');
    }
  };

  const exportCsv = async () => {
    try {
      const blob = await notifyService.exportAdminCsv();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'notify_subscriptions.csv';
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (error) {
      console.error('Failed to export CSV:', error);
      alert('Failed to export CSV.');
    }
  };

  const columns = useMemo(
    () => [
      {
        header: '',
        accessorKey: 'id',
        className: 'w-[40px]',
        cell: (item: NotifyRequestRow) => (
          <input
            type="checkbox"
            className="h-4 w-4 rounded border-border"
            checked={selectedIds.includes(item.id)}
            onChange={() => toggleSelectRow(item.id)}
            onClick={(e) => e.stopPropagation()}
          />
        ),
      },
      { header: 'Product', accessorKey: 'product_name', className: 'font-semibold' },
      {
        header: 'User / Email',
        accessorKey: 'email',
        cell: (item: NotifyRequestRow) => item.user_email || item.email || '—',
      },
      { header: 'Phone', accessorKey: 'phone', cell: (item: NotifyRequestRow) => item.phone || '—' },
      {
        header: 'Status',
        accessorKey: 'status',
        align: 'right' as const,
        cell: (item: NotifyRequestRow) => <StatusBadge status={item.status} />,
      },
      {
        header: 'Created At',
        accessorKey: 'created_at',
        align: 'right' as const,
        cell: (item: NotifyRequestRow) => new Date(item.created_at).toLocaleString(),
      },
    ],
    [selectedIds]
  );

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Notify Requests</h1>
          <p className="text-sm text-muted-foreground">Track users waiting for out-of-stock products.</p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" className="rounded-xl h-10" onClick={exportCsv}>
            <Download size={16} className="mr-2" />
            Export CSV
          </Button>
          <Button variant="outline" className="rounded-xl h-10" onClick={markAllAsNotified} disabled={rows.length === 0}>
            Mark All as Notified
          </Button>
          <Button className="rounded-xl h-10" onClick={markSelectedAsNotified} disabled={selectedIds.length === 0}>
            Mark as Notified
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-3">
        <div className="lg:col-span-5 relative">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
          <Input
            className="pl-9 h-10 rounded-xl"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search product, email, phone"
          />
        </div>
        <div className="lg:col-span-2">
          <select
            className="h-10 w-full rounded-xl border border-border bg-background px-3 text-sm"
            value={isNotified}
            onChange={(e) => setIsNotified(e.target.value)}
          >
            <option value="">All Status</option>
            <option value="false">Pending</option>
            <option value="true">Notified</option>
          </select>
        </div>
        <div className="lg:col-span-2">
          <Input type="date" className="h-10 rounded-xl" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} />
        </div>
        <div className="lg:col-span-2">
          <Input type="date" className="h-10 rounded-xl" value={dateTo} onChange={(e) => setDateTo(e.target.value)} />
        </div>
        <div className="lg:col-span-1">
          <Button variant="outline" className="w-full h-10 rounded-xl" onClick={loadRows} disabled={loading}>
            <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
          </Button>
        </div>
      </div>

      <div className="bg-white rounded-[14px] border border-border shadow-sm p-3">
        <label className="inline-flex items-center gap-2 text-xs text-muted-foreground font-medium">
          <input type="checkbox" className="h-4 w-4 rounded border-border" checked={allSelected} onChange={toggleSelectAll} />
          Select all
        </label>
      </div>

      <DataTable data={rows} columns={columns as any} />
    </div>
  );
};
