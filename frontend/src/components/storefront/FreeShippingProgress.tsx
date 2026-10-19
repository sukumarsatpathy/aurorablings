import React from 'react';
import { Truck } from 'lucide-react';
import { useCurrency } from '@/hooks/useCurrency';
import { cn } from '@/lib/utils';

interface FreeShippingProgressProps {
  /** Cart value the threshold is compared against (before delivery and tax). */
  subtotal: number;
  /** Order value at which delivery becomes free; 0 / missing hides the bar. */
  threshold: number;
  className?: string;
}

/**
 * "Add ₹400 more for FREE delivery" nudge with a progress bar.
 * The threshold comes from the backend shipping rules (surcharge API),
 * so it always matches what checkout will actually charge.
 */
export const FreeShippingProgress: React.FC<FreeShippingProgressProps> = ({ subtotal, threshold, className }) => {
  const { formatCurrency } = useCurrency();
  if (!threshold || threshold <= 0 || subtotal <= 0) return null;

  const remaining = Math.max(0, threshold - subtotal);
  const unlocked = remaining <= 0;
  const percent = Math.min(100, Math.round((subtotal / threshold) * 100));

  return (
    <div
      className={cn('rounded-2xl border border-primary/20 bg-primary/5 px-4 py-3', className)}
      role="status"
      aria-live="polite"
    >
      <p className="flex items-center gap-2 text-sm text-foreground">
        <Truck size={16} className="shrink-0 text-primary" aria-hidden="true" />
        {unlocked ? (
          <span>
            You&apos;ve unlocked <strong className="text-primary">FREE delivery</strong>
          </span>
        ) : (
          <span>
            Add <strong>{formatCurrency(remaining)}</strong> more for <strong className="text-primary">FREE delivery</strong>
          </span>
        )}
      </p>
      <div
        className="mt-2 h-1.5 overflow-hidden rounded-full bg-primary/15"
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={percent}
        aria-label="Progress towards free delivery"
      >
        <div className="h-full rounded-full bg-primary transition-[width] duration-500" style={{ width: `${percent}%` }} />
      </div>
    </div>
  );
};

export default FreeShippingProgress;
