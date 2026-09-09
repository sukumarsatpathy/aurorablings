import type { CartEntry } from '@/hooks/usePosCart';

interface Props {
  entries: CartEntry[];
  itemCount: number;
  indicativeSubtotal: number;
  busy?: boolean;
  onSetQuantity: (variantId: string, quantity: number) => void;
  onRemove: (variantId: string) => void;
  onCreateOrder: () => void;
  error?: string;
}

const money = (value: number | string) =>
  `₹${Number(value).toLocaleString('en-IN', { maximumFractionDigits: 0 })}`;

/**
 * The current sale.
 *
 * The subtotal shown here is indicative and says so. The server prices the sale
 * when the order is created — coupons, surcharges and any price that changed
 * since the tablet loaded are applied there, and that figure is the one money is
 * taken against.
 */
export function CartPanel({
  entries,
  itemCount,
  indicativeSubtotal,
  busy,
  onSetQuantity,
  onRemove,
  onCreateOrder,
  error,
}: Props) {
  return (
    <div className="flex h-full flex-col bg-muted/30">
      <div className="flex items-center justify-between border-b border-border p-4">
        <h2 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          Current sale
        </h2>
        <span className="text-xs text-muted-foreground tabular-nums">
          {itemCount} {itemCount === 1 ? 'item' : 'items'}
        </span>
      </div>

      <div className="flex-1 overflow-y-auto">
        {entries.length === 0 ? (
          <p className="p-12 text-center text-sm leading-relaxed text-muted-foreground">
            Cart is empty.
            <br />
            Tap a piece to start a sale.
          </p>
        ) : (
          entries.map(({ row, quantity }) => (
            <div
              key={row.variant_id}
              className="grid grid-cols-[auto_1fr_auto] gap-x-3 border-b border-border/60 p-4"
            >
              {/*
                A thumbnail in the cart is the check staff make before taking
                money: the line they added is the thing on the counter. Small
                and fixed-size so a long cart still scrolls in one column.
              */}
              <span className="h-11 w-11 shrink-0 overflow-hidden rounded-md bg-muted">
                {row.image && (
                  <img
                    src={row.image}
                    alt=""
                    loading="lazy"
                    className="h-full w-full object-cover"
                  />
                )}
              </span>
              <div>
                <p className="text-sm font-semibold leading-tight">{row.product_name}</p>
                <p className="mt-0.5 font-mono text-[11px] text-muted-foreground">
                  {row.sku} · {money(row.price)}
                </p>
                <div className="mt-2 flex items-center gap-1">
                  <button
                    type="button"
                    aria-label="Decrease"
                    className="grid h-7 w-7 place-items-center rounded-md border border-border"
                    onClick={() => onSetQuantity(row.variant_id, quantity - 1)}
                  >
                    −
                  </button>
                  <span className="min-w-8 text-center text-sm font-semibold tabular-nums">
                    {quantity}
                  </span>
                  <button
                    type="button"
                    aria-label="Increase"
                    className="grid h-7 w-7 place-items-center rounded-md border border-border disabled:opacity-40"
                    disabled={row.track_inventory && quantity >= row.stock}
                    onClick={() => onSetQuantity(row.variant_id, quantity + 1)}
                  >
                    +
                  </button>
                  <button
                    type="button"
                    className="ml-2 rounded-md border border-dashed border-border px-2 py-0.5 text-[11px] text-muted-foreground"
                    onClick={() => onRemove(row.variant_id)}
                  >
                    remove
                  </button>
                </div>
              </div>
              <span className="self-center text-sm font-bold tabular-nums">
                {money(Number(row.price) * quantity)}
              </span>
            </div>
          ))
        )}
      </div>

      <div className="border-t border-border bg-card p-4">
        <div className="flex items-baseline justify-between">
          <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            Subtotal
          </span>
          <span className="text-2xl font-semibold tabular-nums">{money(indicativeSubtotal)}</span>
        </div>
        <p className="mt-1 text-[11px] text-muted-foreground">
          Indicative. Coupons and final pricing are applied when the sale is created.
        </p>

        {error && (
          <p className="mt-3 rounded-lg bg-destructive/10 px-3 py-2 text-sm text-destructive">
            {error}
          </p>
        )}

        <button
          type="button"
          disabled={entries.length === 0 || busy}
          onClick={onCreateOrder}
          className="mt-3 w-full rounded-lg bg-primary px-4 py-3 text-sm font-semibold text-primary-foreground disabled:opacity-50"
        >
          {busy ? 'Creating sale…' : 'Create sale'}
        </button>
      </div>
    </div>
  );
}
