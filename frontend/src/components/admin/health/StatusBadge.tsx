import { Badge } from '@/components/ui/Badge';
import { cn } from '@/lib/utils';
import type { HealthStatus } from '@/types/health';

const statusConfig: Record<HealthStatus, { label: string; className: string }> = {
  healthy: {
    label: 'Healthy',
    className: 'border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-500/40 dark:bg-emerald-500/10 dark:text-emerald-300',
  },
  warning: {
    label: 'Warning',
    className: 'border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-500/40 dark:bg-amber-500/10 dark:text-amber-300',
  },
  degraded: {
    label: 'Degraded',
    className: 'border-orange-200 bg-orange-50 text-orange-700 dark:border-orange-500/40 dark:bg-orange-500/10 dark:text-orange-300',
  },
  down: {
    label: 'Down',
    className: 'border-red-200 bg-red-50 text-red-700 dark:border-red-500/40 dark:bg-red-500/10 dark:text-red-300',
  },
};

interface StatusBadgeProps {
  status: HealthStatus;
  className?: string;
}

export function StatusBadge({ status, className }: StatusBadgeProps) {
  const config = statusConfig[status];
  const shouldPulse = status === 'degraded' || status === 'down';

  return (
    <Badge
      variant="outline"
      className={cn('border px-2.5 py-1 text-[11px] font-semibold uppercase tracking-wide', config.className, className)}
    >
      <span className="flex items-center gap-1.5">
        <span className={cn('h-1.5 w-1.5 rounded-full bg-current', shouldPulse ? 'animate-pulse' : '')} />
        {config.label}
      </span>
    </Badge>
  );
}
