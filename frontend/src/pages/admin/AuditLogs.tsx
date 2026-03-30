import React, { useEffect, useMemo, useState } from 'react';
import { Search, Filter, RefreshCw, ChevronLeft, ChevronRight, Eye } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { DataTable, StatusBadge } from '@/components/admin/AdminTable';
import {
  Modal,
  ModalContent,
  ModalHeader,
  ModalTitle,
  ModalFooter,
} from '@/components/ui/Modal';
import auditLogsService, { type ActivityLogItem } from '@/services/api/auditLogs';

const ACTOR_TYPES = ['', 'admin', 'staff', 'customer', 'system'];
const ACTIONS = ['', 'CREATE', 'UPDATE', 'DELETE', 'LOGIN', 'LOGOUT', 'STATUS_CHANGE'];
const ENTITY_TYPES = [
  '',
  'auth',
  'product',
  'product_price',
  'inventory',
  'order',
  'return_request',
  'exchange_request',
  'coupon',
  'setting',
  'payment_config',
  'banner',
  'seo_setting',
  'feature_flag',
];

const toTitle = (value: string) => value.replace(/_/g, ' ').replace(/\b\w/g, (m) => m.toUpperCase());

interface ParsedListResponse {
  results: ActivityLogItem[];
  count: number;
  next: string | null;
  previous: string | null;
}

const parseListResponse = (payload: any): ParsedListResponse => {
  if (Array.isArray(payload?.results)) {
    return {
      results: payload.results,
      count: Number(payload.count || payload.results.length || 0),
      next: payload.next || null,
      previous: payload.previous || null,
    };
  }

  if (Array.isArray(payload?.data?.results)) {
    return {
      results: payload.data.results,
      count: Number(payload.data.count || payload.data.results.length || 0),
      next: payload.data.next || null,
      previous: payload.data.previous || null,
    };
  }

  if (Array.isArray(payload?.data)) {
    return {
      results: payload.data,
      count: Number(payload.data.length || 0),
      next: null,
      previous: null,
    };
  }

  if (Array.isArray(payload)) {
    return {
      results: payload,
      count: Number(payload.length || 0),
      next: null,
      previous: null,
    };
  }

  return { results: [], count: 0, next: null, previous: null };
};

