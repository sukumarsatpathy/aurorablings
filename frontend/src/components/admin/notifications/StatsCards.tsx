import React from 'react';
import { Card } from '@/components/ui/Card';

interface Props {
  totalSent: number;
  totalFailed: number;
  totalPending: number;
  successRate: number;
}

export const StatsCards: React.FC<Props> = ({ totalSent, totalFailed, totalPending, successRate }) => {
  const cards = [
    { label: 'Total Sent', value: totalSent, accent: 'text-emerald-700' },
    { label: 'Failed', value: totalFailed, accent: 'text-red-600' },
    { label: 'Pending', value: totalPending, accent: 'text-amber-600' },
    { label: 'Success Rate', value: `${successRate}%`, accent: 'text-primary' },
  ];

  return (
    <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
      {cards.map((card) => (
        <Card key={card.label} className="rounded-2xl border border-border/70 bg-white p-5 shadow-sm">
          <p className="text-xs uppercase tracking-wide text-muted-foreground">{card.label}</p>
          <p className={`mt-2 text-2xl font-bold ${card.accent}`}>{card.value}</p>
        </Card>
      ))}
    </div>
  );
};
