import { useMemo, useState } from 'react';

import { CartPanel } from '@/components/pos/CartPanel';
import { PaymentStage } from '@/components/pos/PaymentStage';
import { CatalogueGrid } from '@/components/pos/CatalogueGrid';
import { ShiftGate } from '@/components/pos/ShiftGate';
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

  const [creating, setCreating] = useState(false);
  const [orderError, setOrderError] = useState('');
  const [order, setOrder] = useState<PosOrder | null>(null);

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
      });
      setOrder(created);
      cart.clear();
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

  if (loading) {
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
        <span className="font-semibold">
          Aurora <span className="text-primary">Blings</span>
        </span>
        <span className="border-l border-border pl-4 font-mono text-[11px] text-muted-foreground">
          {shift.terminal_code} · shift open
        </span>
        <span className="ml-auto flex items-center gap-4 text-xs text-muted-foreground tabular-nums">
          <span>Drawer: ₹{Number(shift.expected_cash_now).toLocaleString('en-IN')}</span>
          {shift.part_paid_orders.length > 0 && (
            <span className="rounded-full bg-amber-500/10 px-3 py-1 font-semibold text-amber-600">
              {shift.part_paid_orders.length} part-paid
            </span>
          )}
        </span>
      </header>

      {order ? (
        // Once a sale exists the counter has one job: collect the money. The
        // catalogue is deliberately out of the way — a half-finished sale sitting
        // behind a product grid is how part-paid orders get forgotten.
        <div className="flex-1 overflow-y-auto bg-muted/20">
          <PaymentStage
            order={order}
            shiftId={shift.id}
            onFinished={() => {
              setOrder(null);
              void refresh();
            }}
            onVoided={() => {
              setOrder(null);
              void refresh();
            }}
          />
        </div>
      ) : (
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
      )}
    </div>
  );
}

export default PosPage;
