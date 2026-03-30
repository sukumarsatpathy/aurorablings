import { AlertTriangle, Clock3 } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { StatusBadge } from '@/components/admin/health/StatusBadge';
import type { HealthAlert } from '@/types/health';

interface IncidentTimelineProps {
  incidents: HealthAlert[];
}

const toDateTime = (value: string) =>
  new Intl.DateTimeFormat(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(value));

export function IncidentTimeline({ incidents }: IncidentTimelineProps) {
  return (
    <Card className="border-border/60 bg-card/95">
      <CardHeader className="pb-3">
        <div className="flex items-center gap-2">
          <Clock3 className="h-4 w-4 text-muted-foreground" />
          <CardTitle className="text-base text-foreground">Incident Timeline</CardTitle>
        </div>
      </CardHeader>
      <CardContent className="pt-0">
        {!incidents.length ? (
          <div className="rounded-xl border border-dashed border-border/80 bg-muted/20 p-4 text-sm text-muted-foreground">
            No incidents recorded in this period.
          </div>
        ) : (
          <ol className="space-y-3">
            {incidents.map((incident) => (
              <li key={incident.id} className="relative rounded-xl border border-border/60 bg-background/80 p-4">
                <div className="absolute bottom-0 left-5 top-0 -z-10 hidden w-px bg-border/70 md:block" />
                <div className="mb-2 flex items-start justify-between gap-2">
                  <div className="flex items-start gap-2">
                    <AlertTriangle className="mt-0.5 h-4 w-4 text-amber-500" />
                    <div>
                      <p className="text-sm font-semibold text-foreground">{incident.title}</p>
                      <p className="text-xs text-muted-foreground">{toDateTime(incident.timestamp)}</p>
                    </div>
                  </div>
                  <StatusBadge status={incident.status} />
                </div>
                <p className="text-sm text-muted-foreground">{incident.message}</p>
              </li>
            ))}
          </ol>
        )}
      </CardContent>
    </Card>
  );
}