export const AuditLogs: React.FC = () => {
  const [logs, setLogs] = useState<ActivityLogItem[]>([]);
  const [loading, setLoading] = useState(true);

  const [search, setSearch] = useState('');
  const [actorType, setActorType] = useState('');
  const [action, setAction] = useState('');
  const [entityType, setEntityType] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');

  const [page, setPage] = useState(1);
  const [count, setCount] = useState(0);
  const [hasNext, setHasNext] = useState(false);
  const [hasPrevious, setHasPrevious] = useState(false);
  const pageSize = 20;

  const [selectedLog, setSelectedLog] = useState<ActivityLogItem | null>(null);

  const fetchLogs = async () => {
    try {
      setLoading(true);
      const params: Record<string, string | number> = {
        page,
        ordering: '-created_at',
      };
      if (search.trim()) params.search = search.trim();
      if (actorType) params.actor_type = actorType;
      if (action) params.action = action;
      if (entityType) params.entity_type = entityType;
      if (dateFrom) params.date_from = `${dateFrom}T00:00:00`;
      if (dateTo) params.date_to = `${dateTo}T23:59:59`;

      const response = await auditLogsService.list(params);
      const parsed = parseListResponse(response);

      setLogs(parsed.results);
      setCount(parsed.count);
      setHasNext(Boolean(parsed.next));
      setHasPrevious(Boolean(parsed.previous));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchLogs();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page]);

  const applyFilters = () => {
    setPage(1);
    fetchLogs();
  };

  const clearFilters = () => {
    setSearch('');
    setActorType('');
    setAction('');
    setEntityType('');
    setDateFrom('');
    setDateTo('');
    setPage(1);
    setTimeout(() => {
      fetchLogs();
    }, 0);
  };

  const totalPages = Math.max(1, Math.ceil(count / pageSize));

  const columns = useMemo(
    () => [
      {
        header: 'Time',
        accessorKey: 'created_at',
        className: 'text-xs text-muted-foreground',
        cell: (item: ActivityLogItem) => new Date(item.created_at).toLocaleString(),
      },
      {
        header: 'Actor',
        accessorKey: 'actor_type',
        cell: (item: ActivityLogItem) => (
          <div className="flex flex-col">
            <StatusBadge status={toTitle(item.actor_type)} type="generic" />
            <span className="text-[11px] text-muted-foreground mt-1">{item.user?.email || 'System'}</span>
          </div>
        ),
      },
      {
        header: 'Action',
        accessorKey: 'action',
        cell: (item: ActivityLogItem) => <StatusBadge status={toTitle(item.action)} type="generic" />,
      },
      {
        header: 'Entity',
        accessorKey: 'entity_type',
        cell: (item: ActivityLogItem) => (
          <div className="flex flex-col">
            <span className="font-semibold">{toTitle(item.entity_type)}</span>
            <span className="text-[11px] text-muted-foreground">{item.entity_id || '-'}</span>
          </div>
        ),
      },
      {
        header: 'Description',
        accessorKey: 'description',
        cell: (item: ActivityLogItem) => <span className="text-xs">{item.description}</span>,
      },
      {
        header: 'Request',
        accessorKey: 'request_id',
        cell: (item: ActivityLogItem) => (
          <div className="flex flex-col text-[11px] text-muted-foreground">
            <span>{item.method || '-'} {item.path || '-'}</span>
            <span>{item.request_id || '-'}</span>
          </div>
        ),
      },
    ],
    []
  );

  const actions = (item: ActivityLogItem) => (
    <Button variant="ghost" size="sm" className="h-8 gap-1" onClick={() => setSelectedLog(item)}>
      <Eye size={14} />
      View
    </Button>
  );

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-foreground">Audit Logs</h1>
          <p className="text-xs text-muted-foreground mt-1">Centralized activity timeline across admin, customer, and system actions.</p>
        </div>
        <Button variant="outline" onClick={fetchLogs} className="h-10 gap-2 px-4 rounded-xl border-border/60 bg-white">
          <RefreshCw size={16} />
          Refresh
        </Button>
      </div>

      <div className="bg-white p-4 rounded-[14px] border border-border shadow-sm space-y-3">
        <div className="grid grid-cols-1 md:grid-cols-6 gap-3">
          <div className="relative md:col-span-2">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" size={16} />
            <Input
              placeholder="Search description or entity id"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-9 h-10 border-border/60 bg-muted/20"
            />
          </div>

          <select className="h-10 rounded-md border border-border/60 bg-white px-3 text-sm" value={actorType} onChange={(e) => setActorType(e.target.value)}>
            {ACTOR_TYPES.map((v) => <option key={v || 'all'} value={v}>{v ? toTitle(v) : 'All Actors'}</option>)}
          </select>

          <select className="h-10 rounded-md border border-border/60 bg-white px-3 text-sm" value={action} onChange={(e) => setAction(e.target.value)}>
            {ACTIONS.map((v) => <option key={v || 'all'} value={v}>{v ? toTitle(v) : 'All Actions'}</option>)}
          </select>

          <select className="h-10 rounded-md border border-border/60 bg-white px-3 text-sm" value={entityType} onChange={(e) => setEntityType(e.target.value)}>
            {ENTITY_TYPES.map((v) => <option key={v || 'all'} value={v}>{v ? toTitle(v) : 'All Entities'}</option>)}
          </select>

          <div className="flex items-center gap-2">
            <Button onClick={applyFilters} className="h-10 px-4 gap-2 w-full">
              <Filter size={14} />
              Apply
            </Button>
            <Button type="button" variant="outline" onClick={clearFilters} className="h-10 px-3 border-border/60">
              Clear
            </Button>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
          <div className="grid gap-1">
            <label className="text-[11px] uppercase font-bold text-muted-foreground">Date From</label>
            <Input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} className="h-10 border-border/60" />
          </div>
          <div className="grid gap-1">
            <label className="text-[11px] uppercase font-bold text-muted-foreground">Date To</label>
            <Input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} className="h-10 border-border/60" />
          </div>
          <div className="md:col-span-2 flex items-end text-xs text-muted-foreground">
            Showing page {page} of {totalPages} ({count} records)
          </div>
        </div>
      </div>

      {loading ? (
        <div className="rounded-[14px] border border-border bg-white p-8 text-center text-sm text-muted-foreground">Loading audit logs...</div>
      ) : (
        <DataTable data={logs} columns={columns} actions={actions} onRowClick={(item) => setSelectedLog(item as ActivityLogItem)} />
      )}

      <div className="flex items-center justify-end gap-2">
        <Button variant="outline" className="h-9 gap-1 border-border/60" disabled={!hasPrevious || page <= 1} onClick={() => setPage((p) => Math.max(1, p - 1))}>
          <ChevronLeft size={14} />
          Prev
        </Button>
        <span className="text-xs text-muted-foreground px-2">Page {page}</span>
        <Button variant="outline" className="h-9 gap-1 border-border/60" disabled={!hasNext} onClick={() => setPage((p) => p + 1)}>
          Next
          <ChevronRight size={14} />
        </Button>
      </div>

      <Modal open={Boolean(selectedLog)} onOpenChange={(open) => { if (!open) setSelectedLog(null); }}>
        <ModalContent className="max-w-3xl max-h-[85vh] overflow-y-auto">
          <ModalHeader>
            <ModalTitle>Audit Entry Details</ModalTitle>
          </ModalHeader>

          {selectedLog ? (
            <div className="space-y-4 text-sm">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <div><span className="font-bold">Time:</span> {new Date(selectedLog.created_at).toLocaleString()}</div>
                <div><span className="font-bold">Action:</span> {selectedLog.action}</div>
                <div><span className="font-bold">Actor:</span> {selectedLog.actor_type}</div>
                <div><span className="font-bold">Entity:</span> {selectedLog.entity_type}</div>
                <div><span className="font-bold">Entity ID:</span> {selectedLog.entity_id || '-'}</div>
                <div><span className="font-bold">User:</span> {selectedLog.user?.email || 'System'}</div>
                <div className="md:col-span-2"><span className="font-bold">Description:</span> {selectedLog.description}</div>
                <div><span className="font-bold">Request ID:</span> {selectedLog.request_id || '-'}</div>
                <div><span className="font-bold">IP Address:</span> {selectedLog.ip_address || '-'}</div>
                <div className="md:col-span-2"><span className="font-bold">Path:</span> {selectedLog.method || '-'} {selectedLog.path || '-'}</div>
              </div>
              <div className="rounded-xl border border-border bg-muted/20 p-3">
                <p className="text-xs font-bold uppercase text-muted-foreground mb-2">Metadata</p>
                <pre className="text-xs whitespace-pre-wrap break-all">{JSON.stringify(selectedLog.metadata || {}, null, 2)}</pre>
              </div>
            </div>
          ) : null}

          <ModalFooter>
            <Button variant="outline" onClick={() => setSelectedLog(null)}>Close</Button>
          </ModalFooter>
        </ModalContent>
      </Modal>
    </div>
  );
};
