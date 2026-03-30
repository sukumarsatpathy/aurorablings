import { useEffect, useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  Activity,
  RefreshCw,
  Server,
  ShieldCheck,
  WalletCards,
  Wifi,
} from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { Card, CardContent } from '@/components/ui/Card';
import { Skeleton } from '@/components/ui/Skeleton';
import {
  AlertsPanel,
  HealthCard,
  HealthChart,
  IncidentTimeline,
  HealthSection,
  SummaryCard,
  StatusBadge,
} from '@/components/admin/health';
import healthService from '@/services/api/health';
import type { HealthAlert, HealthDashboardData } from '@/types/health';

interface ToastState {
  title: string;
  message: string;
}

const toDateTime = (value: string) =>
  new Intl.DateTimeFormat(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  }).format(new Date(value));

const copyText = async (text: string) => {
  if (!navigator?.clipboard?.writeText) return false;
  await navigator.clipboard.writeText(text);
  return true;
};

export function HealthDashboard() {
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [toast, setToast] = useState<ToastState | null>(null);
  const [alertFilter, setAlertFilter] = useState<'all' | HealthAlert['status']>('all');

  useEffect(() => {
    const timer = window.setTimeout(() => setToast(null), 2400);
    return () => window.clearTimeout(timer);
  }, [toast]);

  const { data, isLoading, isFetching, refetch } = useQuery<HealthDashboardData>({
    queryKey: ['admin-health-dashboard'],
    queryFn: () => healthService.getDashboard(),
    refetchInterval: autoRefresh ? 30_000 : false,
  });

  const summaryCards = useMemo(() => {
    if (!data) return [];
    return [
      {
        title: 'Overall Status',
        description: data.summary.overallDescription,
        status: data.summary.overallStatus,
        icon: ShieldCheck,
      },
      {
        title: 'Server Health',
        description: data.summary.serverHealth.description,
        status: data.summary.serverHealth.status,
        icon: Server,
      },
      {
        title: 'API Health',
        description: data.summary.apiHealth.description,
        status: data.summary.apiHealth.status,
        icon: Wifi,
      },
      {
        title: 'Payment Health',
        description: data.summary.paymentHealth.description,
        status: data.summary.paymentHealth.status,
        icon: WalletCards,
      },
    ];
  }, [data]);

  const lastUpdatedText = data ? toDateTime(data.summary.updatedAt) : 'Waiting for data...';

  const filteredAlerts = useMemo(() => {
    const source = data?.alerts ?? [];
    if (alertFilter === 'all') return source;
    return source.filter((alert) => alert.status === alertFilter);
  }, [alertFilter, data?.alerts]);

  const incidentTimeline = useMemo(() => {
    const fromAlerts = (data?.alerts ?? []).map((alert) => ({
      ...alert,
      timestampValue: new Date(alert.timestamp).getTime(),
    }));

    const synthetic = (data?.detailed.trends ?? [])
      .filter((point) => point.failures > 0)
      .map((point, index) => ({
        id: `trend-incident-${index}`,
        status: 'warning' as const,
        title: `Failure spike detected (${point.failures})`,
        message: `Latency ${Math.round(point.latency)}ms with ${point.failures} failures in this interval.`,
        timestamp: point.timestamp,
        timestampValue: new Date(point.timestamp).getTime(),
      }));

    return [...fromAlerts, ...synthetic]
      .sort((a, b) => b.timestampValue - a.timestampValue)
      .slice(0, 8)
      .map(({ timestampValue, ...incident }) => incident);
  }, [data?.alerts, data?.detailed.trends]);

  const tooltips = useMemo<Record<string, string>>(
    () => ({
      CPU: 'Tracks processor utilization across application workers.',
      Memory: 'Measures RAM pressure and swap risk on compute nodes.',
      Disk: 'Shows active storage usage and I/O saturation signals.',
      Database: 'Represents DB query latency and connection stability.',
      Redis: 'Checks cache hit latency and queue responsiveness.',
      'Product API': 'Endpoint health for product listing and detail APIs.',
      'Cart API': 'Monitors cart read/write latency and status responses.',
      'Checkout API': 'Tracks checkout orchestration and order creation latency.',
      'Admin API': 'Monitors admin backend endpoints used by dashboard flows.',
      'Cashfree Config': 'Validates credentials and required gateway configuration.',
      'Cashfree Connectivity': 'Checks live network communication with Cashfree.',
      'Webhook Health': 'Tracks webhook delivery success and signature validation.',
      'Payment Trend': 'Aggregated payment success/failure performance over time.',
    }),
    [],
  );

  const handleRefresh = async () => {
    await refetch();
    setToast({ title: 'Dashboard refreshed', message: 'Latest health snapshot loaded' });
  };

  const handleCopyMessage = async (value: string) => {
    try {
      const copied = await copyText(value);
      setToast({
        title: copied ? 'Copied' : 'Clipboard unavailable',
        message: copied ? 'Message copied to clipboard' : 'Your browser blocked clipboard access',
      });
    } catch {
      setToast({ title: 'Copy failed', message: 'Unable to copy message right now' });
    }
  };

  return (
    <div className="space-y-6 overflow-x-hidden pb-8">
      <header className="rounded-2xl border border-border/60 bg-card/80 p-4 shadow-soft backdrop-blur-sm sm:p-5">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div className="space-y-2">
            <h1 className="text-2xl font-bold tracking-tight text-foreground">System Health</h1>
            <p className="text-sm text-muted-foreground">Real-time monitoring of Aurora Blings platform</p>
            <div className="flex flex-wrap items-center gap-2">
              <StatusBadge status={data?.summary.overallStatus ?? 'healthy'} />
              <p className="text-xs text-muted-foreground">Last updated: {lastUpdatedText}</p>
            </div>
          </div>

          <div className="grid grid-cols-1 gap-2 sm:flex sm:flex-wrap sm:items-center sm:justify-end">
            <Button
              type="button"
              size="sm"
              variant={autoRefresh ? 'default' : 'outline'}
              className="rounded-lg px-3 sm:w-auto"
              onClick={() => setAutoRefresh((previous) => !previous)}
            >
              <Activity className="mr-1.5 h-4 w-4" />
              Auto refresh {autoRefresh ? 'on' : 'off'}
            </Button>
            <Button type="button" size="sm" className="rounded-lg px-3 sm:w-auto" onClick={handleRefresh}>
              <RefreshCw className={`mr-1.5 h-4 w-4 ${isFetching ? 'animate-spin' : ''}`} />
              Refresh
            </Button>
          </div>
        </div>
      </header>

      <section className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
        {isLoading
          ? Array.from({ length: 4 }).map((_, index) => (
              <Card key={`summary-skeleton-${index}`}>
                <CardContent className="space-y-3 p-5">
                  <Skeleton className="h-10 w-10 rounded-xl" />
                  <Skeleton className="h-4 w-24" />
                  <Skeleton className="h-3 w-full" />
                </CardContent>
              </Card>
            ))
          : summaryCards.map((card) => <SummaryCard key={card.title} {...card} />)}
      </section>

      <HealthSection title="Server Health" description="Infrastructure uptime, usage, and storage health">
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-5">
          {isLoading
            ? Array.from({ length: 5 }).map((_, index) => (
                <Card key={`server-skeleton-${index}`}>
                  <CardContent className="space-y-3 p-4">
                    <Skeleton className="h-4 w-20" />
                    <Skeleton className="h-6 w-16" />
                    <Skeleton className="h-3 w-full" />
                  </CardContent>
                </Card>
              ))
            : (data?.detailed.server ?? []).map((item) => (
                <HealthCard
                  key={item.id}
                  item={item}
                  tooltipText={tooltips[item.name]}
                  onCopyMessage={handleCopyMessage}
                />
              ))}
        </div>
      </HealthSection>

      <HealthSection title="API Health" description="Request latency, response codes, and endpoint stability">
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
          {isLoading
            ? Array.from({ length: 4 }).map((_, index) => (
                <Card key={`api-skeleton-${index}`}>
                  <CardContent className="space-y-3 p-4">
                    <Skeleton className="h-4 w-24" />
                    <Skeleton className="h-6 w-16" />
                    <Skeleton className="h-3 w-full" />
                  </CardContent>
                </Card>
              ))
            : (data?.detailed.api ?? []).map((item) => (
                <HealthCard
                  key={item.id}
                  item={item}
                  tooltipText={tooltips[item.name]}
                  onCopyMessage={handleCopyMessage}
                />
              ))}
        </div>
      </HealthSection>

      <HealthSection title="Payment Health" description="Cashfree configuration, connectivity, webhooks, and payment trend">
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
          {isLoading
            ? Array.from({ length: 4 }).map((_, index) => (
                <Card key={`payment-skeleton-${index}`}>
                  <CardContent className="space-y-3 p-4">
                    <Skeleton className="h-4 w-28" />
                    <Skeleton className="h-6 w-16" />
                    <Skeleton className="h-3 w-full" />
                  </CardContent>
                </Card>
              ))
            : (data?.detailed.payment ?? []).map((item) => (
                <HealthCard
                  key={item.id}
                  item={item}
                  tooltipText={tooltips[item.name]}
                  onCopyMessage={handleCopyMessage}
                />
              ))}
        </div>
      </HealthSection>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-6">
        <div className="min-w-0 xl:col-span-2">
          <AlertsPanel
            alerts={filteredAlerts}
            onCopy={handleCopyMessage}
            filter={alertFilter}
            onFilterChange={setAlertFilter}
          />
        </div>
        <div className="min-w-0 xl:col-span-4">
          <HealthChart data={data?.detailed.trends ?? []} />
        </div>
      </div>

      <IncidentTimeline incidents={incidentTimeline} />

      {toast ? (
        <div className="fixed bottom-4 left-4 right-4 z-50 rounded-xl border border-border/60 bg-background/95 px-4 py-3 shadow-premium backdrop-blur-sm sm:left-auto sm:right-6 sm:w-auto">
          <p className="text-sm font-semibold text-foreground">{toast.title}</p>
          <p className="text-xs text-muted-foreground">{toast.message}</p>
        </div>
      ) : null}
    </div>
  );
}
