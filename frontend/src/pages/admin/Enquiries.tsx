import React, { useEffect, useMemo, useState } from 'react';
import { DataTable, StatusBadge } from '@/components/admin/AdminTable';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Search, RefreshCw, CheckCircle2 } from 'lucide-react';
import notifyService, { type ContactQueryItem } from '@/services/api/notify';

const extractRows = (payload: any): ContactQueryItem[] => {
  if (Array.isArray(payload?.data)) return payload.data as ContactQueryItem[];
  return [];
};

export const Enquiries: React.FC = () => {
  const [rows, setRows] = useState<ContactQueryItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [search, setSearch] = useState('');
  const [status, setStatus] = useState('');
  const [selectedIds, setSelectedIds] = useState<string[]>([]);

  const loadRows = async () => {
    try {
      setLoading(true);
      const data = await notifyService.listContactQueries({
        search: search.trim() || undefined,
        status: status === '' ? undefined : (status as 'new' | 'read' | 'resolved'),
      });
      setRows(extractRows(data));
      setSelectedIds([]);
    } catch (error) {
      console.error('Failed to load enquiries:', error);
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
    setSelectedIds(rows.map((row) => row.id));
  };

  const toggleSelectRow = (id: string) => {
    setSelectedIds((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));
  };

  const markSelectedAsRead = async () => {
    if (selectedIds.length === 0) return;
    try {
      await notifyService.markContactQueriesRead(selectedIds);
      await loadRows();
    } catch (error) {
      console.error('Failed to mark enquiries as read:', error);
      alert('Failed to mark selected enquiries as read.');
    }
  };

  const columns = useMemo(
    () => [
      {
        header: '',
        accessorKey: 'id',
        className: 'w-[40px]',
        cell: (item: ContactQueryItem) => (
          <input
            type="checkbox"
            className="h-4 w-4 rounded border-border"
            checked={selectedIds.includes(item.id)}
            onChange={() => toggleSelectRow(item.id)}
            onClick={(e) => e.stopPropagation()}
          />
        ),
      },
      { header: 'Name', accessorKey: 'name', className: 'font-semibold' },
      { header: 'Email', accessorKey: 'email' },
      { header: 'Phone', accessorKey: 'phone', cell: (item: ContactQueryItem) => item.phone || '—' },
      { header: 'Subject', accessorKey: 'subject', cell: (item: ContactQueryItem) => item.subject || 'General enquiry' },
      {
        header: 'Status',
        accessorKey: 'status',
        align: 'right' as const,
        cell: (item: ContactQueryItem) => (
          <StatusBadge status={item.is_read ? 'Completed' : 'Pending'} />
        ),
      },
      {
        header: 'Created At',
        accessorKey: 'created_at',
        align: 'right' as const,
        cell: (item: ContactQueryItem) => new Date(item.created_at).toLocaleString(),
      },
    ],
    [selectedIds]
  );

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Enquiries</h1>
          <p className="text-sm text-muted-foreground">Customer enquiries submitted from Contact Us form.</p>
        </div>
        <Button className="rounded-xl h-10" onClick={markSelectedAsRead} disabled={selectedIds.length === 0}>
          <CheckCircle2 size={16} className="mr-2" />
          Mark as Read
        </Button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-3">
        <div className="lg:col-span-8 relative">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
          <Input
            className="pl-9 h-10 rounded-xl"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search by name, email, phone, subject"
          />
        </div>
        <div className="lg:col-span-3">
          <select
            className="h-10 w-full rounded-xl border border-border bg-background px-3 text-sm"
            value={status}
            onChange={(e) => setStatus(e.target.value)}
          >
            <option value="">All Status</option>
            <option value="new">New</option>
            <option value="read">Read</option>
            <option value="resolved">Resolved</option>
          </select>
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
