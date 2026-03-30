import React from 'react';
import { Card } from '@/components/ui/Card';

interface Point {
  day: string;
  total: number;
  failed: number;
}

interface BreakdownItem {
  key: string;
  count: number;
}

interface Props {
  series: Point[];
  channelBreakdown: BreakdownItem[];
  providerBreakdown: BreakdownItem[];
}

const TinyBars: React.FC<{ items: BreakdownItem[] }> = ({ items }) => {
  const max = Math.max(1, ...items.map((item) => item.count));
  return (
    <div className="space-y-2">
      {items.slice(0, 6).map((item) => (
        <div key={item.key} className="space-y-1">
          <div className="flex items-center justify-between text-xs">
            <span className="uppercase text-muted-foreground">{item.key}</span>
            <span className="font-semibold text-foreground">{item.count}</span>
          </div>
          <div className="h-2 rounded bg-muted">
            <div className="h-2 rounded bg-primary" style={{ width: `${(item.count / max) * 100}%` }} />
          </div>
        </div>
      ))}
    </div>
  );
};

export const NotificationCharts: React.FC<Props> = ({ series, channelBreakdown, providerBreakdown }) => {
  const maxSeries = Math.max(1, ...series.map((p) => p.total));

  return (
    <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
      <Card className="rounded-2xl border border-border/70 bg-white p-5 shadow-sm xl:col-span-2">
        <h3 className="text-sm font-semibold">Notifications Over Time</h3>
        <div className="mt-4 flex h-40 items-end gap-2">
          {series.slice(-14).map((point) => (
            <div key={point.day} className="flex flex-1 flex-col items-center gap-1">
              <div className="relative flex h-32 w-full items-end rounded bg-muted/40">
                <div className="w-full rounded bg-primary/85" style={{ height: `${(point.total / maxSeries) * 100}%` }} />
                <div className="absolute bottom-0 right-0 left-0 bg-red-500/40" style={{ height: `${(point.failed / maxSeries) * 100}%` }} />
              </div>
              <span className="text-[10px] text-muted-foreground">{point.day.slice(5)}</span>
            </div>
          ))}
        </div>
      </Card>

      <Card className="rounded-2xl border border-border/70 bg-white p-5 shadow-sm">
        <h3 className="text-sm font-semibold">Channel Distribution</h3>
        <div className="mt-3">
          <TinyBars items={channelBreakdown} />
        </div>
      </Card>

      <Card className="rounded-2xl border border-border/70 bg-white p-5 shadow-sm xl:col-span-3">
        <h3 className="text-sm font-semibold">Provider Distribution</h3>
        <div className="mt-3">
          <TinyBars items={providerBreakdown} />
        </div>
      </Card>
    </div>
  );
};
