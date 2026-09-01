import { useMemo, useState } from 'react';

import posService from '@/services/api/pos';

import { money } from './money';

const REASONS = [
  { value: 'display_piece', label: 'Display piece' },
  { value: 'minor_defect', label: 'Minor defect' },
  { value: 'bulk_purchase', label: 'Bulk purchase' },
  { value: 'repeat_customer', label: 'Repeat customer' },
  { value: 'price_match', label: 'Price match' },
];

const CEILING_PCT = 10;

interface Props {
  orderId: string;
  orderTotal: string;
  onClose: () => void;
  onApplied: (grandTotal: string) => void;
}

/**
 * A staff discount, with the approval prompt.
 *
 * The ceiling shown here is a courtesy: the server enforces it, and will refuse
 * an over-ceiling discount that arrives without a manager regardless of what
 * this screen did. That matters because this screen runs on a shared, unlocked
 * tablet on a stall table.
 *
 * A manager types their own credentials rather than a PIN. A PIN would be one
 * more secret to leak, and every manager already has an account.
 */
export function DiscountDialog({ orderId, orderTotal, onClose, onApplied }: Props) {
  const [mode, setMode] = useState<'percent' | 'amount'>('percent');
  const [value, setValue] = useState('10');
  const [reason, setReason] = useState(REASONS[0].value);
  const [approverEmail, setApproverEmail] = useState('');
  const [approverPassword, setApproverPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const total = Number(orderTotal || 0);
  const numeric = Number(value || 0);

  const effectivePct = useMemo(() => {
    if (mode === 'percent') return numeric;
    return total > 0 ? (numeric / total) * 100 : 0;
  }, [mode, numeric, total]);

  const off = mode === 'percent' ? (total * numeric) / 100 : numeric;
  const overCeiling = effectivePct > CEILING_PCT;

  const apply = async () => {
    setBusy(true);
    setError('');
    try {
      const result = await posService.applyDiscount(orderId, {
        [mode]: String(numeric),
        reason,
        ...(overCeiling
          ? { approver_email: approverEmail, approver_password: approverPassword }
          : {}),
      } as any);
      onApplied(result.grand_total);
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Could not apply the discount.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="fixed inset-0 z-40 grid place-items-center bg-black/50 p-5">
      <div className="w-full max-w-md rounded-xl border border-border bg-card p-5 shadow-xl">
        <h3 className="text-base font-semibold">Manual discount</h3>

        <div className="mt-4 flex gap-2">
          {(['percent', 'amount'] as const).map((m) => (
            <button
              key={m}
              type="button"
              onClick={() => setMode(m)}
              className={`flex-1 rounded-lg border px-3 py-2 text-sm font-semibold ${
                mode === m
                  ? 'border-primary bg-primary text-primary-foreground'
                  : 'border-border bg-background'
              }`}
            >
              {m === 'percent' ? 'Percent' : 'Flat ₹'}
            </button>
          ))}
        </div>

        <label className="mt-4 block text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          {mode === 'percent' ? 'Percent off' : 'Amount off'}
        </label>
        <input
          className="mt-2 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm tabular-nums"
          inputMode="decimal"
          value={value}
          onChange={(e) => setValue(e.target.value)}
        />

        <label className="mt-4 block text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          Reason (required)
        </label>
        <select
          className="mt-2 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm"
          value={reason}
          onChange={(e) => setReason(e.target.value)}
        >
          {REASONS.map((r) => (
            <option key={r.value} value={r.value}>
              {r.label}
            </option>
          ))}
        </select>

        <p className="mt-4 rounded-lg bg-muted px-3 py-2 text-sm tabular-nums">
          {money(off)} off · new total {money(Math.max(total - off, 0))}
        </p>

        {overCeiling ? (
          <div className="mt-4 space-y-2 rounded-lg bg-amber-500/10 p-3">
            <p className="text-sm font-medium text-amber-700">
              {effectivePct.toFixed(1)}% is over the {CEILING_PCT}% staff ceiling — a manager
              must approve it.
            </p>
            <input
              className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm"
              placeholder="Manager email"
              autoComplete="off"
              value={approverEmail}
              onChange={(e) => setApproverEmail(e.target.value)}
            />
            <input
              className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm"
              type="password"
              placeholder="Manager password"
              autoComplete="new-password"
              value={approverPassword}
              onChange={(e) => setApproverPassword(e.target.value)}
            />
          </div>
        ) : (
          <p className="mt-4 rounded-lg bg-emerald-500/10 px-3 py-2 text-xs text-emerald-800">
            Within the {CEILING_PCT}% staff ceiling. Recorded against you and this shift.
          </p>
        )}

        {error && (
          <p className="mt-3 rounded-lg bg-destructive/10 px-3 py-2 text-sm text-destructive">
            {error}
          </p>
        )}

        <div className="mt-5 flex gap-2">
          <button
            type="button"
            className="flex-1 rounded-lg border border-border px-4 py-2.5 text-sm font-semibold"
            onClick={onClose}
          >
            Cancel
          </button>
          <button
            type="button"
            disabled={busy || numeric <= 0}
            className="flex-1 rounded-lg bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground disabled:opacity-50"
            onClick={() => void apply()}
          >
            {busy ? 'Applying…' : 'Apply'}
          </button>
        </div>
      </div>
    </div>
  );
}
