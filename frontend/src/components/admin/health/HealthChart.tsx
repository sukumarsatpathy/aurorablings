import { useMemo } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import type { HealthTrendPoint } from '@/types/health';
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

interface HealthChartProps {
  data: HealthTrendPoint[];
}

const toShortTime = (timestamp: string) =>
  new Intl.DateTimeFormat(undefined, { hour: '2-digit', minute: '2-digit' }).format(new Date(timestamp));

export function HealthChart({ data }: HealthChartProps) {
  const chartData = useMemo(
    () =>
      data.map((point) => ({
        ...point,
        time: toShortTime(point.timestamp),
      })),
    [data],
  );

  return (
    <Card className="min-w-0 border-border/60 bg-card/95">
      <CardHeader className="pb-2">
        <CardTitle className="text-base text-foreground">Health Trend History</CardTitle>
        <p className="text-xs text-muted-foreground">Failures and latency over time</p>
      </CardHeader>
      <CardContent>
        <div className="h-72 w-full min-w-0">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartData} margin={{ left: 0, right: 8, top: 12, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgb(148 163 184 / 0.2)" />
              <XAxis dataKey="time" tickLine={false} axisLine={false} tick={{ fontSize: 12, fill: '#64748b' }} />
              <YAxis yAxisId="left" tickLine={false} axisLine={false} tick={{ fontSize: 12, fill: '#64748b' }} />
              <YAxis
                yAxisId="right"
                orientation="right"
                tickLine={false}
                axisLine={false}
                tick={{ fontSize: 12, fill: '#64748b' }}
              />
              <Tooltip
                contentStyle={{
                  borderRadius: '12px',
                  border: '1px solid rgba(148, 163, 184, 0.25)',
                  background: 'rgba(255,255,255,0.96)',
                  boxShadow: '0 10px 30px rgba(15, 23, 42, 0.08)',
                }}
              />
              <Legend />
              <Line
                yAxisId="left"
                type="monotone"
                dataKey="failures"
                stroke="#f97316"
                strokeWidth={2}
                dot={false}
                name="Failures"
              />
              <Line
                yAxisId="right"
                type="monotone"
                dataKey="latency"
                stroke="#16a34a"
                strokeWidth={2}
                dot={false}
                name="Latency (ms)"
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  );
}
