import { useEffect, useMemo, useState } from 'react';

import { usePaymentPolling } from '@/hooks/usePaymentPolling';
import posService from '@/services/api/pos';

import { money } from './money';

interface Collection {
  kind: 'qr' | 'link';
  transaction_id: string;
  qr_id: string;
  image_url?: string;
  payment_url?: string;
  amount: string;
  note?: string;
  close_by?: number | null;
}

interface Props {
  orderId: string;
  orderNumber: string;
  shiftId: string;
  collection: Collection;
  /** Already collected in cash on this sale, so the customer can see it. */
  paidSoFar: string;
  orderTotal: string;
  onSettled: () => void;
  onClose: () => void;
  onRegenerated: (next: Collection) => void;
}

/**
 * The customer's screen.
 *
 * At a stall this tablet gets physically turned around, so it carries one thing:
 * the amount and the code. On a split sale it also states what has already been
 * paid in cash — without that line, a customer looking at a second amount
 * reasonably assumes they are being charged twice.
 *
 * "Paid" here is never decided by this screen. It polls our backend, which only
 * believes a signature-verified webhook.
 */
export function UpiQrScreen({
  orderId,
  orderNumber,
  shiftId,
  collection,
  paidSoFar,
  orderTotal,
  onSettled,
  onClose,
  onRegenerated,
}: Props) {
  const { state, error, refresh } = usePaymentPolling(orderId, true);
  const [checking, setChecking] = useState(false);
  const [regenerating, setRegenerating] = useState(false);
  const [secondsLeft, setSecondsLeft] = useState(() =>
    collection.close_by ? Math.max(collection.close_by - Math.floor(Date.now() / 1000), 0) : 15 * 60,
  );

  const settled = state ? Number(state.balance_due) <= 0 : false;

  useEffect(() => {
    if (settled) onSettled();
  }, [settled, onSettled]);

  useEffect(() => {
    if (settled) return;
    const t = window.setInterval(() => setSecondsLeft((s) => Math.max(s - 1, 0)), 1000);
    return () => window.clearInterval(t);
  }, [settled]);

  const clock = useMemo(() => {
    const m = Math.floor(secondsLeft / 60);
    const s = secondsLeft % 60;
    return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
  }, [secondsLeft]);

  const cashAlready = Number(paidSoFar || 0);

  const regenerate = async () => {
    setRegenerating(true);
    try {
      // Closes the previous QR upstream first, so an expired code and its
      // replacement can never both be paid.
      const next = await posService.upiCollection(orderId, shiftId, collection.transaction_id);
      onRegenerated(next);
      setSecondsLeft(next.close_by ? Math.max(next.close_by - Math.floor(Date.now() / 1000), 0) : 900);
    } finally {
      setRegenerating(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex flex-col bg-[#0d0d13] text-[#f4f4f8]">
      <header className="flex items-center gap-3 border-b border-white/10 px-5 py-3">
        <span className="font-semibold">
          Aurora <span className="text-emerald-400">Blings</span>
        </span>
        <span className="ml-auto font-mono text-xs text-white/50">
          {settled ? orderNumber : secondsLeft > 0 ? `expires in ${clock}` : 'QR expired'}
        </span>
      </header>

      <div className="grid flex-1 place-items-center overflow-y-auto p-6 text-center">
        {settled ? (
          <div className="flex flex-col items-center gap-4">
            <div className="grid h-20 w-20 place-items-center rounded-full bg-emerald-400">
              <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="#04231b" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
                <path d="M20 6 9 17l-5-5" />
              </svg>
            </div>
            <h2 className="text-3xl font-semibold">Paid</h2>
            <p className="text-2xl font-semibold tabular-nums">{money(orderTotal)}</p>
            <p className="text-xs uppercase tracking-widest text-white/50">
              confirmed by the payment gateway
            </p>
          </div>
        ) : (
          <div className="flex flex-col items-center gap-5">
            {collection.kind === 'qr' && collection.image_url ? (
              <img
                src={collection.image_url}
                alt="Scan to pay"
                className="w-[230px] rounded-2xl bg-white p-3"
              />
            ) : (
              <div className="max-w-sm rounded-2xl bg-white/5 p-5">
                <p className="text-sm text-white/70">
                  QR codes aren't enabled on this Razorpay account, so this sale uses a
                  payment link instead.
                </p>
                <a
                  href={collection.payment_url}
                  target="_blank"
                  rel="noreferrer"
                  className="mt-3 block break-all font-mono text-xs text-emerald-300 underline"
                >
                  {collection.payment_url}
                </a>
              </div>
            )}

            <div>
              <p className="text-4xl font-semibold tabular-nums">{money(collection.amount)}</p>
              <p className="mt-1 text-xs uppercase tracking-widest text-white/50">
                {orderNumber} · scan with any UPI app
              </p>
              {cashAlready > 0 && (
                <p className="mt-3 inline-flex rounded-full bg-emerald-400/10 px-4 py-1.5 text-sm font-medium text-emerald-300">
                  ✓ {money(cashAlready)} already paid in cash · order total {money(orderTotal)}
                </p>
              )}
            </div>

            <p className="flex items-center gap-2 text-xs text-white/50">
              <span className="h-2 w-2 animate-pulse rounded-full bg-emerald-400" />
              Waiting for the payment gateway…
            </p>
            {error && <p className="text-xs text-amber-300">{error}</p>}
          </div>
        )}
      </div>

      <footer className="flex flex-wrap items-center gap-2 border-t border-white/10 px-5 py-3">
        <button
          type="button"
          className="rounded-lg border border-white/20 bg-white/5 px-3 py-2 text-sm font-semibold"
          onClick={onClose}
        >
          {settled ? 'Done' : 'Back'}
        </button>

        {!settled && (
          <>
            <button
              type="button"
              disabled={checking}
              className="rounded-lg border border-white/20 bg-white/5 px-3 py-2 text-sm font-semibold"
              onClick={async () => {
                setChecking(true);
                try {
                  await refresh();
                } finally {
                  setChecking(false);
                }
              }}
            >
              {checking ? 'Checking…' : 'Check status'}
            </button>
            <button
              type="button"
              disabled={regenerating}
              className="ml-auto rounded-lg border border-white/20 bg-white/5 px-3 py-2 text-sm font-semibold"
              onClick={() => void regenerate()}
            >
              {regenerating ? 'Regenerating…' : 'Regenerate QR'}
            </button>
          </>
        )}
      </footer>
    </div>
  );
}
