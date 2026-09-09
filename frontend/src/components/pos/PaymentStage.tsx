import { useState } from 'react';

import { usePaymentPolling } from '@/hooks/usePaymentPolling';
import posService, { type PosOrder } from '@/services/api/pos';

import { CashTenderDialog } from './CashTenderDialog';
import { DiscountDialog } from './DiscountDialog';
import { ReceiptPanel } from './ReceiptPanel';
import { UpiQrScreen } from './UpiQrScreen';
import { money } from './money';

interface Props {
  order: PosOrder;
  shiftId: string;
  customerPhone?: string;
  onFinished: () => void;
  onVoided: () => void;
  /**
   * Back to the cart before any money has arrived.
   *
   * Not a plain navigation: the sale exists on the server with stock reserved
   * against it, so stepping back cancels it and releases that stock. The cart
   * lines are still on the tablet, so staff re-ring the corrected sale. Once a
   * tender has landed this is gone and Void is the only way out — that path
   * refunds cash from the drawer, which is a different decision.
   */
  onBack: (lines: Array<{ variant_id: string; quantity: number }>) => void;
}

type Collection = Parameters<typeof UpiQrScreen>[0]['collection'];

/**
 * Taking the money.
 *
 * The sale exists on the server before any of this runs, which is what makes a
 * dead battery survivable: the webhook still lands, the order is still paid, and
 * it is on the part-paid list when staff come back to it.
 */
export function PaymentStage({
  order,
  shiftId,
  customerPhone,
  onFinished,
  onVoided,
  onBack,
}: Props) {
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

  // Priced by the server; the tablet only renders. Before the first poll lands
  // we fall back to what order creation returned, so the card is never blank.
  const subtotal = Number(state?.subtotal ?? order.subtotal);
  const couponOff = Number(state?.discount_amount ?? order.discount_amount);
  const manualOff = Number(state?.manual_discount_amount ?? 0);
  const manualReason = (state?.manual_discount_reason ?? '').replace(/_/g, ' ');
  const grandTotal = Number(state?.grand_total ?? total);
  const tax = Number(state?.tax_amount ?? 0);
  const shipping = Number(state?.shipping_cost ?? 0);
  // Whatever is left once every named line is accounted for. It should be zero;
  // if it isn't, something is being charged that this screen cannot name, and
  // showing it is how that gets noticed instead of being absorbed silently.
  const unaccounted = Number(
    (grandTotal - (subtotal - couponOff - manualOff + tax + shipping)).toFixed(2),
  );
  const hasDiscount = couponOff > 0 || manualOff > 0;

  const backOut = async () => {
    setBusy(true);
    setError('');
    try {
      // The order's own lines go back to the cart, so a sale survives being
      // stepped out of even if the tablet has been reloaded since it was rung up.
      await posService.voidSale(order.order_id, 'edited before payment');
      onBack(state?.items ?? []);
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Could not return to the cart.');
    } finally {
      setBusy(false);
    }
  };

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
        <div className="flex items-center gap-3">
          {!settled && !partPaid && (
            <button
              type="button"
              disabled={busy}
              onClick={() => void backOut()}
              title="Cancel this sale and go back to the cart"
              className="-ml-1 rounded-md border border-border px-2 py-1 text-xs font-semibold disabled:opacity-50"
            >
              ← Back to cart
            </button>
          )}
          <p className="truncate font-mono text-xs text-muted-foreground">
            {order.order_number}
          </p>
        </div>

        {/*
          What came off the price, itemised.

          A customer at a stall is watching this screen while a staff member tells
          them they've had something off. One number can't show that, and "trust
          me, it's discounted" is how a discount stops being worth giving. Coupon
          and manual are kept apart because they answer to different people: one
          is a campaign, the other is a staff member's judgement with a reason
          attached.
        */}
        <dl className="mt-4 space-y-1.5 text-sm">
          <div className="flex justify-between">
            <dt className="text-muted-foreground">Subtotal</dt>
            <dd className="tabular-nums">{money(subtotal)}</dd>
          </div>

          {couponOff > 0 && (
            <div className="flex justify-between text-emerald-700">
              <dt>Coupon discount</dt>
              <dd className="tabular-nums">− {money(couponOff)}</dd>
            </div>
          )}

          {manualOff > 0 && (
            <div className="flex justify-between text-emerald-700">
              <dt>
                Manual discount
                {manualReason && (
                  <span className="ml-1 text-xs capitalize opacity-80">({manualReason})</span>
                )}
              </dt>
              <dd className="tabular-nums">− {money(manualOff)}</dd>
            </div>
          )}

          {tax > 0 && (
            <div className="flex justify-between">
              <dt className="text-muted-foreground">Tax</dt>
              <dd className="tabular-nums">{money(tax)}</dd>
            </div>
          )}

          {shipping > 0 && (
            <div className="flex justify-between">
              <dt className="text-muted-foreground">Shipping</dt>
              <dd className="tabular-nums">{money(shipping)}</dd>
            </div>
          )}

          {unaccounted !== 0 && (
            <div className="flex justify-between text-amber-700">
              <dt>Unaccounted</dt>
              <dd className="tabular-nums">{money(unaccounted)}</dd>
            </div>
          )}

          <div className="flex justify-between border-t border-border pt-1.5 font-semibold">
            <dt>Total</dt>
            <dd className="tabular-nums">{money(grandTotal)}</dd>
          </div>

          {hasDiscount && (
            <p className="pt-0.5 text-right text-xs font-semibold text-emerald-700">
              {money(couponOff + manualOff)} saved
            </p>
          )}
        </dl>

        <div className="mt-4 flex items-baseline justify-between border-t border-border pt-4">
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

        {settled ? null : (
          <>
            {/*
              Three actions, none of them pre-chosen.

              UPI used to carry the filled primary style while Cash and Split
              were outlined. Everywhere else in this UI filled-versus-outlined
              means *selected*, so the screen read as "UPI is already chosen,
              waiting for a QR" — and waiting is the reasonable response to
              that. The QR cannot be raised in advance: it is issued for the
              balance at the moment it is asked for, and on a split sale that
              balance is only known after the cash leg. Raising one on arrival
              would also start a 15-minute expiry and leave an unpaid QR
              against every sale that turns out to be cash.

              So the three carry equal weight, and the tender is whatever the
              staff member taps.
            */}
            <p className="mt-5 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              How is the customer paying?
            </p>

            <div className="mt-2 grid grid-cols-3 gap-2">
              <button
                type="button"
                disabled={busy}
                className="rounded-lg border border-border px-3 py-3.5 text-sm font-semibold disabled:opacity-50"
                onClick={() => void raiseQr()}
              >
                UPI
                <span className="block text-[10px] font-medium text-muted-foreground">
                  {busy ? 'raising QR…' : 'tap to show QR'}
                </span>
              </button>
              <button
                type="button"
                className="rounded-lg border border-border px-3 py-3.5 text-sm font-semibold"
                onClick={() => setDialog('cash')}
              >
                Cash
                <span className="block text-[10px] font-medium text-muted-foreground">
                  tap to enter
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
                  cash, then UPI
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

      {settled && (
        <ReceiptPanel
          orderId={order.order_id}
          orderNumber={order.order_number}
          state={state}
          customerPhone={customerPhone}
          onDone={onFinished}
        />
      )}

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
