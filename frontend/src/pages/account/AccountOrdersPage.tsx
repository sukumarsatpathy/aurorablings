import React, { useCallback, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { useCurrency } from '@/hooks/useCurrency';
import ordersService, { type CustomerOrderDetail, type CustomerOrderListRow } from '@/services/api/orders';
import { extractData, extractRows, formatDateTime, formatStatus } from './accountUtils';

const statusClass = (status: string) => {
  const value = status.toLowerCase();
  if (['delivered', 'completed', 'paid'].includes(value)) return 'bg-emerald-50 text-emerald-700 border border-emerald-200';
  if (['cancelled', 'failed', 'refunded'].includes(value)) return 'bg-red-50 text-red-700 border border-red-200';
  if (['shipped', 'in_transit', 'out_for_delivery'].includes(value)) return 'bg-sky-50 text-sky-700 border border-sky-200';
  return 'bg-amber-50 text-amber-700 border border-amber-200';
};

export const AccountOrdersPage: React.FC = () => {
  const { formatCurrency } = useCurrency();
  const [loading, setLoading] = useState(true);
  const [orders, setOrders] = useState<CustomerOrderListRow[]>([]);
  const [selectedOrderId, setSelectedOrderId] = useState<string>('');
  const [selectedOrder, setSelectedOrder] = useState<CustomerOrderDetail | null>(null);
  const [detailsLoading, setDetailsLoading] = useState(false);
  const [statusFilter, setStatusFilter] = useState('');
  const [error, setError] = useState('');
  const [invoiceLoading, setInvoiceLoading] = useState(false);

  const loadOrders = useCallback(async () => {
    try {
      setLoading(true);
      setError('');
      const response = await ordersService.listMyOrders(statusFilter ? { status: statusFilter } : undefined);
      const rows = extractRows<CustomerOrderListRow>(response);
      setOrders(rows);
      if (rows.length === 0) {
        setSelectedOrderId('');
        setSelectedOrder(null);
      } else {
        setSelectedOrderId((prev) => prev || rows[0].id);
      }
    } catch (err: any) {
      setError(err?.response?.data?.message || 'Unable to load your orders.');
    } finally {
      setLoading(false);
    }
  }, [statusFilter]);

  const loadOrderDetails = useCallback(async (orderId: string) => {
    try {
      setDetailsLoading(true);
      const response = await ordersService.getMyOrder(orderId);
      setSelectedOrder(extractData<CustomerOrderDetail>(response));
    } catch (err: any) {
      setSelectedOrder(null);
      setError(err?.response?.data?.message || 'Unable to load order details.');
    } finally {
      setDetailsLoading(false);
    }
  }, []);

  React.useEffect(() => {
    void loadOrders();
  }, [loadOrders]);

  React.useEffect(() => {
    if (!selectedOrderId) return;
    void loadOrderDetails(selectedOrderId);
  }, [selectedOrderId, loadOrderDetails]);

  const canCancel = useMemo(() => {
    const current = String(selectedOrder?.status || '').toLowerCase();
    return ['placed', 'pending', 'confirmed'].includes(current);
  }, [selectedOrder?.status]);

  const handleCancelOrder = async () => {
    if (!selectedOrder) return;
    if (!window.confirm('Cancel this order?')) return;
    try {
      setDetailsLoading(true);
      await ordersService.cancelMyOrder(selectedOrder.id);
      await loadOrderDetails(selectedOrder.id);
      await loadOrders();
    } catch (err: any) {
      setError(err?.response?.data?.message || 'Unable to cancel this order.');
    } finally {
      setDetailsLoading(false);
    }
  };

  const downloadInvoice = async () => {
    if (!selectedOrder) return;
    try {
      setInvoiceLoading(true);
      await ordersService.downloadInvoice(selectedOrder.id, selectedOrder.invoice_url);
    } catch (err: any) {
      setError(err?.response?.data?.message || 'Unable to download invoice right now.');
    } finally {
      setInvoiceLoading(false);
    }
  };

  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-[360px_1fr]">
      <Card className="rounded-3xl border-[#517b4b]/15 bg-white p-5 shadow-[0_12px_28px_rgba(81,123,75,0.1)]">
        <div className="mb-4 flex items-center justify-between gap-3">
          <h2 className="text-lg font-bold text-[#517b4b]">My Orders</h2>
          <select
            className="h-9 rounded-lg border border-border bg-white px-2 text-xs"
            value={statusFilter}
            onChange={(event) => setStatusFilter(event.target.value)}
          >
            <option value="">All</option>
            <option value="placed">Placed</option>
            <option value="shipped">Shipped</option>
            <option value="delivered">Delivered</option>
            <option value="cancelled">Cancelled</option>
          </select>
        </div>

        {loading ? <p className="text-sm text-muted-foreground">Loading orders...</p> : null}
        {error ? <p className="mb-2 text-sm text-red-600">{error}</p> : null}

        {!loading && orders.length === 0 ? (
          <p className="text-sm text-muted-foreground">No orders found.</p>
        ) : (
          <div className="max-h-[560px] space-y-2 overflow-auto pr-1">
            {orders.map((order) => (
              <button
                key={order.id}
                type="button"
                onClick={() => setSelectedOrderId(order.id)}
                className={`w-full rounded-xl border p-3 text-left transition-colors ${
                  selectedOrderId === order.id
                    ? 'border-[#517b4b] bg-[#517b4b]/5'
                    : 'border-border/70 bg-muted/20 hover:border-[#517b4b]/30'
                }`}
              >
                <p className="font-semibold">{order.order_number}</p>
                <p className="text-xs text-muted-foreground">{formatDateTime(order.placed_at || order.created_at)}</p>
                <div className="mt-2 flex items-center justify-between text-xs">
                  <span>{formatCurrency(Number(order.grand_total || 0))}</span>
                  <span className={`rounded-full px-2 py-1 font-semibold ${statusClass(order.status)}`}>
                    {formatStatus(order.status)}
                  </span>
                </div>
              </button>
            ))}
          </div>
        )}
      </Card>

      <Card className="rounded-3xl border-[#517b4b]/15 bg-white p-6 shadow-[0_12px_28px_rgba(81,123,75,0.1)]">
        {!selectedOrderId ? (
          <p className="text-sm text-muted-foreground">Select an order to view details.</p>
        ) : detailsLoading ? (
          <p className="text-sm text-muted-foreground">Loading order details...</p>
        ) : !selectedOrder ? (
          <p className="text-sm text-muted-foreground">Order details unavailable.</p>
        ) : (
          <div className="space-y-6">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <h2 className="text-xl font-bold text-[#517b4b]">{selectedOrder.order_number}</h2>
                <p className="text-sm text-muted-foreground">Placed on {formatDateTime(selectedOrder.placed_at || selectedOrder.created_at)}</p>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <Badge className={statusClass(selectedOrder.status)}>{formatStatus(selectedOrder.status)}</Badge>
                <Badge className={statusClass(selectedOrder.payment_status)}>{formatStatus(selectedOrder.payment_status)}</Badge>
              </div>
            </div>

            <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
              <div className="rounded-xl border border-border/70 bg-muted/20 p-4">
                <p className="text-xs uppercase text-muted-foreground">Total</p>
                <p className="mt-1 font-bold">{formatCurrency(Number(selectedOrder.grand_total || 0))}</p>
              </div>
              <div className="rounded-xl border border-border/70 bg-muted/20 p-4">
                <p className="text-xs uppercase text-muted-foreground">Payment Method</p>
                <p className="mt-1 font-bold">{formatStatus(selectedOrder.payment_method)}</p>
              </div>
              <div className="rounded-xl border border-border/70 bg-muted/20 p-4">
                <p className="text-xs uppercase text-muted-foreground">Items</p>
                <p className="mt-1 font-bold">{selectedOrder.item_count || selectedOrder.items?.length || 0}</p>
              </div>
            </div>

            <div className="rounded-2xl border border-border/70 bg-muted/20 p-4">
              <h3 className="mb-2 font-semibold text-[#517b4b]">Shipping & Tracking</h3>
              <div className="grid grid-cols-1 gap-2 text-sm text-muted-foreground md:grid-cols-2">
                <p>Status: {formatStatus(selectedOrder.shipment?.status || selectedOrder.status)}</p>
                <p>AWB: {selectedOrder.shipment?.awb_code || selectedOrder.tracking_number || 'N/A'}</p>
                <p>Courier: {selectedOrder.shipment?.courier_name || selectedOrder.shipping_carrier || 'N/A'}</p>
                <p>Updated: {formatDateTime(selectedOrder.updated_at)}</p>
              </div>
              <div className="mt-3 flex flex-wrap gap-2">
                {selectedOrder.shipment?.tracking_url ? (
                  <a href={selectedOrder.shipment.tracking_url} target="_blank" rel="noreferrer">
                    <Button size="sm" className="rounded-xl bg-[#517b4b] text-white hover:bg-[#456a41]">Track Shipment</Button>
                  </a>
                ) : null}
                <Button
                  size="sm"
                  variant="outline"
                  className="rounded-xl"
                  disabled={invoiceLoading}
                  onClick={downloadInvoice}
                >
                  {invoiceLoading ? 'Preparing Invoice...' : 'Download Invoice'}
                </Button>
                {canCancel ? (
                  <Button size="sm" variant="outline" className="rounded-xl text-red-600" onClick={handleCancelOrder}>
                    Cancel Order
                  </Button>
                ) : null}
              </div>
            </div>

            <div>
              <h3 className="mb-3 font-semibold text-[#517b4b]">Items</h3>
              <div className="space-y-2">
                {(selectedOrder.items || []).map((item) => (
                  <div key={item.id} className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-border/70 bg-white px-3 py-2">
                    <div>
                      <p className="font-medium">{item.product_name}</p>
                      <p className="text-xs text-muted-foreground">
                        {item.variant_name} • SKU {item.sku} • Qty {item.quantity}
                      </p>
                    </div>
                    <div className="flex items-center gap-2">
                      <p className="font-semibold">{formatCurrency(Number(item.line_total || 0))}</p>
                      {item.product_id ? (
                        item.can_review || item.has_reviewed || item.my_review_id ? (
                          <Button asChild size="sm" variant="outline" className="rounded-lg">
                            <Link to={`/product/${item.product_id}?review=1`}>
                              {item.has_reviewed || item.my_review_id ? 'Edit Review' : 'Write Review'}
                            </Link>
                          </Button>
                        ) : (
                          <Button size="sm" variant="outline" className="rounded-lg" disabled title={item.review_eligibility_reason || ''}>
                            Write Review
                          </Button>
                        )
                      ) : null}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </Card>
    </div>
  );
};
