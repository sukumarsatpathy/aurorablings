import { useState } from 'react';

import { usePaymentPolling } from '@/hooks/usePaymentPolling';
import posService, { type PosOrder } from '@/services/api/pos';

import { CashTenderDialog } from './CashTenderDialog';
import { DiscountDialog } from './DiscountDialog';
import { UpiQrScreen } from './UpiQrScreen';
import { money } from './money';

interface Props {
  order: PosOrder;
  shiftId: string;
  onFinished: () => void;
  onVoided: () => void;
}

type Collection = Parameters<typeof UpiQrScreen>[0]['collection'];

/**
 * Taking the money.
 *
 * The sale exists on the server before any of this runs, which is what makes a
 * dead battery survivable: the webhook still lands, the order is still paid, and
 * it is on the part-paid list when staff come back to it.
 */
export function PaymentStage({ order, shiftId, onFinished, onVoided }: Props) {
  const { state, refresh } = usePaymentPolling(order.order_id, true);
  const [dialog, setDialog] = useState<'none' | 'cash' | 'split' | 'discount'>('none');
  const [collection, setCollection] = useState<Collection | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [total, setTotal] = useState(order.grand_total);

  const balance = state?.balance_due ?? total;
  const paid = state?.amount_paid ?? '0';
  const settled = Number(balance) <= 0;
  const partPaid = Number(paid) > 0 && !settled;

  const raiseQr = async () => {
    setBusy(true);
    setError('');
    try {
      const next = await posService.upiCollection(order.order_id, shiftId);
      setCollection(next);
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Could not raise a UPI collection.');
    } finally {
      setBusy(false);
    }
  };

  const voidSale = async () => {
    const reason = window.prompt('Why is this sale being voided?');
    if (!reason) return;
    setBusy(true);
    try {
      await posService.voidSale(order.order_id, reason);
      onVoided();
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Could not void the sale.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="mx-auto w-full max-w-lg p-6">
      <div className="rounded-xl border border-border bg-card p-5">
        <p className="font-mono text-xs text-muted-foreground">{order.order_number}</p>

        <div className="mt-3 flex items-baseline justify-between">
          <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            {settled ? 'Paid' : partPaid ? 'Still to collect' : 'Amount due'}
          </span>
          <span className="text-4xl font-semibold tabular-nums">{money(balance)}</span>
        </div>

        {partPaid && (
          <p className="mt-3 rounded-lg bg-amber-500/10 px-3 py-2 text-sm text-amber-800">
            <strong>Part paid.</strong> {money(paid)} of {money(total)} collected. Finish the
            balance, or void the sale — voiding refunds the cash from the drawer.
          </p>
        )}

        {state && state.tenders.length > 0 && (
          <ul className="mt-3 space-y-1 text-sm">
            {state.tenders.map((t, i) => (
              <li key={i} className="flex justify-between text-muted-foreground">
                <span className="uppercase">{t.method}</span>
                <span className="tabular-nums">− {money(t.amount)}</span>
              </li>
            ))}
          </ul>
        )}

        {error && (
          <p className="mt-3 rounded-lg bg-destructive/10 px-3 py-2 text-sm text-destructive">
            {error}
          </p>
        )}

        {settled ? (
          <button
            type="button"
            className="mt-5 w-full rounded-lg bg-primary px-4 py-3 text-sm font-semibold text-primary-foreground"
            onClick={onFinished}
          >
            Next sale
          </button>
        ) : (
          <>
            <div className="mt-5 grid grid-cols-3 gap-2">
              <button
                type="button"
                disabled={busy}
                className="rounded-lg bg-primary px-3 py-3.5 text-sm font-semibold text-primary-foreground disabled:opacity-50"
                onClick={() => void raiseQr()}
              >
                UPI
                <span className="block text-[10px] font-medium opacity-80">dynamic QR</span>
              </button>
              <button
                type="button"
                className="rounded-lg border border-border px-3 py-3.5 text-sm font-semibold"
                onClick={() => setDialog('cash')}
              >
                Cash
                <span className="block text-[10px] font-medium text-muted-foreground">
                  change due
                </span>
              </button>
              <button
                type="button"
                disabled={partPaid}
                className="rounded-lg border border-border px-3 py-3.5 text-sm font-semibold disabled:opacity-40"
                onClick={() => setDialog('split')}
              >
                Split
                <span className="block text-[10px] font-medium text-muted-foreground">
                  cash + UPI
                </span>
              </button>
            </div>

            <div className="mt-2 flex gap-2">
              <button
                type="button"
                disabled={partPaid}
                className="flex-1 rounded-lg border border-border px-3 py-2 text-xs font-semibold disabled:opacity-40"
                onClick={() => setDialog('discount')}
              >
                Manual discount
              </button>
              <button
                type="button"
                className="flex-1 rounded-lg border border-dashed border-border px-3 py-2 text-xs font-semibold text-muted-foreground"
                onClick={() => void voidSale()}
              >
                {partPaid ? 'Void & refund cash' : 'Void sale'}
              </button>
            </div>
          </>
        )}
      </div>

      {dialog === 'discount' && (
        <DiscountDialog
          orderId={order.order_id}
          orderTotal={total}
          onClose={() => setDialog('none')}
          onApplied={(grandTotal) => {
            setTotal(grandTotal);
            setDialog('none');
            void refresh();
          }}
        />
      )}

      {(dialog === 'cash' || dialog === 'split') && (
        <CashTenderDialog
          orderId={order.order_id}
          shiftId={shiftId}
          balanceDue={balance}
          split={dialog === 'split'}
          onClose={() => setDialog('none')}
          onTaken={async (result) => {
            const wasSplit = dialog === 'split';
            setDialog('none');
            await refresh();
            // Split: the cash leg is in, so raise the QR for exactly what's left.
            if (wasSplit && Number(result.balance_due) > 0) await raiseQr();
          }}
        />
      )}

      {collection && (
        <UpiQrScreen
          orderId={order.order_id}
          orderNumber={order.order_number}
          shiftId={shiftId}
          collection={collection}
          paidSoFar={paid}
          orderTotal={total}
          onSettled={() => void refresh()}
          onClose={() => {
            setCollection(null);
            void refresh();
          }}
          onRegenerated={setCollection}
        />
      )}
    </div>
  );
}
