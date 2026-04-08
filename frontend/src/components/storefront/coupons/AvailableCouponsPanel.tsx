import React from 'react';
import { TicketPercent } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import type { CartCouponSummary } from '@/services/api/cart';
import { useCurrency } from '@/hooks/useCurrency';

interface AvailableCouponsPanelProps {
  coupons: CartCouponSummary[];
  loading?: boolean;
  applyingCode?: string;
  onApply: (code: string) => void;
}

const formatCouponValue = (coupon: CartCouponSummary) => {
  if (coupon.discount_type === 'percentage') {
    return `${Number(coupon.value || 0)}% OFF`;
  }
  return `Flat ${coupon.value} OFF`;
};

export const AvailableCouponsPanel: React.FC<AvailableCouponsPanelProps> = ({
  coupons,
  loading = false,
  applyingCode = '',
  onApply,
}) => {
  const { formatCurrency } = useCurrency();

  if (loading) {
    return <p className="text-xs text-muted-foreground">Loading coupons...</p>;
  }

  if (!coupons.length) {
    return <p className="text-xs text-muted-foreground">No coupons are available for this cart right now.</p>;
  }

  return (
    <div className="space-y-2.5">
      {coupons.map((coupon) => (
        <div
          key={coupon.id}
          className={`rounded-xl border p-3 ${
            coupon.is_eligible
              ? 'border-emerald-200 bg-emerald-50/60'
              : 'border-border bg-muted/20 opacity-80'
          }`}
        >
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0 space-y-1">
              <div className="inline-flex items-center gap-2">
                <span className="inline-flex h-7 w-7 items-center justify-center rounded-full bg-white text-primary shadow-sm">
                  <TicketPercent size={14} />
                </span>
                <div>
                  <p className="text-sm font-bold text-foreground">{coupon.code}</p>
                  <p className="text-xs font-medium text-emerald-700">{formatCouponValue(coupon)}</p>
                </div>
              </div>
              <p className="text-xs text-muted-foreground">
                Min order {formatCurrency(Number(coupon.min_order_amount || 0))}
                {coupon.max_discount ? ` • Max discount ${formatCurrency(Number(coupon.max_discount))}` : ''}
              </p>
              {coupon.is_eligible ? (
                <p className="text-xs text-emerald-700">
                  You can save up to {formatCurrency(Number(coupon.estimated_discount || 0))} on this cart.
                </p>
              ) : (
                <p className="text-xs text-amber-700">{coupon.disabled_reason}</p>
              )}
            </div>

            <Button
              type="button"
              variant={coupon.is_applied ? 'outline' : 'default'}
              disabled={!coupon.is_eligible || coupon.is_applied || applyingCode === coupon.code}
              onClick={() => onApply(coupon.code)}
              className="h-9 shrink-0 rounded-lg px-3 text-xs"
            >
              {coupon.is_applied ? 'Applied' : applyingCode === coupon.code ? 'Applying...' : 'Apply'}
            </Button>
          </div>
        </div>
      ))}
    </div>
  );
};
