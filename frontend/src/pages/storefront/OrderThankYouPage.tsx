import React, { useEffect, useMemo, useState } from 'react';
import { CheckCircle2 } from 'lucide-react';
import { Link, Navigate, useLocation } from 'react-router-dom';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { useCurrency } from '@/hooks/useCurrency';
import apiClient from '@/services/api/client';

type OrderAddress = Record<string, string>;

type OrderItem = {
  id: string;
  sku: string;
  product_name: string;
  variant_name: string;
  quantity: number;
  unit_price: string;
  line_total: string;
};

type ThankYouOrder = {
  order_number?: string;
  status?: string;
  payment_status?: string;
  payment_method?: string;
  created_at?: string;
  shipping_address?: OrderAddress;
  billing_address?: OrderAddress;
  subtotal?: string;
  shipping_cost?: string;
  tax_amount?: string;
  discount_amount?: string;
  grand_total?: string;
  currency?: string;
  notes?: string;
  items?: OrderItem[];
};

const formatAddress = (address: OrderAddress | undefined) => {
  if (!address) return 'N/A';
  const lines = [
    address.full_name,
    address.line1,
    address.line2,
    [address.city, address.state, address.pincode].filter(Boolean).join(', '),
    address.country,
    address.phone ? `Phone: ${address.phone}` : '',
  ]
    .map((value) => String(value || '').trim())
    .filter(Boolean);

  return lines.join('\n');
};

const formatStatus = (value: string | undefined) => {
  if (!value) return 'N/A';
  return value
    .split('_')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
};

