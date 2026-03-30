import { AlertTriangle, Copy, Siren } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import type { HealthAlert, HealthStatus } from '@/types/health';
import { StatusBadge } from '@/components/admin/health/StatusBadge';

interface AlertsPanelProps {
  alerts: HealthAlert[];
  onCopy: (text: string) => void;
  filter: 'all' | Extract<HealthStatus, 'warning' | 'degraded' | 'down'>;
  onFilterChange: (value: 'all' | Extract<HealthStatus, 'warning' | 'degraded' | 'down'>) => void;
}

const toDateTime = (value: string) =>
  new Intl.DateTimeFormat(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(value));

export function AlertsPanel({ alerts, onCopy, filter, onFilterChange }: AlertsPanelProps) {
  const filterButtons: Array<{
    label: string;
    value: 'all' | Extract<HealthStatus, 'warning' | 'degraded' | 'down'>;
  }> = [
    { label: 'All', value: 'all' },
    { label: 'Warning', value: 'warning' },
    { label: 'Degraded', value: 'degraded' },
    { label: 'Down', value: 'down' },
  ];

  return (
    <Card className="border-border/60 bg-card/95">
      <CardHeader className="space-y-3 pb-3">
        <div className="flex items-center gap-2">
          <Siren className="h-4 w-4 text-muted-foreground" />
          <CardTitle className="text-base text-foreground">Active Alerts</CardTitle>
        </div>
        <div className="flex flex-wrap gap-2">
          {filterButtons.map((item) => (
            <Button
              key={item.value}
              type="button"
              size="sm"
              variant={filter === item.value ? 'secondary' : 'ghost'}
              className="h-7 rounded-full px-2.5 text-[11px]"
              onClick={() => onFilterChange(item.value)}
            >
              {item.label}
            </Button>
          ))}
        </div>
      </CardHeader>
      <CardContent className="space-y-3 pt-0">
        {!alerts.length ? (
          <div className="rounded-xl border border-dashed border-border/80 bg-muted/20 p-4 text-sm text-muted-foreground">
            No active alerts right now.
          </div>
        ) : null}

        {alerts.map((alert) => (
          <article
            key={alert.id}
            className="rounded-xl border border-border/60 bg-background/80 p-4 transition-all duration-300 hover:shadow-soft"
          >
            <div className="mb-2 flex items-start justify-between gap-3">
              <div className="flex items-start gap-2">
                <AlertTriangle className="mt-0.5 h-4 w-4 text-amber-500" />
                <div>
                  <p className="text-sm font-semibold text-foreground">{alert.title}</p>
                  <p className="text-xs text-muted-foreground">{toDateTime(alert.timestamp)}</p>
                </div>
              </div>
              <StatusBadge status={alert.status} />
            </div>
            <p className="text-sm text-muted-foreground">{alert.message}</p>
            <div className="mt-3">
              <Button
                type="button"
                size="sm"
                variant="ghost"
                className="h-8 rounded-lg px-2.5 text-xs text-muted-foreground hover:text-foreground"
                onClick={() => onCopy(alert.message)}
              >
                <Copy className="mr-1.5 h-3.5 w-3.5" />
                Copy message
              </Button>
            </div>
          </article>
        ))}
      </CardContent>
    </Card>
  );
}
