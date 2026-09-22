import { useEffect, useState } from 'react';

import posService, { type CustomerLookup } from '@/services/api/pos';

export interface CounterCustomer {
  name: string;
  phone: string;
  email: string;
  createAccount: boolean;
  /** Set once the server recognises the number — an existing account. */
  existing?: boolean;
  orders?: number;
  /** ISO yyyy-mm-dd or '' — optional, and never required to complete a sale. */
  dateOfBirth?: string;
  anniversaryDate?: string;
  /** The customer's id, when they already have an account. */
  id?: string;
}

interface Props {
  value: CounterCustomer | null;
  onChange: (customer: CounterCustomer | null) => void;
}

const EMPTY: CounterCustomer = {
  name: '', phone: '', email: '', createAccount: true,
  dateOfBirth: '', anniversaryDate: '',
};

/** Today as yyyy-mm-dd — nobody's birthday is in the future. */
const TODAY = new Date().toISOString().slice(0, 10);

/**
 * Who bought it — optional, and skippable in one tap.
 *
 * Capture never blocks a sale. A customer who won't give details still buys the
 * necklace, and a stall queue is not the place to insist. No email simply means
 * no account: the order keeps the name and number, which is a complete sale.
 *
 * The account itself is created server-side after the money lands, and the
 * server decides whether this is a returning customer — phone first. This panel
 * only collects.
 */