export const OrderThankYouPage: React.FC = () => {
  const { formatCurrency } = useCurrency();
  const location = useLocation();
  const orderIdFromQuery = useMemo(() => {
    const params = new URLSearchParams(location.search);
    return String(params.get('order_id') || '').trim();
  }, [location.search]);

  const stateOrder = (location.state as { order?: ThankYouOrder } | null)?.order;
  let cachedOrder: ThankYouOrder | null = null;
  const cachedOrderRaw = sessionStorage.getItem('aurora_last_order');
  if (cachedOrderRaw) {
    try {
      cachedOrder = JSON.parse(cachedOrderRaw) as ThankYouOrder;
    } catch {
      cachedOrder = null;
    }
  }
  const [order, setOrder] = useState<ThankYouOrder | null>(stateOrder || cachedOrder);
  const [syncingPayment, setSyncingPayment] = useState(false);

  useEffect(() => {
    if (!orderIdFromQuery) return;

    let cancelled = false;
    const wait = (ms: number) => new Promise((resolve) => window.setTimeout(resolve, ms));

    const syncOrder = async () => {
      setSyncingPayment(true);
      try {
        for (let attempt = 0; attempt < 10; attempt += 1) {
          try {
            await apiClient.post('/v1/payments/reconcile/', { order_id: orderIdFromQuery });
          } catch {
            // webhook may have already processed; ignore reconcile errors here
          }

          try {
            const response = await apiClient.get(`/v1/orders/${orderIdFromQuery}/`);
            const latest = response?.data?.data || null;
            if (!latest) break;
            if (cancelled) return;
            setOrder(latest);
            sessionStorage.setItem('aurora_last_order', JSON.stringify(latest));

            const paymentStatus = String(latest.payment_status || '').toLowerCase();
            if (paymentStatus === 'paid' || paymentStatus === 'failed' || paymentStatus === 'refunded') {
              break;
            }
          } catch {
            // keep last known cached order if detail call fails
          }

          await wait(3000);
        }
      } finally {
        if (!cancelled) setSyncingPayment(false);
      }
    };

    void syncOrder();
    return () => {
      cancelled = true;
    };
  }, [orderIdFromQuery]);

  if (!order) {
    return <Navigate to="/checkout" replace />;
  }

  const subtotal = Number(order.subtotal || 0);
  const shipping = Number(order.shipping_cost || 0);
  const tax = Number(order.tax_amount || 0);
  const discount = Number(order.discount_amount || 0);
  const total = Number(order.grand_total || 0);

  return (
    <div className="pt-32 pb-24">
      <div className="container mx-auto px-4 max-w-5xl space-y-6">
        <Card className="p-8 rounded-3xl border bg-white/90">
          <div className="flex items-start gap-4">
            <CheckCircle2 className="text-emerald-600 mt-1" size={34} />
            <div>
              <h1 className="text-3xl font-bold">Thank you. Your order is confirmed.</h1>
              <p className="text-muted-foreground mt-1">
                Order {order.order_number || ''} placed successfully.
              </p>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-6 text-sm">
            <div className="rounded-xl border p-4 bg-muted/20">
              <p className="text-muted-foreground">Order Status</p>
              <p className="font-semibold">{formatStatus(order.status)}</p>
            </div>
            <div className="rounded-xl border p-4 bg-muted/20">
              <p className="text-muted-foreground">Payment</p>
              <p className="font-semibold">{formatStatus(order.payment_method)} ({formatStatus(order.payment_status)})</p>
              {syncingPayment ? (
                <p className="text-xs text-muted-foreground mt-1">Syncing latest payment status...</p>
              ) : null}
            </div>
          </div>
        </Card>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <Card className="p-6 rounded-2xl lg:col-span-2 space-y-4">
            <h2 className="text-lg font-bold">Order Items</h2>
            {(order.items || []).length === 0 ? (
              <p className="text-sm text-muted-foreground">No items found in this order.</p>
            ) : (
              <div className="space-y-3">
                {(order.items || []).map((item) => (
                  <div key={item.id} className="flex items-center justify-between border rounded-xl p-3">
                    <div>
                      <p className="font-semibold text-sm">{item.product_name}</p>
                      <p className="text-xs text-muted-foreground">{item.variant_name} • SKU: {item.sku} • Qty: {item.quantity}</p>
                    </div>
                    <p className="font-semibold">{formatCurrency(Number(item.line_total || 0))}</p>
                  </div>
                ))}
              </div>
            )}
          </Card>

          <Card className="p-6 rounded-2xl space-y-3">
            <h2 className="text-lg font-bold">Price Details</h2>
            <div className="flex justify-between text-sm"><span>Subtotal</span><span>{formatCurrency(subtotal)}</span></div>
            <div className="flex justify-between text-sm"><span>Shipping</span><span>{shipping === 0 ? 'Free' : formatCurrency(shipping)}</span></div>
            <div className="flex justify-between text-sm"><span>Tax</span><span>{formatCurrency(tax)}</span></div>
            <div className="flex justify-between text-sm"><span>Discount</span><span>-{formatCurrency(discount)}</span></div>
            <div className="border-t pt-3 flex justify-between font-bold"><span>Total</span><span>{formatCurrency(total)}</span></div>
          </Card>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <Card className="p-6 rounded-2xl">
            <h2 className="text-lg font-bold mb-3">Shipping Address</h2>
            <pre className="text-sm text-foreground whitespace-pre-wrap font-sans">{formatAddress(order.shipping_address)}</pre>
          </Card>

          <Card className="p-6 rounded-2xl">
            <h2 className="text-lg font-bold mb-3">Billing Address</h2>
            <pre className="text-sm text-foreground whitespace-pre-wrap font-sans">{formatAddress(order.billing_address)}</pre>
          </Card>
        </div>

        {order.notes ? (
          <Card className="p-6 rounded-2xl">
            <h2 className="text-lg font-bold mb-2">Order Notes</h2>
            <p className="text-sm text-muted-foreground">{order.notes}</p>
          </Card>
        ) : null}

        <div className="flex items-center gap-3">
          <Link to="/products/"><Button variant="outline" className="rounded-xl">Continue Shopping</Button></Link>
          <Link to="/cart"><Button className="rounded-xl">Back to Cart</Button></Link>
        </div>
      </div>
    </div>
  );
};
