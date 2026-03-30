import React, { useEffect, useMemo, useState } from 'react';
import { Badge } from '@/components/ui/Badge';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { useCurrency } from '@/hooks/useCurrency';
import ordersService, { type CustomerOrderDetail, type CustomerOrderListRow } from '@/services/api/orders';
import profileService, { type ProfileData } from '@/services/api/profile';
import { extractData, extractRows, formatDateTime, formatStatus } from './accountUtils';
import { Link } from 'react-router-dom';

const statusBadgeClass = (status: string) => {
  const value = status.toLowerCase();
  if (['delivered', 'completed', 'paid'].includes(value)) return 'bg-emerald-50 text-emerald-700 border border-emerald-200';
  if (['cancelled', 'failed', 'refunded'].includes(value)) return 'bg-red-50 text-red-700 border border-red-200';
  if (['shipped', 'in_transit', 'out_for_delivery'].includes(value)) return 'bg-sky-50 text-sky-700 border border-sky-200';
  return 'bg-amber-50 text-amber-700 border border-amber-200';
};

export const AccountDashboardPage: React.FC = () => {
  const { formatCurrency } = useCurrency();
  const [loading, setLoading] = useState(true);
  const [profile, setProfile] = useState<ProfileData | null>(null);
  const [orders, setOrders] = useState<CustomerOrderListRow[]>([]);
  const [trackedOrders, setTrackedOrders] = useState<CustomerOrderDetail[]>([]);

  useEffect(() => {
    let mounted = true;
    const load = async () => {
      try {
        setLoading(true);
        const [profilePayload, ordersPayload] = await Promise.all([
          profileService.getProfile(),
          ordersService.listMyOrders(),
        ]);
        if (!mounted) return;

        setProfile(extractData<ProfileData>(profilePayload));
        const rows = extractRows<CustomerOrderListRow>(ordersPayload);
        setOrders(rows);

        const selectedIds = rows.slice(0, 3).map((row) => row.id);
        if (!selectedIds.length) {
          setTrackedOrders([]);
          return;
        }
        const details = await Promise.all(
          selectedIds.map(async (id) => extractData<CustomerOrderDetail>(await ordersService.getMyOrder(id)))
        );
        if (!mounted) return;
        setTrackedOrders(details.filter(Boolean) as CustomerOrderDetail[]);
      } finally {
        if (mounted) setLoading(false);
      }
    };
    void load();
    return () => {
      mounted = false;
    };
  }, []);

  useEffect(() => {
    if (!trackedOrders.length) return;
    let cancelled = false;
    const interval = window.setInterval(async () => {
      try {
        const details = await Promise.all(
          trackedOrders.map(async (order) => extractData<CustomerOrderDetail>(await ordersService.getMyOrder(order.id)))
        );
        if (!cancelled) setTrackedOrders(details.filter(Boolean) as CustomerOrderDetail[]);
      } catch {
        // keep last known shipping snapshot
      }
    }, 25000);
    return () => {
      cancelled = true;
      window.clearInterval(interval);
    };
  }, [trackedOrders]);

  const summary = useMemo(() => {
    const total = orders.length;
    const inTransit = orders.filter((row) => ['shipped', 'in_transit', 'out_for_delivery'].includes(String(row.status || '').toLowerCase())).length;
    const completed = orders.filter((row) => ['delivered', 'completed'].includes(String(row.status || '').toLowerCase())).length;
    const pendingPayment = orders.filter((row) => String(row.payment_status || '').toLowerCase() === 'pending').length;
    return { total, inTransit, completed, pendingPayment };
  }, [orders]);

  const displayName = useMemo(() => {
    const full = `${profile?.first_name || ''} ${profile?.last_name || ''}`.trim();
    return full || profile?.email || 'Customer';
  }, [profile]);

  if (loading) {
    return (
      <Card className="rounded-3xl border-[#517b4b]/15 bg-white p-8 shadow-[0_14px_32px_rgba(81,123,75,0.12)]">
        <p className="text-sm text-muted-foreground">Loading account summary...</p>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      <Card className="rounded-3xl border-[#517b4b]/20 bg-white p-8 shadow-[0_14px_32px_rgba(81,123,75,0.12)]">
        <h2 className="text-2xl font-bold text-[#517b4b]">Welcome back, {displayName}</h2>
        <p className="mt-2 text-sm text-muted-foreground">Here is your latest order and shipping snapshot.</p>
      </Card>

      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <Card className="rounded-2xl border-[#517b4b]/15 bg-white p-5 shadow-[0_10px_24px_rgba(81,123,75,0.1)]">
          <p className="text-xs uppercase text-muted-foreground">Total Orders</p>
          <p className="mt-2 text-2xl font-bold text-[#517b4b]">{summary.total}</p>
        </Card>
        <Card className="rounded-2xl border-[#517b4b]/15 bg-white p-5 shadow-[0_10px_24px_rgba(81,123,75,0.1)]">
          <p className="text-xs uppercase text-muted-foreground">In Transit</p>
          <p className="mt-2 text-2xl font-bold text-[#517b4b]">{summary.inTransit}</p>
        </Card>
        <Card className="rounded-2xl border-[#517b4b]/15 bg-white p-5 shadow-[0_10px_24px_rgba(81,123,75,0.1)]">
          <p className="text-xs uppercase text-muted-foreground">Completed</p>
          <p className="mt-2 text-2xl font-bold text-[#517b4b]">{summary.completed}</p>
        </Card>
        <Card className="rounded-2xl border-[#517b4b]/15 bg-white p-5 shadow-[0_10px_24px_rgba(81,123,75,0.1)]">
          <p className="text-xs uppercase text-muted-foreground">Pending Payment</p>
          <p className="mt-2 text-2xl font-bold text-[#517b4b]">{summary.pendingPayment}</p>
        </Card>
      </div>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        <Card className="rounded-3xl border-[#517b4b]/15 bg-white p-6 shadow-[0_12px_28px_rgba(81,123,75,0.1)]">
          <div className="mb-4 flex items-center justify-between">
            <h3 className="text-lg font-bold text-[#517b4b]">Shipping Status</h3>
            <Badge className="bg-[#517b4b]/10 text-[#517b4b]">Live refresh</Badge>
          </div>
          {!trackedOrders.length ? (
            <p className="text-sm text-muted-foreground">No recent shipments yet.</p>
          ) : (
            <div className="space-y-3">
              {trackedOrders.map((order) => (
                <div key={order.id} className="rounded-2xl border border-border/70 bg-muted/20 p-4">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <p className="font-semibold">Order {order.order_number}</p>
                    <span className={`rounded-full px-3 py-1 text-xs font-semibold ${statusBadgeClass(String(order.shipment?.status || order.status || 'pending'))}`}>
                      {formatStatus(String(order.shipment?.status || order.status || 'pending'))}
                    </span>
                  </div>
                  <div className="mt-2 grid grid-cols-1 gap-2 text-sm text-muted-foreground md:grid-cols-3">
                    <p>AWB: {order.shipment?.awb_code || order.tracking_number || 'N/A'}</p>
                    <p>Courier: {order.shipment?.courier_name || order.shipping_carrier || 'N/A'}</p>
                    <p>Updated: {formatDateTime(order.updated_at)}</p>
                  </div>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {order.shipment?.tracking_url ? (
                      <a href={order.shipment.tracking_url} target="_blank" rel="noreferrer">
                        <Button size="sm" className="rounded-xl bg-[#517b4b] text-white hover:bg-[#456a41]">Track Shipment</Button>
                      </a>
                    ) : null}
                    {order.shipment?.invoice_url ? (
                      <Button
                        size="sm"
                        variant="outline"
                        className="rounded-xl"
                        onClick={() => {
                          void ordersService.downloadInvoice(order.id, order.shipment?.invoice_url || order.invoice_url);
                        }}
                      >
                        Invoice
                      </Button>
                    ) : null}
                  </div>
                </div>
              ))}
            </div>
          )}
        </Card>

        <Card className="rounded-3xl border-[#517b4b]/15 bg-white p-6 shadow-[0_12px_28px_rgba(81,123,75,0.1)]">
          <div className="mb-4 flex items-center justify-between">
            <h3 className="text-lg font-bold text-[#517b4b]">Recent Orders</h3>
            <Link to="/account/orders">
              <Button variant="outline" size="sm" className="rounded-xl">View All</Button>
            </Link>
          </div>
          {!orders.length ? (
            <p className="text-sm text-muted-foreground">You have not placed any orders yet.</p>
          ) : (
            <div className="space-y-3">
              {orders.slice(0, 4).map((row) => (
                <div key={row.id} className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-border/70 bg-muted/20 px-4 py-3">
                  <div>
                    <p className="font-semibold">{row.order_number}</p>
                    <p className="text-xs text-muted-foreground">{formatDateTime(row.placed_at || row.created_at)}</p>
                  </div>
                  <div className="text-right">
                    <p className="font-semibold">{formatCurrency(Number(row.grand_total || 0))}</p>
                    <p className="text-xs text-muted-foreground">{formatStatus(row.status)}</p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>
    </div>
  );
};