export function CustomerPanel({ value, onChange }: Props) {
  // Always start collapsed.
  //
  // This panel is unmounted while the payment screen is up, so coming back from
  // payment remounts it. Opening on a customer being present meant the full
  // edit form reappeared every time, covering the catalogue and the cart — the
  // staff member's next action is almost always to keep selling, not to re-edit
  // a customer they already attached.
  //
  // The earlier reason for opening — that a collapsed panel read as "the name
  // is gone" — is answered by the collapsed summary row below, which shows the
  // name, the phone, the known/new badge and an Edit button. Nothing is hidden.
  const [open, setOpen] = useState(false);
  const [lookup, setLookup] = useState<CustomerLookup | null>(null);
  const [looking, setLooking] = useState(false);
  const draft = value ?? EMPTY;

  const update = (patch: Partial<CounterCustomer>) => onChange({ ...draft, ...patch });

  // Look the number up as soon as it is complete. Staff should not have to press
  // anything to find out they are serving a regular — and a till that says "new
  // customer" about someone who has shopped four times is how duplicate accounts
  // get made.
  useEffect(() => {
    const phone = draft.phone;
    if (!open || phone.length !== 10) {
      setLookup(null);
      return;
    }

    let active = true;
    setLooking(true);
    const timer = window.setTimeout(async () => {
      try {
        const result = await posService.lookupCustomer(phone);
        if (!active) return;
        setLookup(result);
        if (result.found && result.customer) {
          // Prefill from the account, but never overwrite something staff typed.
          onChange({
            ...draft,
            id: result.customer.id,
            name: draft.name || result.customer.name,
            email: draft.email || result.customer.email,
            // Dates already on file prefill, so staff can see them rather than
            // asking a regular their birthday every single visit. Anything
            // staff already typed still wins.
            dateOfBirth: draft.dateOfBirth || result.customer.date_of_birth || '',
            anniversaryDate: draft.anniversaryDate || result.customer.anniversary_date || '',
            existing: true,
            orders: result.customer.orders,
            createAccount: false,
          });
        } else {
          onChange({ ...draft, id: undefined, existing: false, orders: 0 });
        }
      } catch {
        if (active) setLookup(null);
      } finally {
        if (active) setLooking(false);
      }
    }, 350);

    return () => {
      active = false;
      window.clearTimeout(timer);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [draft.phone, open]);

  if (!open && !value) {
    return (
      <div className="flex items-center gap-3 border-b border-border bg-card px-4 py-2.5">
        <span className="flex-1 text-sm text-muted-foreground">
          No customer attached — the sale works fine without one
        </span>
        <button
          type="button"
          className="rounded-md border border-border px-2.5 py-1.5 text-xs font-semibold"
          onClick={() => setOpen(true)}
        >
          Add customer
        </button>
      </div>
    );
  }

  if (!open && value) {
    return (
      <div className="flex items-center gap-3 border-b border-border bg-card px-4 py-2.5">
        <span className="rounded-full bg-emerald-500/10 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-emerald-700">
          {value.existing
            ? `known · ${value.orders ?? 0} orders`
            : value.email && value.createAccount
              ? 'new account'
              : 'contact only'}
        </span>
        <span className="flex-1 truncate text-sm">
          <strong>{value.name || 'Unnamed'}</strong>
          <span className="ml-2 font-mono text-[11px] text-muted-foreground">
            {value.phone}
            {value.email ? ` · ${value.email}` : ' · no email'}
          </span>
        </span>
        <button
          type="button"
          className="rounded-md border border-border px-2.5 py-1.5 text-xs font-semibold"
          onClick={() => setOpen(true)}
        >
          Edit
        </button>
        {/* Detaching has to be reachable from here. Staff attach the wrong
            customer at a busy counter, and making them open the editor to find
            "Skip" is the kind of friction that ends with the wrong person's
            details on a sale. */}
        <button
          type="button"
          className="rounded-md border border-dashed border-border px-2.5 py-1.5 text-xs font-semibold text-muted-foreground"
          onClick={() => {
            onChange(null);
            setLookup(null);
          }}
        >
          Remove
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-3 border-b border-border bg-card p-4">
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <label className="block">
          <span className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
            Phone — checked first
          </span>
          <input
            className="mt-1 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm"
            inputMode="numeric"
            maxLength={10}
            value={draft.phone}
            onChange={(e) => update({ phone: e.target.value.replace(/\D/g, '').slice(0, 10) })}
          />
        </label>
        <label className="block">
          <span className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
            Name
          </span>
          <input
            className="mt-1 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm"
            value={draft.name}
            onChange={(e) => update({ name: e.target.value })}
          />
        </label>
        <label className="block">
          <span className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
            Email — optional
          </span>
          <input
            className="mt-1 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm"
            type="email"
            placeholder="Leave blank for a contact-only sale"
            value={draft.email}
            onChange={(e) => update({ email: e.target.value })}
          />
        </label>
      </div>

      {open && draft.phone.length === 10 && (
        <p
          className={
            lookup?.found
              ? 'rounded-lg bg-emerald-500/10 px-3 py-2 text-sm text-emerald-800'
              : lookup?.conflict
                ? 'rounded-lg bg-amber-500/10 px-3 py-2 text-sm text-amber-800'
                : 'rounded-lg bg-muted px-3 py-2 text-sm text-muted-foreground'
          }
        >
          {looking
            ? 'Checking…'
            : lookup?.found && lookup.customer
              ? `Existing account — ${lookup.customer.name}, ${lookup.customer.orders} past ${
                  lookup.customer.orders === 1 ? 'order' : 'orders'
                }. This sale links to it; no new account, no welcome email.`
              : lookup?.conflict
                ? `Needs a human: ${lookup.reason}. The sale still works — it just won't create an account.`
                : 'No account on this number — new customer.'}
        </p>
      )}

      {/* Occasions. Optional, collapsed behind nothing — two small fields that
          staff can ignore entirely. Never blocks "Attach to sale".

          For a NEW customer these ride on the order and are copied across once
          the account exists after settlement. For a known customer they are
          saved directly, because the account is already there to save them to. */}
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <label className="block">
          <span className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
            Birthday — optional
          </span>
          <input
            className="mt-1 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm"
            type="date"
            max={TODAY}
            value={draft.dateOfBirth || ''}
            onChange={(e) => update({ dateOfBirth: e.target.value })}
          />
        </label>
        <label className="block">
          <span className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
            Anniversary — optional
          </span>
          <input
            className="mt-1 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm"
            type="date"
            max={TODAY}
            value={draft.anniversaryDate || ''}
            onChange={(e) => update({ anniversaryDate: e.target.value })}
          />
        </label>
      </div>

      {(draft.dateOfBirth || draft.anniversaryDate) && (
        <p className="rounded-lg bg-muted px-3 py-2 text-[11px] text-muted-foreground">
          We&apos;ll email a gift coupon a few days before. Please ask before typing a date —
          it is the customer&apos;s to give.
        </p>
      )}

      {draft.email && !draft.existing && (
        <label className="flex items-start gap-2 rounded-lg border border-border bg-muted/40 p-3 text-sm">
          <input
            type="checkbox"
            className="mt-0.5"
            checked={draft.createAccount}
            onChange={(e) => update({ createAccount: e.target.checked })}
          />
          <span>
            <strong>Create an account and send a welcome email</strong>
            <span className="block text-[11px] text-muted-foreground">
              Created after the payment settles. Tell the customer you're doing it.
            </span>
          </span>
        </label>
      )}

      <div className="flex gap-2">
        <button
          type="button"
          className="rounded-lg border border-border px-3 py-2 text-xs font-semibold"
          onClick={() => {
            onChange(null);
            setLookup(null);
            setOpen(false);
          }}
        >
          {value ? 'Remove customer' : 'Skip'}
        </button>
        <button
          type="button"
          disabled={draft.phone.length !== 10}
          className="rounded-lg bg-primary px-3 py-2 text-xs font-semibold text-primary-foreground disabled:opacity-50"
          onClick={() => {
            // A known customer's dates are saved now, because their account
            // already exists and the order path only ever *fills blanks* — it
            // will not correct a date that is already on file, by design.
            //
            // Deliberately not awaited and deliberately swallowed: this is a
            // queue, and a slow or failed write of an optional birthday must
            // never stand between staff and the next sale.
            if (draft.existing && draft.id) {
              void posService
                .setCustomerOccasions(draft.id, {
                  date_of_birth: draft.dateOfBirth || null,
                  anniversary_date: draft.anniversaryDate || null,
                })
                .catch(() => undefined);
            }
            setOpen(false);
          }}
        >
          Attach to sale
        </button>
      </div>
    </div>
  );
}
