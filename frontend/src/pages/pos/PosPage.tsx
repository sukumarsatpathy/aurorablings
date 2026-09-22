import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';

import { CartPanel } from '@/components/pos/CartPanel';
import { PaymentStage } from '@/components/pos/PaymentStage';
import { CatalogueGrid } from '@/components/pos/CatalogueGrid';
import { CloseShiftDialog } from '@/components/pos/CloseShiftDialog';
import { CustomerPanel, type CounterCustomer } from '@/components/pos/CustomerPanel';
import { ShiftGate } from '@/components/pos/ShiftGate';
import { useBranding } from '@/hooks/useBranding';
import { usePosCart } from '@/hooks/usePosCart';
import { usePosShift } from '@/hooks/usePosShift';
import posService, { type PosOrder } from '@/services/api/pos';

/**
 * The counter.
 *
 * One screen with panels rather than pages: at a stall, every navigation is a
 * tap that isn't selling. The shift gate is the only thing that comes before it,
 * because a sale without a shift is cash nobody can reconcile.
 *
 * F1/F2 — catalogue, cart and sale creation. Taking payment (F4), the customer
 * panel (F5) and the receipt (F6) land next; the backend for all three is
 * already in place.
 */
export function PosPage() {
  const { terminals, terminalId, chooseTerminal, shift, loading, error, refresh, openShift } =
    usePosShift();
  const cart = usePosCart();
  // Same source as the storefront navbar: Settings → Branding → Brand Logo URL.
  // The name was hard-coded here, so renaming the shop or changing the logo left
  // the till showing the old one.
  const branding = useBranding();

  const [creating, setCreating] = useState(false);
  const [orderError, setOrderError] = useState('');
  const [order, setOrder] = useState<PosOrder | null>(null);
  const [customer, setCustomer] = useState<CounterCustomer | null>(null);
  const [resuming, setResuming] = useState(true);
  const [closingShift, setClosingShift] = useState(false);

  /**
   * An in-progress sale must survive a reload.
   *
   * This is the half that actually matters. A created order has stock reserved
   * against it and may already hold cash; if a refresh loses the reference, the
   * till shows an empty cart as though nothing happened while a real order sits
   * open in the database. Only the id is kept — every figure is re-read from the
   * server on resume.
   */
  useEffect(() => {
    let active = true;
    const stored = sessionStorage.getItem('pos_active_order');
    if (!stored) {
      setResuming(false);
      return;
    }

    (async () => {
      try {
        const state = await posService.paymentState(stored);
        if (!active) return;
        if (Number(state.balance_due) > 0) {
          setOrder({
            order_id: stored,
            order_number: state.order_number,
            // Re-read, not guessed: the payment screen shows this breakdown to
            // a customer, and a resumed sale that had a discount on it must not
            // come back looking like it never did.
            subtotal: state.subtotal,
            discount_amount: state.discount_amount,
            grand_total: state.grand_total,
            fulfilment_type: 'carry_away',
          });
          // Who the sale is for comes back too. A resumed order that shows no
          // name reads as a different sale to the person holding the tablet.
          if (state.contact_phone || state.contact_name) {
            setCustomer({
              name: state.contact_name,
              phone: state.contact_phone,
              email: state.contact_email,
              createAccount: Boolean(state.contact_email),
            });
          }
        } else {
          // Settled while the tab was away — nothing left to collect.
          sessionStorage.removeItem('pos_active_order');
        }
      } catch {
        sessionStorage.removeItem('pos_active_order');
      } finally {
        if (active) setResuming(false);
      }
    })();

    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (order) sessionStorage.setItem('pos_active_order', order.order_id);
    else sessionStorage.removeItem('pos_active_order');
  }, [order]);

  const inCart = useMemo(
    () =>
      cart.entries.reduce<Record<string, number>>((acc, e) => {
        acc[e.row.variant_id] = e.quantity;
        return acc;
      }, {}),
    [cart.entries],
  );

  const createSale = async () => {
    if (!shift) return;
    setCreating(true);
    setOrderError('');
    try {
      const created = await posService.createOrder({
        items: cart.lines,
        shift: shift.id,
        fulfilment_type: 'carry_away',
        contact_name: customer?.name || '',
        contact_phone: customer?.phone || '',
        // The email always goes on the order. A receipt is transactional and
        // needs somewhere to send it, and dropping the address because the
        // account box was unticked left the sale with no way to reach the
        // customer at all. Whether they wanted a login is a separate answer,
        // sent separately, and honoured after settlement.
        contact_email: customer?.email || '',
        // Optional. null rather than '' when unset — DRF reads an empty string
        // as a malformed date rather than as "no value given".
        date_of_birth: customer?.dateOfBirth || null,
        anniversary_date: customer?.anniversaryDate || null,
        create_account: Boolean(customer?.createAccount && customer?.email),
      });
      setOrder(created);
      // The cart is deliberately kept until the sale is settled or abandoned:
      // it is what "back to cart" restores, and re-typing a five-line sale
      // because a customer added one more pair is the kind of friction that
      // makes staff stop using the till.
      void refresh();
    } catch (err: any) {
      // Stock that sold online mid-sale surfaces here. Say so plainly rather
      // than leaving staff to guess why the button did nothing.
      setOrderError(
        err?.response?.data?.detail ||
          err?.response?.data?.message ||
          'Could not create the sale.',
      );
    } finally {
      setCreating(false);
    }
  };

  if (loading || resuming || cart.restoring) {
    return <p className="p-10 text-center text-sm text-muted-foreground">Loading counter…</p>;
  }

  if (!shift) {
    return (
      <ShiftGate
        terminals={terminals}
        terminalId={terminalId}
        onChooseTerminal={chooseTerminal}
        onOpenShift={openShift}
        error={error}
      />
    );
  }

  return (
    <div className="flex h-[calc(100vh-4rem)] flex-col">
      <header className="flex items-center gap-4 border-b border-border bg-card px-4 py-3">
        {/* The configured logo, falling back to the brand name as text. The
            fallback matters: a counter that renders a broken-image icon because
            the media file moved is worse than one that just says the name. */}
        {branding.logoUrl ? (
          <img
            src={branding.logoUrl}
            alt={branding.brandName}
            className="h-8 w-auto shrink-0 object-contain"
          />
        ) : (
          <span className="shrink-0 font-semibold">{branding.brandName}</span>
        )}
        <span className="border-l border-border pl-4 font-mono text-[11px] text-muted-foreground">
          {shift.terminal_code} · shift open
        </span>
        <Link
          to="/admin/dashboard"
          className="rounded-md border border-border px-2 py-1 text-[11px] font-semibold text-muted-foreground"
        >
          ← Admin
        </Link>
        <span className="ml-auto flex items-center gap-4 text-xs text-muted-foreground tabular-nums">
          <span>Drawer: ₹{Number(shift.expected_cash_now).toLocaleString('en-IN')}</span>
          {shift.part_paid_orders.length > 0 && (
            <span className="rounded-full bg-amber-500/10 px-3 py-1 font-semibold text-amber-600">
              {shift.part_paid_orders.length} part-paid
            </span>
          )}
          {/*
            Ending the day is a counter action, so it lives on the counter. The
            button is disabled mid-sale rather than hidden: an order with stock
            reserved and possibly cash against it must be finished or voided
            before the drawer is counted, and a hidden control just sends staff
            looking for it.
          */}
          <button
            type="button"
            onClick={() => setClosingShift(true)}
            disabled={Boolean(order)}
            title={order ? 'Finish or void the open sale first' : 'Count the drawer and end the shift'}
            className="rounded-md border border-border px-2.5 py-1 text-[11px] font-semibold text-foreground disabled:opacity-40"
          >
            Close shift
          </button>
        </span>
      </header>

      {closingShift && (
        <CloseShiftDialog
          shiftId={shift.id}
          onCancel={() => setClosingShift(false)}
          onClosed={() => {
            setClosingShift(false);
            setOrder(null);
            setCustomer(null);
            cart.clear();
            sessionStorage.removeItem('pos_active_order');
            // No shift means the gate takes over — the till is closed until
            // someone opens the next one with a counted float.
            void refresh();
          }}
        />
      )}

      {order ? (
        // Once a sale exists the counter has one job: collect the money. The
        // catalogue is deliberately out of the way — a half-finished sale sitting
        // behind a product grid is how part-paid orders get forgotten.
        <div className="flex-1 overflow-y-auto bg-muted/20">
          <PaymentStage
            order={order}
            shiftId={shift.id}
            customerPhone={customer?.phone}
            onFinished={() => {
              setOrder(null);
              setCustomer(null);
              cart.clear();
              void refresh();
            }}
            onVoided={() => {
              setOrder(null);
              cart.clear();
              void refresh();
            }}
            // Back keeps the lines. Void throws them away — that is the whole
            // difference between the two, and why they are separate controls.
            onBack={(lines) => {
              setOrder(null);
              void cart.replaceFromLines(lines);
              void refresh();
            }}
          />
        </div>
      ) : (
      <div className="flex flex-1 flex-col overflow-hidden">
      {cart.restoreNote && (
        <div className="flex items-center gap-3 border-b border-border bg-amber-500/10 px-4 py-2.5 text-sm text-amber-800">
          <span>Cart restored, with changes: {cart.restoreNote}.</span>
          <button
            type="button"
            className="ml-auto text-xs font-semibold underline"
            onClick={cart.dismissRestoreNote}
          >
            Dismiss
          </button>
        </div>
      )}
      <CustomerPanel value={customer} onChange={setCustomer} />
      <div className="grid flex-1 grid-cols-1 overflow-hidden md:grid-cols-[1.35fr_1fr]">
        <div className="overflow-hidden border-r border-border">
          <CatalogueGrid onAdd={cart.add} inCart={inCart} />
        </div>
        <CartPanel
          entries={cart.entries}
          itemCount={cart.itemCount}
          indicativeSubtotal={cart.indicativeSubtotal}
          busy={creating}
          onSetQuantity={cart.setQuantity}
          onRemove={cart.remove}
          onCreateOrder={() => void createSale()}
          error={orderError}
        />
      </div>
      </div>
      )}
    </div>
  );
}

export default PosPage;
