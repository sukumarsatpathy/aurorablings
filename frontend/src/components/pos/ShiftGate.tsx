import { useState } from 'react';

import type { PosTerminal } from '@/services/api/pos';

interface Props {
  terminals: PosTerminal[];
  terminalId: string;
  onChooseTerminal: (id: string) => void;
  onOpenShift: (openingFloat: string) => Promise<unknown>;
  error?: string;
}

/**
 * Nothing sells until a shift is open.
 *
 * This is a gate rather than a banner because a sale taken without a shift is
 * cash that cannot be reconciled at close — the exact failure the shift exists
 * to prevent. Better to stop at the door than to let staff halfway into a sale.
 */
export function ShiftGate({ terminals, terminalId, onChooseTerminal, onOpenShift, error }: Props) {
  const [float, setFloat] = useState('2000');
  const [busy, setBusy] = useState(false);
  const [failure, setFailure] = useState('');

  const start = async () => {
    setBusy(true);
    setFailure('');
    try {
      await onOpenShift(float || '0');
    } catch (err: any) {
      setFailure(err?.response?.data?.detail || err?.message || 'Could not open the shift.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex min-h-[60vh] items-center justify-center p-6">
      <div className="w-full max-w-md rounded-xl border border-border bg-card p-6 shadow-sm">
        <h1 className="text-xl font-semibold">Open a shift</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Count the cash already in the drawer and enter it as the opening float. Everything
          taken today is measured against this number at close.
        </p>

        <label className="mt-6 block text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          Terminal
        </label>
        <select
          className="mt-2 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm"
          value={terminalId}
          onChange={(e) => onChooseTerminal(e.target.value)}
        >
          <option value="">Choose a terminal…</option>
          {terminals.map((t) => (
            <option key={t.id} value={t.id}>
              {t.code} — {t.name}
            </option>
          ))}
        </select>

        <label className="mt-4 block text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          Opening float
        </label>
        <input
          className="mt-2 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm tabular-nums"
          inputMode="decimal"
          value={float}
          onChange={(e) => setFloat(e.target.value)}
        />

        {(failure || error) && (
          <p className="mt-4 rounded-lg bg-destructive/10 px-3 py-2 text-sm text-destructive">
            {failure || error}
          </p>
        )}

        <button
          type="button"
          className="mt-6 w-full rounded-lg bg-primary px-4 py-3 text-sm font-semibold text-primary-foreground disabled:opacity-50"
          disabled={!terminalId || busy}
          onClick={() => void start()}
        >
          {busy ? 'Opening…' : 'Open shift'}
        </button>

        {terminals.length === 0 && (
          <p className="mt-4 text-xs text-muted-foreground">
            No terminals are set up yet. An admin can add one under Settings → POS
            Terminals.
          </p>
        )}
      </div>
    </div>
  );
}
