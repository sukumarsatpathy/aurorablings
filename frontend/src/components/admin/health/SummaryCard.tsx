import type { LucideIcon } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/Card';
import { StatusBadge } from '@/components/admin/health/StatusBadge';
import type { HealthStatus } from '@/types/health';

interface SummaryCardProps {
  title: string;
  description: string;
  status: HealthStatus;
  icon: LucideIcon;
}

export function SummaryCard({ title, description, status, icon: Icon }: SummaryCardProps) {
  return (
    <Card className="h-full border-border/60 bg-card/90 backdrop-blur-sm transition-all duration-300 hover:-translate-y-0.5 hover:shadow-premium">
      <CardContent className="space-y-4 p-5">
        <div className="flex items-start justify-between gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-muted/70 text-primary">
            <Icon size={18} />
          </div>
          <StatusBadge status={status} />
        </div>
        <div className="space-y-1.5">
          <p className="text-sm font-semibold text-foreground">{title}</p>
          <p className="text-xs text-muted-foreground">{description}</p>
        </div>
      </CardContent>
    </Card>
  );
}
