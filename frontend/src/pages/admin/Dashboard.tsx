import React, { useEffect, useMemo, useState } from 'react';
import { StatCard } from '@/components/admin/StatCard';
import { ActivityRing, BarChart, MiniLineChart } from '@/components/admin/Charts';
import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Package, ShieldCheck, Percent } from 'lucide-react';
import { useCurrency } from '@/hooks/useCurrency';
import dashboardService, { type DashboardResponse, type DashboardRange } from '@/services/api/dashboard';

const RANGE_OPTIONS: Array<{ value: DashboardRange; label: string }> = [
  { value: 'today', label: 'Today' },
  { value: 'yesterday', label: 'Yesterday' },
  { value: 'day_before_yesterday', label: 'Day Before Yesterday' },
  { value: 'last_month', label: 'Last Month' },
  { value: 'custom', label: 'Custom Date Range' },
];

const toTitle = (value: string) => value.replace(/_/g, ' ').replace(/\b\w/g, (m) => m.toUpperCase());

export const Dashboard: React.FC = () => {
  const { formatCurrency } = useCurrency();
  const [loading, setLoading] = useState(true);
  const [dashboard, setDashboard] = useState<DashboardResponse | null>(null);

  const [range, setRange] = useState<DashboardRange>('today');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');

  const loadDashboard = async () => {
    try {
      setLoading(true);
      const params: Record<string, string | number> = { range };
      // Send timezone offset in minutes (positive for ahead of UTC).
      params.tz_offset = -new Date().getTimezoneOffset();
      if (range === 'custom') {
        if (dateFrom) params.date_from = dateFrom;
        if (dateTo) params.date_to = dateTo;
      }
      const response = await dashboardService.getAdminDashboard(params);
      setDashboard(response?.data ?? null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadDashboard();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const revenueSeries = useMemo(() => dashboard?.charts?.revenue?.map((p) => p.value) ?? [], [dashboard]);
  const ordersSeries = useMemo(() => dashboard?.charts?.orders?.map((p) => p.value) ?? [], [dashboard]);

  const rangeLabel = dashboard?.range?.label || RANGE_OPTIONS.find((o) => o.value === range)?.label || 'Today';

  const recentOrders = dashboard?.recent_orders ?? [];
  const recentStock = dashboard?.recent_stock ?? [];
  const shippingOrders = dashboard?.shipping_orders ?? [];
  const couponUsage = dashboard?.coupon_usage ?? [];
  const referral = dashboard?.referral;

  const totalRevenue = dashboard?.summary?.total_revenue ?? '0';
  const totalOrders = dashboard?.summary?.total_orders ?? 0;
  const shippingCount = dashboard?.summary?.shipping_orders ?? 0;
  const couponCount = dashboard?.summary?.coupon_uses ?? 0;
  const lowStockCount = dashboard?.summary?.low_stock_count ?? 0;

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-foreground">Overview</h1>
          <p className="text-xs text-muted-foreground mt-1">Live operational snapshot from the Aurora Blings database.</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <select
            className="h-10 rounded-md border border-border/60 bg-white px-3 text-sm"
            value={range}
            onChange={(e) => setRange(e.target.value as DashboardRange)}
          >
            {RANGE_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </select>
          {range === 'custom' ? (
            <div className="flex items-center gap-2">
              <Input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} className="h-10" />
              <Input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} className="h-10" />
            </div>
          ) : null}
          <Button onClick={loadDashboard} className="h-10 px-4">Apply</Button>
          <Badge variant="surface" className="font-medium px-3 py-1">{rangeLabel}</Badge>
        </div>
      </div>

      {/* Top Metrics Row */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          variant="primary"
          label="Total Revenue"
          value={formatCurrency(Number(totalRevenue || 0))}
          trend={{ value: 0, label: 'current range', isPositive: true }}
        >
          <BarChart values={revenueSeries.length ? revenueSeries.slice(-7) : [5, 8, 6, 9, 7, 10, 8]} />
        </StatCard>

        <StatCard
          variant="cyan"
          label="Total Orders"
          value={totalOrders}
          trend={{ value: 0, label: 'current range', isPositive: true }}
        >
          <ActivityRing pct={Math.min(1, totalOrders ? 0.75 : 0)} size={54} />
        </StatCard>

        <StatCard
          variant="purple"
          label="Shipping Orders"
          value={shippingCount}
          trend={{ value: 0, label: 'current range', isPositive: true }}
        >
          <BarChart values={ordersSeries.length ? ordersSeries.slice(-7) : [3, 4, 2, 5, 4, 3, 5]} color="#ffffff" />
        </StatCard>

        <StatCard
          variant="default"
          label="Coupons Used"
          value={couponCount}
          trend={{ value: 0, label: 'current range', isPositive: true }}
        >
          <div className="w-12 h-12 rounded-full bg-primary/10 flex items-center justify-center text-primary">
            <Percent size={22} />
          </div>
        </StatCard>
      </div>

      {/* Main Content */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Card className="p-5 rounded-[14px] shadow-sm">
              <div className="flex justify-between items-start mb-4">
                <div>
                  <div className="text-xs font-medium text-muted-foreground mb-1">Revenue Trend</div>
                  <div className="text-lg font-bold">{formatCurrency(Number(totalRevenue || 0))}</div>
                </div>
              </div>
              <div className="-ml-2">
                <MiniLineChart color="#517b4b" points={revenueSeries.length ? revenueSeries : [5, 7, 6, 8, 7, 6, 9]} w={300} h={80} />
              </div>
            </Card>

            <Card className="p-5 rounded-[14px] shadow-sm">
              <div className="flex justify-between items-start mb-4">
                <div>
                  <div className="text-xs font-medium text-muted-foreground mb-1">Orders Trend</div>
                  <div className="text-lg font-bold">{totalOrders}</div>
                </div>
              </div>
              <div className="-ml-2">
                <MiniLineChart color="#c8a97e" points={ordersSeries.length ? ordersSeries : [2, 4, 3, 5, 4, 3, 6]} w={300} h={80} />
              </div>
            </Card>
          </div>

          <Card className="p-5 rounded-[14px] shadow-sm">
            <div className="flex justify-between items-center mb-6">
              <div className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Recent Orders</div>
              <Badge variant="surface" className="text-[10px]">{recentOrders.length} Orders</Badge>
            </div>
            <div className="space-y-4">
              {recentOrders.length === 0 ? (
                <div className="text-xs text-muted-foreground">No recent orders in this range.</div>
              ) : (
                recentOrders.map((order) => (
                  <div key={order.id} className="flex items-center justify-between p-3 rounded-xl bg-muted/30 border border-border/50">
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-lg bg-white border border-border flex items-center justify-center text-primary">
                        <Package size={14} />
                      </div>
                      <div>
                        <div className="text-xs font-bold">#{order.order_number}</div>
                        <div className="text-[10px] text-muted-foreground">{order.user__email || 'Guest'} • {toTitle(order.status)}</div>
                      </div>
                    </div>
                    <div className="text-sm font-bold text-primary">{formatCurrency(Number(order.grand_total || 0))}</div>
                  </div>
                ))
              )}
            </div>
          </Card>

          <Card className="p-5 rounded-[14px] shadow-sm">
            <div className="flex justify-between items-center mb-6">
              <div className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Discount Coupons Used</div>
              <Badge variant="surface" className="text-[10px]">{couponCount} Uses</Badge>
            </div>
            <div className="space-y-3">
              {couponUsage.length === 0 ? (
                <div className="text-xs text-muted-foreground">No coupon usage recorded in this range.</div>
              ) : (
                couponUsage.map((usage) => (
                  <div key={usage.id} className="flex items-center justify-between p-3 rounded-xl bg-muted/30 border border-border/50">
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-lg bg-white border border-border flex items-center justify-center text-primary">
                        <Percent size={14} />
                      </div>
                      <div>
                        <div className="text-xs font-bold">{usage.coupon__code}</div>
                        <div className="text-[10px] text-muted-foreground">{usage.user__email || 'Guest'} • Order {usage.order__order_number || '-'}</div>
                      </div>
                    </div>
                    <div className="text-sm font-bold text-primary">{formatCurrency(Number(usage.discount_amount || 0))}</div>
                  </div>
                ))
              )}
            </div>
          </Card>
        </div>

        <div className="space-y-6">
          <Card className="p-5 rounded-[14px] shadow-sm flex flex-col items-center">
            <div className="w-16 h-16 rounded-full bg-primary/10 flex items-center justify-center text-primary mb-3">
              <ShieldCheck size={28} />
            </div>
            <div className="text-sm font-bold">System Snapshot</div>
            <div className="text-[11px] text-muted-foreground text-center mt-1 mb-4">
              Low stock alerts and fulfillment updates for the selected range.
            </div>
            <div className="grid grid-cols-2 w-full gap-2 text-center border-t border-border pt-4">
              <div>
                <div className="text-lg font-bold text-foreground">{lowStockCount}</div>
                <div className="text-[10px] text-muted-foreground">Low Stock</div>
              </div>
              <div>
                <div className="text-lg font-bold text-foreground">{shippingCount}</div>
                <div className="text-[10px] text-muted-foreground">Shipping</div>
              </div>
            </div>
          </Card>

          <Card className="p-5 rounded-[14px] shadow-sm">
            <div className="flex justify-between items-center mb-4">
              <div className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Recent Stock Items</div>
              <Badge variant="surface" className="text-[10px]">{recentStock.length} Items</Badge>
            </div>
            <div className="space-y-3">
              {recentStock.length === 0 ? (
                <div className="text-xs text-muted-foreground">No inventory updates yet.</div>
              ) : (
                recentStock.map((stock) => (
                  <div key={stock.id} className="flex items-center justify-between text-xs border-b border-border/60 pb-2 last:border-0 last:pb-0">
                    <div>
                      <div className="font-semibold">{stock.variant__product__name}</div>
                      <div className="text-[10px] text-muted-foreground">{stock.variant__sku} • {stock.warehouse__code}</div>
                    </div>
                    <div className="font-bold">{stock.available}</div>
                  </div>
                ))
              )}
            </div>
          </Card>

          <Card className="p-5 rounded-[14px] shadow-sm">
            <div className="flex justify-between items-center mb-4">
              <div className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Shipping Orders</div>
              <Badge variant="surface" className="text-[10px]">{shippingOrders.length} Active</Badge>
            </div>
            <div className="space-y-3">
              {shippingOrders.length === 0 ? (
                <div className="text-xs text-muted-foreground">No shipping orders in this range.</div>
              ) : (
                shippingOrders.map((order) => (
                  <div key={order.id} className="flex items-center justify-between text-xs border-b border-border/60 pb-2 last:border-0 last:pb-0">
                    <div>
                      <div className="font-semibold">#{order.order_number}</div>
                      <div className="text-[10px] text-muted-foreground">{order.shipping_carrier || 'Carrier TBD'} • {order.tracking_number || '-'}</div>
                    </div>
                    <div className="font-bold">{toTitle(order.status)}</div>
                  </div>
                ))
              )}
            </div>
          </Card>

          <div className="bg-[#7c6fd4] text-white rounded-[14px] p-5 text-center relative overflow-hidden">
            <div className="absolute top-0 right-0 w-32 h-32 bg-white/10 rounded-full -translate-y-1/2 translate-x-1/3 blur-2xl" />
            <div className="text-xs font-bold mb-4 relative z-10">Referral Program</div>
            <div className="grid grid-cols-3 gap-3 text-[11px] relative z-10">
              <div>
                <div className="text-lg font-bold">{formatCurrency(Number(referral?.revenue || 0))}</div>
                <div className="text-white/70">Revenue</div>
              </div>
              <div>
                <div className="text-lg font-bold">{formatCurrency(Number(referral?.user_earning || 0))}</div>
                <div className="text-white/70">User Earn</div>
              </div>
              <div>
                <div className="text-lg font-bold">{formatCurrency(Number(referral?.referrer_earning || 0))}</div>
                <div className="text-white/70">Referrer Earn</div>
              </div>
            </div>
            <div className="mt-4 flex justify-center">
              <ActivityRing pct={referral?.revenue && Number(referral.revenue) > 0 ? 0.6 : 0.15} size={90} className="w-20 h-20" />
            </div>
            <div className="mt-3 text-[10px] text-white/70">Top referrers will appear here once referrals are enabled.</div>
          </div>
        </div>
      </div>

      {loading ? (
        <div className="rounded-[14px] border border-border bg-white p-8 text-center text-sm text-muted-foreground">Loading dashboard data...</div>
      ) : null}
    </div>
  );
};
