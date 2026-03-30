import React, { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import notificationsAdminService, { type NotificationProviderStatus } from '@/services/api/adminNotifications';
import { StatsCards } from '@/components/admin/notifications/StatsCards';
import { NotificationCharts } from '@/components/admin/notifications/NotificationCharts';
import { ProviderStatusCards } from '@/components/admin/notifications/ProviderStatusCards';

interface DashboardData {
  stats: any;
  provider_status: NotificationProviderStatus[];
  recent_failures: Array<any>;
  template_usage: Array<any>;
}

export const NotificationDashboard: React.FC = () => {
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [testingId, setTestingId] = useState<number | null>(null);

  const load = async () => {
    try {
      setLoading(true);
      const response = await notificationsAdminService.getDashboard();
      setData(response?.data || null);
    } catch (error) {
      console.error('Failed to load notification dashboard', error);
      setData(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, []);

  const stats = data?.stats || {};

  const channelBreakdown = useMemo(
    () => (stats.channel_breakdown || []).map((x: any) => ({ key: x.channel, count: x.count })),
    [stats.channel_breakdown]
  );
  const providerBreakdown = useMemo(
    () => (stats.provider_breakdown || []).map((x: any) => ({ key: x.provider, count: x.count })),
    [stats.provider_breakdown]
  );

  const handleTestProvider = async (providerId: number) => {
    try {
      setTestingId(providerId);
      await notificationsAdminService.testProvider(providerId);
      await load();
    } catch (error) {
      console.error('Provider test failed', error);
      alert('Provider test failed.');
    } finally {
      setTestingId(null);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Notification Dashboard</h1>
          <p className="text-xs text-muted-foreground">Operational view of all outgoing notifications across providers and templates.</p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" onClick={() => load()} className="h-9">Refresh</Button>
          <Link to="/admin/notifications/logs">
            <Button className="h-9">Open Logs</Button>
          </Link>
        </div>
      </div>

      <StatsCards
        totalSent={Number(stats.total_sent || 0)}
        totalFailed={Number(stats.total_failed || 0)}
        totalPending={Number(stats.total_pending || 0)}
        successRate={Number(stats.success_rate || 0)}
      />

      <NotificationCharts
        series={stats.daily_counts || []}
        channelBreakdown={channelBreakdown}
        providerBreakdown={providerBreakdown}
      />

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        <Card className="rounded-2xl border border-border/70 bg-white p-5 shadow-sm">
          <h3 className="text-sm font-semibold">Recent Failures</h3>
          <div className="mt-3 space-y-2">
            {(data?.recent_failures || []).length === 0 ? (
              <p className="text-xs text-muted-foreground">No failures found.</p>
            ) : (
              (data?.recent_failures || []).map((row: any) => (
                <div key={row.id} className="rounded-lg border border-border/70 p-3 text-xs">
                  <p className="font-semibold text-foreground truncate">{row.recipient || 'Unknown recipient'}</p>
                  <p className="text-muted-foreground truncate">{row.subject || 'No subject'}</p>
                  <p className="text-red-600 truncate">{row.error_message || 'Delivery failed'}</p>
                </div>
              ))
            )}
          </div>
        </Card>

        <Card className="rounded-2xl border border-border/70 bg-white p-5 shadow-sm">
          <h3 className="text-sm font-semibold">Template Usage</h3>
          <div className="mt-3 space-y-2">
            {(data?.template_usage || []).length === 0 ? (
              <p className="text-xs text-muted-foreground">No template usage available.</p>
            ) : (
              (data?.template_usage || []).map((row: any) => (
                <div key={row.template_code} className="grid grid-cols-4 gap-2 rounded-lg border border-border/70 p-3 text-xs">
                  <p className="col-span-2 font-semibold truncate">{row.template_code}</p>
                  <p className="text-emerald-700">S {row.success_count}</p>
                  <p className="text-red-600">F {row.failure_count}</p>
                </div>
              ))
            )}
          </div>
        </Card>
      </div>

      <section className="space-y-3">
        <h2 className="text-lg font-semibold">Provider Status</h2>
        <ProviderStatusCards providers={data?.provider_status || []} testingId={testingId} onTest={handleTestProvider} />
      </section>

      {loading ? (
        <div className="rounded-xl border border-border bg-white p-5 text-sm text-muted-foreground">Loading notification dashboard...</div>
      ) : null}
    </div>
  );
};
