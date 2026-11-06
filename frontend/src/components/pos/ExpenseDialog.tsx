import { useCallback, useEffect, useRef, useState } from 'react';

import { expenseService, type PosExpense } from '@/services/api/pos';

import { apiError, shrinkPhoto } from './photo';

interface Props {
  shiftId: string;
  onClose: () => void;
  /** After any change — the drawer figure in the header needs re-reading. */
  onChanged: () => void;
}

const money = (value: string | number) =>
  `₹${Number(value).toLocaleString('en-IN', { maximumFractionDigits: 2 })}`;

const time = (iso: string) =>
  new Date(iso).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' });

/**
 * Money spent while trading — tea, auto, packing, helper.
 *
 * Cash comes out of the drawer, so the shift's expected cash drops by the same
 * amount and the close still balances. UPI is recorded for the books only.
 * Wrong entries are voided, never deleted.
 */
export function ExpenseDialog({ shiftId, onClose, onChanged }: Props) {
  const [mode, setMode] = useState<'cash' | 'upi'>('cash');
  const [amount, setAmount] = useState('');
  const [remarks, setRemarks] = useState('');
  const [reference, setReference] = useState('');
  const [bill, setBill] = useState<Blob | null>(null);
  const [preview, setPreview] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [list, setList] = useState<PosExpense[]>([]);
  const [voiding, setVoiding] = useState<string | null>(null);
  const [voidReason, setVoidReason] = useState('');
  const fileRef = useRef<HTMLInputElement>(null);

  const load = useCallback(async () => {
    try {
      const data = await expenseService.list({ shift: shiftId });
      setList(data.results);
    } catch {
      /* the form still works without the list */
    }
  }, [shiftId]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => () => {
    if (preview) URL.revokeObjectURL(preview);
  }, [preview]);

  const pick = async (file: File | undefined) => {
    if (!file) return;
    const small = await shrinkPhoto(file, 1600, 0.85);
    setBill(small);
    setPreview((old) => {
      if (old) URL.revokeObjectURL(old);
      return URL.createObjectURL(small);
    });
  };

  const amountNum = Number(amount);
  const canSave = amountNum > 0 && remarks.trim().length > 0 && !busy;

  const save = async () => {
    if (!canSave) return;
    setBusy(true);
    setError('');
    setNotice('');
    try {
      const saved = await expenseService.create({
        payment_mode: mode,
        amount: amountNum.toFixed(2),
        remarks: remarks.trim(),
        upi_reference: mode === 'upi' ? reference.trim() : undefined,
        shift: shiftId,
        bill_image: bill,
      });
      setNotice(
        mode === 'cash' && saved.expected_cash_now
          ? `Saved. Drawer should now have ${money(saved.expected_cash_now)}.`
          : 'Saved.',
      );
      setAmount('');
      setRemarks('');
      setReference('');
      setBill(null);
      setPreview('');
      onChanged();
      void load();
    } catch (err) {
      setError(apiError(err, 'Could not save the expense.'));
    } finally {
      setBusy(false);
    }
  };

  const confirmVoid = async (id: string) => {
    if (!voidReason.trim()) return;
    setBusy(true);
    setError('');
    try {
      await expenseService.void(id, voidReason.trim());
      setVoiding(null);
      setVoidReason('');
      onChanged();
      void load();
    } catch (err) {
      setError(apiError(err, 'Could not void the expense.'));
    } finally {
      setBusy(false);
    }
  };

  const live = list.filter((e) => !e.is_voided);
  const cashTotal = live.filter((e) => e.payment_mode === 'cash').reduce((t, e) => t + Number(e.amount), 0);
  const upiTotal = live.filter((e) => e.payment_mode === 'upi').reduce((t, e) => t + Number(e.amount), 0);

  return (
    <div className="fixed inset-0 z-40 grid place-items-center overflow-y-auto bg-black/50 p-4">
      <div className="w-full max-w-lg rounded-xl border border-border bg-card p-5 shadow-xl">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h3 className="text-base font-semibold">Expense</h3>
            <p className="mt-0.5 text-xs text-muted-foreground">
              Cash is taken out of the drawer total. UPI is recorded only.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-md border border-border px-2.5 py-1 text-xs font-semibold"
          >
            Close
          </button>
        </div>

        <form
          className="mt-4"
          onSubmit={(e) => {
            e.preventDefault();
            void save();
          }}
        >
          <div className="grid grid-cols-2 gap-2" role="radiogroup" aria-label="Paid by">
            {(['cash', 'upi'] as const).map((m) => (
              <button
                key={m}
                type="button"
                role="radio"
                aria-checked={mode === m}
                onClick={() => setMode(m)}
                className={`rounded-lg border px-3 py-2.5 text-sm font-semibold ${
                  mode === m ? 'border-primary bg-primary/10 text-foreground' : 'border-border text-muted-foreground'
                }`}
              >
                {m === 'cash' ? 'Cash (from drawer)' : 'UPI'}
              </button>
            ))}
          </div>

          <label className="mt-3 block text-xs font-semibold text-muted-foreground">
            Amount (₹)
            <input
              value={amount}
              onChange={(e) => setAmount(e.target.value.replace(/[^\d.]/g, ''))}
              inputMode="decimal"
              placeholder="0"
              className="mt-1 w-full rounded-lg border border-border bg-background px-3 py-2 text-lg font-semibold tabular-nums text-foreground outline-none focus:border-primary"
              autoFocus
            />
          </label>

          <label className="mt-3 block text-xs font-semibold text-muted-foreground">
            Remarks
            <textarea
              value={remarks}
              onChange={(e) => setRemarks(e.target.value)}
              maxLength={500}
              rows={2}
              placeholder="What was it for? e.g. Tea for helpers, auto to exhibition"
              className="mt-1 w-full resize-none rounded-lg border border-border bg-background px-3 py-2 text-base text-foreground outline-none focus:border-primary md:text-sm"
            />
          </label>

          {mode === 'upi' && (
            <label className="mt-3 block text-xs font-semibold text-muted-foreground">
              UPI reference (optional)
              <input
                value={reference}
                onChange={(e) => setReference(e.target.value)}
                maxLength={64}
                placeholder="12-digit UTR"
                className="mt-1 w-full rounded-lg border border-border bg-background px-3 py-2 text-base text-foreground outline-none focus:border-primary md:text-sm"
              />
            </label>
          )}

          <input
            ref={fileRef}
            type="file"
            accept="image/*"
            capture="environment"
            className="hidden"
            onChange={(e) => {
              void pick(e.target.files?.[0]);
              e.target.value = '';
            }}
          />
          <div className="mt-3 flex items-center gap-3">
            <button
              type="button"
              onClick={() => fileRef.current?.click()}
              className="rounded-lg border border-dashed border-border px-3 py-2 text-sm font-semibold text-muted-foreground hover:border-primary"
            >
              {bill ? 'Retake bill photo' : 'Add bill photo'}
            </button>
            {preview && <img src={preview} alt="Bill" className="h-12 w-12 rounded-md object-cover" />}
            {bill && (
              <button
                type="button"
                className="text-xs text-muted-foreground underline"
                onClick={() => {
                  setBill(null);
                  setPreview('');
                }}
              >
                remove
              </button>
            )}
          </div>

          {error && (
            <p className="mt-3 rounded-lg bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p>
          )}
          {notice && (
            <p className="mt-3 rounded-lg bg-emerald-500/10 px-3 py-2 text-sm text-emerald-800">{notice}</p>
          )}

          <button
            type="submit"
            disabled={!canSave}
            className="mt-4 w-full rounded-lg bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground disabled:opacity-50"
          >
            {busy ? 'Saving…' : `Save ${mode === 'cash' ? 'cash' : 'UPI'} expense`}
          </button>
        </form>

        <div className="mt-5 border-t border-border pt-4">
          <div className="flex items-baseline justify-between">
            <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              This shift
            </h4>
            <span className="text-xs tabular-nums text-muted-foreground">
              Cash {money(cashTotal)} · UPI {money(upiTotal)}
            </span>
          </div>
          {list.length === 0 ? (
            <p className="mt-2 text-sm text-muted-foreground">No expenses yet.</p>
          ) : (
            <ul className="mt-2 max-h-60 divide-y divide-border overflow-y-auto">
              {list.map((e) => (
                <li key={e.id} className={`py-2 text-sm ${e.is_voided ? 'opacity-50' : ''}`}>
                  <div className="flex items-center gap-2">
                    <span className="w-12 shrink-0 text-xs tabular-nums text-muted-foreground">{time(e.created_at)}</span>
                    <span className="rounded bg-muted px-1.5 py-0.5 text-[10px] font-semibold uppercase">
                      {e.payment_mode}
                    </span>
                    <span className={`min-w-0 flex-1 truncate ${e.is_voided ? 'line-through' : ''}`}>{e.remarks}</span>
                    {e.bill_image && (
                      <a href={e.bill_image} target="_blank" rel="noreferrer" className="text-xs font-semibold underline">
                        bill
                      </a>
                    )}
                    <span className="font-semibold tabular-nums">{money(e.amount)}</span>
                    {!e.is_voided && voiding !== e.id && (
                      <button
                        type="button"
                        className="text-xs text-muted-foreground underline"
                        onClick={() => {
                          setVoiding(e.id);
                          setVoidReason('');
                        }}
                      >
                        void
                      </button>
                    )}
                  </div>
                  {e.is_voided && e.void_reason && (
                    <p className="ml-14 mt-0.5 text-[11px] text-muted-foreground">Voided: {e.void_reason}</p>
                  )}
                  {voiding === e.id && (
                    <div className="ml-14 mt-2 flex gap-2">
                      <input
                        value={voidReason}
                        onChange={(ev) => setVoidReason(ev.target.value)}
                        placeholder="Reason, e.g. entered twice"
                        className="min-w-0 flex-1 rounded-md border border-border bg-background px-2 py-1 text-sm outline-none focus:border-primary"
                        autoFocus
                      />
                      <button
                        type="button"
                        disabled={!voidReason.trim() || busy}
                        className="rounded-md bg-destructive px-2.5 py-1 text-xs font-semibold text-white disabled:opacity-50"
                        onClick={() => void confirmVoid(e.id)}
                      >
                        Void
                      </button>
                      <button
                        type="button"
                        className="rounded-md border border-border px-2.5 py-1 text-xs font-semibold"
                        onClick={() => setVoiding(null)}
                      >
                        Keep
                      </button>
                    </div>
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}
