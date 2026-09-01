import { useState } from 'react';

import type { PaymentState } from '@/services/api/pos';

import { money } from './money';

interface Props {
  orderId: string;
  orderNumber: string;
  state: PaymentState | null;
  customerPhone?: string;
  onDone: () => void;
}

const invoiceUrl = (orderId: string) =>
  `${window.location.origin}/api/v1/orders/${orderId}/invoice/public/`;

/**
 * The receipt.
 *
 * The tender breakdown is printed, not just a total: on a split sale that line
 * is what stops a customer disputing the charge a week later, and what lets a
 * bank statement be matched to a paper slip.
 *
 * WhatsApp is first because it is what Indian customers actually open. Printing
 * goes through the browser dialog and a print stylesheet rather than a native
 * integration — a 58mm roll is nice to have, not something to build for.
 */
export function ReceiptPanel({ orderId, orderNumber, state, customerPhone, onDone }: Props) {
  const [copied, setCopied] = useState(false);
  const url = invoiceUrl(orderId);

  const whatsapp = () => {
    const text = `Thank you for shopping with Aurora Blings. Your invoice for ${orderNumber}: ${url}`;
    const target = customerPhone ? `91${customerPhone}` : '';
    window.open(
      `https://wa.me/${target}?text=${encodeURIComponent(text)}`,
      '_blank',
      'noreferrer',
    );
  };

  return (
    <div className="mt-4 rounded-xl border border-border bg-card p-5">
      <h3 className="text-sm font-semibold">Receipt</h3>

      <dl className="mt-3 space-y-1.5 text-sm">
        <div className="flex justify-between text-muted-foreground">
          <dt>Order</dt>
          <dd className="font-mono text-xs text-foreground">{orderNumber}</dd>
        </div>
        {state?.tenders.map((t, i) => (
          <div key={i} className="flex justify-between text-muted-foreground">
            <dt className="capitalize">{t.method === 'upi' ? 'UPI · Razorpay' : t.method}</dt>
            <dd className="font-mono text-xs text-foreground tabular-nums">{money(t.amount)}</dd>
          </div>
        ))}
        <div className="flex justify-between border-t border-border pt-2 font-semibold">
          <dt>Total</dt>
          <dd className="tabular-nums">{money(state?.grand_total ?? '0')}</dd>
        </div>
      </dl>

      <div className="mt-4 grid grid-cols-3 gap-2">
        <button
          type="button"
          className="rounded-lg border border-border px-3 py-2 text-xs font-semibold"
          onClick={whatsapp}
        >
          WhatsApp
        </button>
        <button
          type="button"
          className="rounded-lg border border-border px-3 py-2 text-xs font-semibold"
          onClick={() => window.open(url, '_blank', 'noreferrer')}
        >
          Open / print
        </button>
        <button
          type="button"
          className="rounded-lg border border-border px-3 py-2 text-xs font-semibold"
          onClick={async () => {
            await navigator.clipboard?.writeText(url);
            setCopied(true);
            window.setTimeout(() => setCopied(false), 2000);
          }}
        >
          {copied ? 'Copied' : 'Copy link'}
        </button>
      </div>

      <button
        type="button"
        className="mt-3 w-full rounded-lg bg-primary px-4 py-3 text-sm font-semibold text-primary-foreground"
        onClick={onDone}
      >
        Next sale
      </button>
    </div>
  );
}
