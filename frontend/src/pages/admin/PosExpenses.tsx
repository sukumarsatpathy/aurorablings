import { useCallback, useEffect, useState } from 'react';

import { apiError } from '@/components/pos/photo';
import { money } from '@/components/pos/money';
import { expenseService, type ExpenseTotals, type PosExpense } from '@/services/api/pos';

/** Local date (the shop's day), not UTC — just after midnight IST they differ. */
const today = () => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
};
const monthStart = () => `${today().slice(0, 8)}01`;

const csvCell = (value: string | number | null | undefined) => {
  const text = String(value ?? '');
  return /[",\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
};

/**
 * Every expense recorded at the counter — cash from the drawer and UPI —
 * filterable by date and mode, with the bill photo and a CSV for the books.
 */
export function PosExpenses() {
  const [from, setFrom] = useState(monthStart());
  const [to, setTo] = useState(today());
  const [mode, setMode] = useState<'' | 'cash' | 'upi'>('');
  const [rows, setRows] = useState<PosExpense[]>([]);
  const [totals, setTotals] = useState<ExpenseTotals | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [voiding, setVoiding] = useState<string | null>(null);
  const [reason, setReason] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const data = await expenseService.list({
        from: from || undefined,
        to: to || undefined,
        mode: mode || undefined,
        limit: 500,
      });
      setRows(data.results);
      setTotals(data.totals);
    } catch (err) {
      setError(apiError(err, 'Could not load expenses.'));
    } finally {
      setLoading(false);
    }
  }, [from, to, mode]);

  useEffect(() => {
    void load();
  }, [load]);

  const doVoid = async (id: string) => {
    if (!reason.trim()) return;
    try {
      await expenseService.void(id, reason.trim());
      setVoiding(null);
      setReason('');
      void load();
    } catch (err) {
      setError(apiError(err, 'Could not void the expense.'));
    }
  };

  const exportCsv = () => {
    const header = ['Date', 'Time', 'Mode', 'Amount', 'Remarks', 'UPI reference', 'Terminal', 'By', 'Voided', 'Void reason', 'Bill'];
    const lines = rows.map((r) => {
      const at = new Date(r.created_at);
      return [
        at.toLocaleDateString('en-IN'),
        at.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' }),
        r.payment_mode.toUpperCase(),
        r.amount,
        r.remarks,
        r.upi_reference,
        r.terminal,
        r.created_by,
        r.is_voided ? 'yes' : '',
        r.void_reason,
        r.bill_image || '',
      ].map(csvCell).join(',');
    });
    const blob = new Blob([[header.join(','), ...lines].join('\n')], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `expenses-${from || 'all'}-to-${to || 'today'}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-semibold">Expenses</h1>
        <p className="text-sm text-muted-foreground">
          Recorded from the POS. Cash expenses came out of a shift's drawer; UPI ones are for the books.
        </p>
      </div>

      <div className="flex flex-wrap items-end gap-3 rounded-xl border border-border bg-card p-4">
        <label className="text-xs font-semibold text-muted-foreground">
          From
          <input type="date" value={from} onChange={(e) => setFrom(e.target.value)}
            className="mt-1 block rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground" />
        </label>
        <label className="text-xs font-semibold text-muted-foreground">
          To
          <input type="date" value={to} onChange={(e) => setTo(e.target.value)}
            className="mt-1 block rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground" />
        </label>
        <label className="text-xs font-semibold text-muted-foreground">
          Mode
          <select value={mode} onChange={(e) => setMode(e.target.value as '' | 'cash' | 'upi')}
            className="mt-1 block rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground">
            <option value="">All</option>
            <option value="cash">Cash</option>
            <option value="upi">UPI</option>
          </select>
        </label>
        <button type="button" onClick={() => void load()}
          className="rounded-lg border border-border px-4 py-2 text-sm font-semibold">
          Refresh
        </button>
        <button type="button" onClick={exportCsv} disabled={!rows.length}
          className="rounded-lg border border-border px-4 py-2 text-sm font-semibold disabled:opacity-50">
          Download CSV
        </button>
      </div>

      {totals && (
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          {[
            ['Total', totals.total],
            ['Cash', totals.cash],
            ['UPI', totals.upi],
            ['Entries', String(totals.count)],
          ].map(([label, value]) => (
            <div key={label} className="rounded-xl border border-border bg-card p-4">
              <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">{label}</p>
              <p className="mt-1 text-xl font-semibold tabular-nums">
                {label === 'Entries' ? value : money(value)}
              </p>
            </div>
          ))}
        </div>
      )}

      {error && <p className="rounded-lg bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p>}

      <div className="overflow-x-auto rounded-xl border border-border bg-card">
        <table className="w-full text-sm">
          <thead className="border-b border-border text-left text-xs uppercase tracking-wider text-muted-foreground">
            <tr>
              <th className="px-4 py-3">When</th>
              <th className="px-4 py-3">Mode</th>
              <th className="px-4 py-3">Remarks</th>
              <th className="px-4 py-3 text-right">Amount</th>
              <th className="px-4 py-3">Bill</th>
              <th className="px-4 py-3">By</th>
              <th className="px-4 py-3" />
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {rows.map((r) => (
              <tr key={r.id} className={r.is_voided ? 'opacity-50' : ''}>
                <td className="whitespace-nowrap px-4 py-3 tabular-nums">
                  {new Date(r.created_at).toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short' })}
                  {r.terminal && <span className="block text-xs text-muted-foreground">{r.terminal}</span>}
                </td>
                <td className="px-4 py-3 uppercase">{r.payment_mode}</td>
                <td className="px-4 py-3">
                  <span className={r.is_voided ? 'line-through' : ''}>{r.remarks}</span>
                  {r.upi_reference && <span className="block font-mono text-xs text-muted-foreground">ref {r.upi_reference}</span>}
                  {r.is_voided && <span className="block text-xs text-muted-foreground">Voided: {r.void_reason}</span>}
                </td>
                <td className="px-4 py-3 text-right font-semibold tabular-nums">{money(r.amount)}</td>
                <td className="px-4 py-3">
                  {r.bill_image ? (
                    <a href={r.bill_image} target="_blank" rel="noreferrer">
                      <img src={r.bill_image} alt="Bill" className="h-10 w-10 rounded object-cover" />
                    </a>
                  ) : (
                    <span className="text-xs text-muted-foreground">—</span>
                  )}
                </td>
                <td className="px-4 py-3 text-xs text-muted-foreground">{r.created_by}</td>
                <td className="px-4 py-3 text-right">
                  {!r.is_voided && voiding !== r.id && (
                    <button type="button" className="text-xs text-muted-foreground underline"
                      onClick={() => { setVoiding(r.id); setReason(''); }}>
                      Void
                    </button>
                  )}
                  {voiding === r.id && (
                    <span className="flex justify-end gap-2">
                      <input value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Reason"
                        className="w-36 rounded-md border border-border bg-background px-2 py-1 text-xs" autoFocus />
                      <button type="button" disabled={!reason.trim()} onClick={() => void doVoid(r.id)}
                        className="rounded-md bg-destructive px-2 py-1 text-xs font-semibold text-white disabled:opacity-50">
                        Void
                      </button>
                      <button type="button" onClick={() => setVoiding(null)}
                        className="rounded-md border border-border px-2 py-1 text-xs">
                        Keep
                      </button>
                    </span>
                  )}
                </td>
              </tr>
            ))}
            {!loading && rows.length === 0 && (
              <tr>
                <td colSpan={7} className="px-4 py-10 text-center text-muted-foreground">
                  No expenses in this period.
                </td>
              </tr>
            )}
            {loading && rows.length === 0 && (
              <tr>
                <td colSpan={7} className="px-4 py-10 text-center text-muted-foreground">Loading…</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default PosExpenses;
