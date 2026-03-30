import React, { useEffect, useMemo, useState } from 'react';
import { Button } from '@/components/ui/Button';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/Table';
import notificationsAdminService, { type NotificationLogDetail, type NotificationLogListItem } from '@/services/api/adminNotifications';
import { FiltersBar, type NotificationLogFilters } from '@/components/admin/notifications/FiltersBar';
import { NotificationDetailDrawer } from '@/components/admin/notifications/NotificationDetailDrawer';

const initialFilters: NotificationLogFilters = {
  search: '',
  status: '',
  channel: '',
  provider: '',
  notification_type: '',
  date_from: '',
  date_to: '',
};

export const NotificationLogs: React.FC = () => {
  const [rows, setRows] = useState<NotificationLogListItem[]>([]);
  const [filters, setFilters] = useState<NotificationLogFilters>(initialFilters);
  const [loading, setLoading] = useState(false);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<NotificationLogDetail | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);

  const load = async (nextPage = page) => {
    try {
      setLoading(true);
      const response = await notificationsAdminService.getLogs({ ...filters, page: nextPage, page_size: 20 });
      setRows(response?.data?.items || []);
      setTotalPages(response?.data?.pagination?.total_pages || 1);
      setPage(nextPage);
    } catch (error) {
      console.error('Failed to load notification logs', error);
      setRows([]);
      setTotalPages(1);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load(1);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const openDetail = async (id: string) => {
    try {
      setSelectedId(id);
      setDrawerOpen(true);
      const response = await notificationsAdminService.getLogDetail(id);
      setDetail(response?.data || null);
    } catch (error) {
      console.error('Failed to load notification detail', error);
      setDetail(null);
    }
  };

  const retrySelected = async (id: string) => {
    try {
      await notificationsAdminService.retryLog(id);
      await load(page);
    } catch (error: any) {
      console.error('Failed to retry notification log', error);
      alert(error?.response?.data?.message || 'Retry failed.');
    }
  };

  const paginationLabel = useMemo(() => `Page ${page} of ${Math.max(totalPages, 1)}`, [page, totalPages]);

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold">Notification Logs</h2>
          <p className="text-xs text-muted-foreground">Filter, inspect, and retry failed notifications.</p>
        </div>
      </div>

      <FiltersBar filters={filters} onChange={setFilters} onApply={() => load(1)} loading={loading} />

      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Created</TableHead>
            <TableHead>Channel</TableHead>
            <TableHead>Type</TableHead>
            <TableHead>Recipient</TableHead>
            <TableHead>Subject</TableHead>
            <TableHead>Provider</TableHead>
            <TableHead>Status</TableHead>
            <TableHead>Attempts</TableHead>
            <TableHead className="text-right">Actions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.length === 0 ? (
            <TableRow>
              <TableCell colSpan={9} className="text-center text-sm text-muted-foreground">No logs found.</TableCell>
            </TableRow>
          ) : (
            rows.map((row) => (
              <TableRow key={row.id}>
                <TableCell>{new Date(row.created_at).toLocaleString()}</TableCell>
                <TableCell className="uppercase">{row.channel}</TableCell>
                <TableCell>{row.notification_type}</TableCell>
                <TableCell>{row.recipient || '—'}</TableCell>
                <TableCell className="max-w-[260px] truncate">{row.subject || '—'}</TableCell>
                <TableCell className="uppercase">{row.provider}</TableCell>
                <TableCell className="uppercase">{row.status}</TableCell>
                <TableCell>{row.attempts_count}</TableCell>
                <TableCell className="text-right space-x-2">
                  <Button variant="outline" className="h-8 px-2" onClick={() => openDetail(row.id)}>View</Button>
                  <Button
                    className="h-8 px-2"
                    disabled={row.status !== 'failed'}
                    onClick={() => retrySelected(row.id)}
                  >
                    Retry
                  </Button>
                </TableCell>
              </TableRow>
            ))
          )}
        </TableBody>
      </Table>

      <div className="flex items-center justify-between rounded-xl border border-border/70 bg-white px-4 py-3">
        <span className="text-sm text-muted-foreground">{paginationLabel}</span>
        <div className="space-x-2">
          <Button variant="outline" className="h-9" disabled={page <= 1} onClick={() => load(page - 1)}>Previous</Button>
          <Button variant="outline" className="h-9" disabled={page >= totalPages} onClick={() => load(page + 1)}>Next</Button>
        </div>
      </div>

      <NotificationDetailDrawer open={drawerOpen} onOpenChange={setDrawerOpen} data={selectedId ? detail : null} />
    </div>
  );
};
