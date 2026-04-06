import React, { useEffect, useMemo, useState } from 'react';
import { Search, RefreshCw, Download, MailCheck, MailQuestion, MailX } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { DataTable } from '@/components/admin/AdminTable';
import newsletterService, { type NewsletterSubscriberItem } from '@/services/api/newsletter';

const downloadBlob = (blob: Blob, fileName: string) => {
  const url = window.URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = fileName;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  window.URL.revokeObjectURL(url);
};

const formatDateTime = (value?: string | null) => {
  if (!value) return '—';
  return new Date(value).toLocaleString();
};

const statusTone = (status: string) => {
  const normalized = status.toLowerCase();
  if (normalized.includes('confirmed')) return 'bg-emerald-50 text-emerald-700 border-emerald-200';
  if (normalized.includes('pending')) return 'bg-amber-50 text-amber-700 border-amber-200';
  return 'bg-rose-50 text-rose-700 border-rose-200';
};

export const NewsletterSubscribers: React.FC = () => {
  const [items, setItems] = useState<NewsletterSubscriberItem[]>([]);
  const [summary, setSummary] = useState({ total: 0, confirmed: 0, pending: 0, unsubscribed: 0 });
  const [pagination, setPagination] = useState({ page: 1, page_size: 20, total: 0, total_pages: 1 });
  const [loading, setLoading] = useState(false);
  const [exportingFormat, setExportingFormat] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [sourceFilter, setSourceFilter] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');

  const loadSubscribers = async (page = 1) => {
    try {
      setLoading(true);
      const response = await newsletterService.listSubscribers({
        page,
        page_size: pagination.page_size,
        search: search.trim() || undefined,
        status: (statusFilter || undefined) as 'confirmed' | 'pending' | 'unsubscribed' | undefined,
        source: sourceFilter.trim() || undefined,
        date_from: dateFrom || undefined,
        date_to: dateTo || undefined,
      });

      setItems(response?.data?.items || []);
      setSummary(response?.data?.summary || { total: 0, confirmed: 0, pending: 0, unsubscribed: 0 });
      setPagination(response?.data?.pagination || { page: 1, page_size: 20, total: 0, total_pages: 1 });
    } catch (error) {
      console.error('Failed to load newsletter subscribers:', error);
      setItems([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadSubscribers(1);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleExport = async (format: 'pdf' | 'excel' | 'legacy') => {
    try {
      setExportingFormat(format);
      const blob = await newsletterService.exportSubscribers(format, {
        search: search.trim() || undefined,
        status: (statusFilter || undefined) as 'confirmed' | 'pending' | 'unsubscribed' | undefined,
        source: sourceFilter.trim() || undefined,
        date_from: dateFrom || undefined,
        date_to: dateTo || undefined,
      });

      const fileName =
        format === 'pdf'
          ? 'newsletter-subscribers.pdf'
          : format === 'excel'
            ? 'newsletter-subscribers.xls'
            : 'newsletter-subscribers-legacy.csv';
      downloadBlob(blob, fileName);
    } catch (error) {
      console.error(`Failed to export ${format}:`, error);
      alert(`Failed to export ${format}.`);
    } finally {
      setExportingFormat(null);
    }
  };

  const columns = useMemo(
    () => [
      {
        header: 'Email',
        accessorKey: 'email',
        className: 'font-semibold min-w-[240px]',
      },
      {
        header: 'Status',
        accessorKey: 'status',
        cell: (item: NewsletterSubscriberItem) => (
          <span className={`inline-flex rounded-full border px-3 py-1 text-xs font-semibold ${statusTone(item.status)}`}>
            {item.status}
          </span>
        ),
      },
      {
        header: 'Source',
        accessorKey: 'source',
        cell: (item: NewsletterSubscriberItem) => item.source || 'footer',
      },
      {
        header: 'Subscribed',
        accessorKey: 'subscribed_at',
        cell: (item: NewsletterSubscriberItem) => formatDateTime(item.subscribed_at),
      },
      {
        header: 'Confirmed',
        accessorKey: 'confirmed_at',
        cell: (item: NewsletterSubscriberItem) => formatDateTime(item.confirmed_at),
      },
      {
        header: 'Last Updated',
        accessorKey: 'updated_at',
        cell: (item: NewsletterSubscriberItem) => formatDateTime(item.updated_at),
      },
    ],
    []
  );

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Newsletter Subscribers</h1>
          <p className="text-sm text-muted-foreground">
            Manage signups, confirmation status, unsubscribe state, and exports for the Aurora Blings newsletter.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" className="h-10 rounded-xl" onClick={() => handleExport('pdf')} disabled={exportingFormat !== null}>
            <Download size={16} className="mr-2" />
            {exportingFormat === 'pdf' ? 'Exporting...' : 'Export PDF'}
          </Button>
          <Button variant="outline" className="h-10 rounded-xl" onClick={() => handleExport('excel')} disabled={exportingFormat !== null}>
            <Download size={16} className="mr-2" />
            {exportingFormat === 'excel' ? 'Exporting...' : 'Export Excel'}
          </Button>
          <Button variant="outline" className="h-10 rounded-xl" onClick={() => handleExport('legacy')} disabled={exportingFormat !== null}>
            <Download size={16} className="mr-2" />
            {exportingFormat === 'legacy' ? 'Exporting...' : 'Export Legacy'}
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
        <Card className="hover:translate-y-0">
          <CardHeader className="pb-3">
            <CardDescription>Total Subscribers</CardDescription>
            <CardTitle className="text-3xl">{summary.total}</CardTitle>
          </CardHeader>
          <CardContent className="pt-0 text-xs text-muted-foreground">All newsletter records captured so far.</CardContent>
        </Card>
        <Card className="hover:translate-y-0">
          <CardHeader className="pb-3">
            <CardDescription className="flex items-center gap-2"><MailCheck size={14} /> Confirmed</CardDescription>
            <CardTitle className="text-3xl">{summary.confirmed}</CardTitle>
          </CardHeader>
          <CardContent className="pt-0 text-xs text-muted-foreground">Verified subscribers receiving campaigns.</CardContent>
        </Card>
        <Card className="hover:translate-y-0">
          <CardHeader className="pb-3">
            <CardDescription className="flex items-center gap-2"><MailQuestion size={14} /> Pending</CardDescription>
            <CardTitle className="text-3xl">{summary.pending}</CardTitle>
          </CardHeader>
          <CardContent className="pt-0 text-xs text-muted-foreground">Awaiting double opt-in confirmation.</CardContent>
        </Card>
        <Card className="hover:translate-y-0">
          <CardHeader className="pb-3">
            <CardDescription className="flex items-center gap-2"><MailX size={14} /> Unsubscribed</CardDescription>
            <CardTitle className="text-3xl">{summary.unsubscribed}</CardTitle>
          </CardHeader>
          <CardContent className="pt-0 text-xs text-muted-foreground">Users who opted out using the unsubscribe link.</CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 gap-3 lg:grid-cols-12">
        <div className="relative lg:col-span-4">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
          <Input
            className="h-10 rounded-xl pl-9"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search by email"
          />
        </div>
        <div className="lg:col-span-2">
          <select
            className="h-10 w-full rounded-xl border border-border bg-background px-3 text-sm"
            value={statusFilter}
            onChange={(event) => setStatusFilter(event.target.value)}
          >
            <option value="">All Status</option>
            <option value="confirmed">Confirmed</option>
            <option value="pending">Pending</option>
            <option value="unsubscribed">Unsubscribed</option>
          </select>
        </div>
        <div className="lg:col-span-2">
          <Input
            className="h-10 rounded-xl"
            value={sourceFilter}
            onChange={(event) => setSourceFilter(event.target.value)}
            placeholder="Source"
          />
        </div>
        <div className="lg:col-span-2">
          <Input type="date" className="h-10 rounded-xl" value={dateFrom} onChange={(event) => setDateFrom(event.target.value)} />
        </div>
        <div className="lg:col-span-1">
          <Input type="date" className="h-10 rounded-xl" value={dateTo} onChange={(event) => setDateTo(event.target.value)} />
        </div>
        <div className="lg:col-span-1">
          <Button variant="outline" className="h-10 w-full rounded-xl" onClick={() => loadSubscribers(1)} disabled={loading}>
            <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
          </Button>
        </div>
      </div>

      <DataTable data={items} columns={columns as any} />

      <div className="flex flex-col gap-3 rounded-[14px] border border-border bg-white p-4 shadow-sm md:flex-row md:items-center md:justify-between">
        <p className="text-sm text-muted-foreground">
          Page {pagination.page} of {Math.max(pagination.total_pages, 1)} · {pagination.total} total subscriber(s)
        </p>
        <div className="flex gap-2">
          <Button
            variant="outline"
            className="h-9 rounded-xl"
            disabled={pagination.page <= 1 || loading}
            onClick={() => loadSubscribers(pagination.page - 1)}
          >
            Previous
          </Button>
          <Button
            variant="outline"
            className="h-9 rounded-xl"
            disabled={pagination.page >= pagination.total_pages || loading}
            onClick={() => loadSubscribers(pagination.page + 1)}
          >
            Next
          </Button>
        </div>
      </div>
    </div>
  );
};
