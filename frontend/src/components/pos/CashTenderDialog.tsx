import { useMemo, useState } from 'react';

import posService from '@/services/api/pos';

import { money } from './money';

interface Props {
  orderId: string;
  shiftId: string;
  balanceDue: string;
  /** Split: take part in cash now, then raise a QR for the rest. */
  split?: boolean;
  onClose: () => void;
  onTaken: (result: { balance_due: string; order_payment_status: string }) => void;
}

/**
 * Cash at the counter.
 *
 * Two numbers, kept apart on purpose: what the sale is credited with, and what
 * the customer physically handed over. The difference is change — a drawer
 * movement, never revenue. Conflating them is how a stall's takings quietly
 * inflate, so the server stores both and this screen collects both.
 *
 * In split mode the cash leg is taken first and the remainder goes to a QR. That
 * order matters: cash is instant and its amount is known, so the QR can be raised
 * for an exact figure. The other way round is guessing how much cash a customer
 * will produce, and refunding a gateway payment over a ₹200 gap.
 */
export function CashTenderDialog({
  orderId,
  shiftId,
  balanceDue,
  split,
  onClose,
  onTaken,
}: Props) {
  const due = Number(balanceDue || 0);
  const [entry, setEntry] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const received = Number(entry || 0);
  const applied = split ? received : due;
  const change = split ? 0 : received - due;
  const remaining = split ? due - received : 0;

  const canSubmit = useMemo(() => {
    if (received <= 0) return false;
    if (split) return remaining > 0;
    return change >= 0;
  }, [received, split, remaining, change]);

  const key = (k: string) => {
    if (k === 'del') return setEntry((v) => v.slice(0, -1));
    setEntry((v) => (v + k).slice(0, 7));
  };

  const submit = async () => {
    setBusy(true);
    setError('');
    try {
      const result = await posService.cashTender(shiftId, {
        order: orderId,
        amount_applied: String(applied),
        cash_received: String(received),
      });
      onTaken(result);
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Could not record the cash.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="fixed inset-0 z-40 grid place-items-center overflow-y-auto bg-black/50 p-5">
      <div className="w-full max-w-md rounded-xl border border-border bg-card p-5 shadow-xl">
        <h3 className="text-base font-semibold">
          {split ? 'Split payment · cash leg first' : 'Cash tender'}
        </h3>

        {split && (
          <p className="mt-3 rounded-lg bg-emerald-500/10 px-3 py-2 text-xs text-emerald-800">
            Take the cash first. The QR is then raised for the exact remainder, so the
            customer can never be charged twice for the part they've already paid.
          </p>
        )}

        <div className="mt-4 flex items-baseline justify-between rounded-lg border border-border bg-muted/40 px-3 py-2.5">
          <span className="text-sm">{split ? 'Balance on this sale' : 'Amount due'}</span>
          <span className="text-xl font-semibold tabular-nums">{money(due)}</span>
        </div>

        <div className="mt-2 flex items-baseline justify-between rounded-lg border border-border bg-muted/40 px-3 py-2.5">
          <span className="text-sm">{split ? 'Cash portion' : 'Received'}</span>
          <span className="text-xl font-semibold tabular-nums">{money(received)}</span>
        </div>

        <div className="mt-3 flex gap-2">
          {[500, 1000, 2000].map((v) => (
            <button
              key={v}
              type="button"
              className="flex-1 rounded-lg border border-border py-2 text-sm font-semibold"
              onClick={() => setEntry(String(v))}
            >
              ₹{v}
            </button>
          ))}
          <button
            type="button"
            className="flex-1 rounded-lg border border-border py-2 text-sm font-semibold"
            onClick={() => setEntry(String(split ? Math.round(due / 2) : due))}
          >
            {split ? 'Half' : 'Exact'}
          </button>
        </div>

        <div className="mt-3 grid grid-cols-3 gap-2">
          {['1', '2', '3', '4', '5', '6', '7', '8', '9', '00', '0', 'del'].map((k) => (
            <button
              key={k}
              type="button"
              className="rounded-lg border border-border py-3.5 text-lg font-semibold tabular-nums"
              onClick={() => key(k)}
            >
              {k === 'del' ? '⌫' : k}
            </button>
          ))}
        </div>

        <div className="mt-3">
          {split ? (
            remaining > 0 ? (
              <div className="flex items-baseline justify-between rounded-lg bg-amber-500/10 px-3 py-2.5 text-amber-800">
                <span className="text-sm">Remaining, to collect by UPI</span>
                <span className="text-xl font-semibold tabular-nums">{money(remaining)}</span>
              </div>
            ) : (
              <p className="rounded-lg bg-amber-500/10 px-3 py-2 text-sm text-amber-800">
                Cash covers the whole sale — use Cash rather than Split.
              </p>
            )
          ) : change >= 0 ? (
            <div className="flex items-baseline justify-between rounded-lg bg-emerald-500/10 px-3 py-2.5 text-emerald-800">
              <span className="text-sm">Change due</span>
              <span className="text-xl font-semibold tabular-nums">{money(change)}</span>
            </div>
          ) : (
            <p className="rounded-lg bg-amber-500/10 px-3 py-2 text-sm text-amber-800">
              {money(Math.abs(change))} short
            </p>
          )}
        </div>

        {error && (
          <p className="mt-3 rounded-lg bg-destructive/10 px-3 py-2 text-sm text-destructive">
            {error}
          </p>
        )}

        <div className="mt-4 flex gap-2">
          <button
            type="button"
            className="flex-1 rounded-lg border border-border px-4 py-2.5 text-sm font-semibold"
            onClick={onClose}
          >
            Cancel
          </button>
          <button
            type="button"
            disabled={!canSubmit || busy}
            className="flex-1 rounded-lg bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground disabled:opacity-50"
            onClick={() => void submit()}
          >
            {busy ? 'Recording…' : split ? 'Take cash, then QR' : 'Complete sale'}
          </button>
        </div>
      </div>
    </div>
  );
}
