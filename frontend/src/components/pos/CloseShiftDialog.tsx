import { useEffect, useState } from 'react';

import posService, { type ShiftSummary } from '@/services/api/pos';

import { money } from './money';

interface Props {
  shiftId: string;
  onCancel: () => void;
  onClosed: () => void;
}

/**
 * Closing the drawer.
 *
 * The count is entered before the expected figure is emphasised, and the
 * variance is only revealed afterwards — a staff member who can see the target
 * first will count to it. The server recomputes expected cash from the ledger
 * regardless, so nothing here is trusted; this is about getting an honest count.
 *
 * A shift with part-paid orders open refuses to close (409). That is the one
 * moment unmatched cash hides, so the override is deliberate, second-tap, and
 * recorded with the reason typed into the note.
 */
export function CloseShiftDialog({ shiftId, onCancel, onClosed }: Props) {
  const [summary, setSummary] = useState<ShiftSummary | null>(null);
  const [counted, setCounted] = useState('');
  const [note, setNote] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [needsForce, setNeedsForce] = useState(false);

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const data = await posService.shiftSummary(shiftId);
        if (active) setSummary(data);
      } catch {
        if (active) setError('Could not load the shift figures.');
      }
    })();
    return () => {
      active = false;
    };
  }, [shiftId]);

  const expected = Number(summary?.expected_cash ?? 0);
  const entered = counted.trim() !== '' && !Number.isNaN(Number(counted));
  const variance = entered ? Number(counted) - expected : 0;

  const close = async (force: boolean) => {
    setBusy(true);
    setError('');
    try {
      await posService.closeShift(shiftId, String(Number(counted)), note, force);
      onClosed();
    } catch (err: any) {
      const status = err?.response?.status;
      setError(err?.response?.data?.detail || 'Could not close the shift.');
      // 409 is the drawer refusing, not a malformed request: part-paid sales are
      // still open. Offer the override rather than leaving staff stuck at close.
      if (status === 409) setNeedsForce(true);
    } finally {
      setBusy(false);
    }
  };

  const tenders = Object.entries(summary?.by_tender ?? {});

  return (
    <div className="fixed inset-0 z-40 grid place-items-center overflow-y-auto bg-black/50 p-5">
      <div className="w-full max-w-md rounded-xl border border-border bg-card p-5 shadow-xl">
        <h3 className="text-base font-semibold">Close shift</h3>

        {!summary ? (
          <p className="mt-4 text-sm text-muted-foreground">Loading the shift figures…</p>
        ) : (
          <>
            <dl className="mt-4 space-y-1.5 rounded-lg border border-border bg-muted/40 px-3 py-2.5 text-sm">
              <div className="flex justify-between">
                <dt className="text-muted-foreground">Sales</dt>
                <dd className="tabular-nums">{summary.orders}</dd>
              </div>
              {tenders.map(([method, row]) => (
                <div key={method} className="flex justify-between">
                  <dt className="text-muted-foreground capitalize">{method}</dt>
                  <dd className="tabular-nums">{money(Number(row.total))}</dd>
                </div>
              ))}
              <div className="flex justify-between border-t border-border pt-1.5">
                <dt className="text-muted-foreground">Opening float</dt>
                <dd className="tabular-nums">{money(Number(summary.opening_float))}</dd>
              </div>
              <div className="flex justify-between font-semibold">
                <dt>Expected in drawer</dt>
                <dd className="tabular-nums">{money(expected)}</dd>
              </div>
            </dl>

            {summary.part_paid_open > 0 && (
              <p className="mt-3 rounded-lg bg-amber-500/10 px-3 py-2 text-xs text-amber-800">
                {summary.part_paid_open} part-paid{' '}
                {summary.part_paid_open === 1 ? 'sale is' : 'sales are'} still open. Settle
                or void {summary.part_paid_open === 1 ? 'it' : 'them'} before closing —
                that is exactly where cash goes missing.
              </p>
            )}

            <label className="mt-4 block text-sm font-medium" htmlFor="counted-cash">
              Counted cash in drawer
            </label>
            <input
              id="counted-cash"
              inputMode="decimal"
              autoFocus
              value={counted}
              onChange={(e) => setCounted(e.target.value.replace(/[^\d.]/g, ''))}
              className="mt-1 w-full rounded-lg border border-border bg-background px-3 py-2 text-xl font-semibold tabular-nums"
              placeholder="0.00"
            />

            {entered && (
              <p
                className={`mt-2 text-sm font-semibold tabular-nums ${
                  variance === 0
                    ? 'text-emerald-700'
                    : variance > 0
                      ? 'text-amber-700'
                      : 'text-destructive'
                }`}
              >
                {variance === 0
                  ? 'Balances exactly.'
                  : `${variance > 0 ? 'Over' : 'Short'} by ${money(Math.abs(variance))}`}
              </p>
            )}

            <label className="mt-4 block text-sm font-medium" htmlFor="close-note">
              Note {variance !== 0 && entered ? '(explain the variance)' : '(optional)'}
            </label>
            <input
              id="close-note"
              value={note}
              onChange={(e) => setNote(e.target.value)}
              className="mt-1 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm"
              placeholder="e.g. 100 float taken for change"
            />
          </>
        )}

        {error && <p className="mt-3 text-sm text-destructive">{error}</p>}

        <div className="mt-5 flex gap-2">
          <button
            type="button"
            className="flex-1 rounded-lg border border-border py-2.5 text-sm font-semibold"
            onClick={onCancel}
            disabled={busy}
          >
            Cancel
          </button>
          <button
            type="button"
            className="flex-1 rounded-lg bg-primary py-2.5 text-sm font-semibold text-primary-foreground disabled:opacity-50"
            onClick={() => close(false)}
            disabled={busy || !summary || !entered}
          >
            {busy ? 'Closing…' : 'Close shift'}
          </button>
        </div>

        {needsForce && (
          <button
            type="button"
            className="mt-2 w-full rounded-lg border border-destructive py-2.5 text-sm font-semibold text-destructive disabled:opacity-50"
            onClick={() => close(true)}
            disabled={busy || !note.trim()}
          >
            {note.trim()
              ? 'Close anyway — recorded as an override'
              : 'Add a note to close anyway'}
          </button>
        )}
      </div>
    </div>
  );
}
