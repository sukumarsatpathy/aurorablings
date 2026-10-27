export type FulfilmentChoice = 'carry_away' | 'ship';

export interface CourierAddress {
  full_name: string;
  phone: string;
  line1: string;
  line2: string;
  city: string;
  state: string;
  pincode: string;
}

export const EMPTY_ADDRESS: CourierAddress = {
  full_name: '', phone: '', line1: '', line2: '', city: '', state: '', pincode: '',
};

/** What the server will refuse, said here first so staff fix it before ringing up. */
export function missingCourierFields(address: CourierAddress): string[] {
  const missing: string[] = [];
  if (!address.full_name.trim()) missing.push('name');
  if (address.phone.replace(/\D/g, '').length !== 10) missing.push('10-digit phone');
  if (!address.line1.trim()) missing.push('address line 1');
  if (!address.city.trim()) missing.push('city');
  if (!address.state.trim()) missing.push('state');
  if (address.pincode.replace(/\D/g, '').length !== 6) missing.push('6-digit pincode');
  return missing;
}

interface Props {
  value: FulfilmentChoice;
  address: CourierAddress;
  onChange: (value: FulfilmentChoice) => void;
  onAddressChange: (address: CourierAddress) => void;
  /** Customer details already typed, offered as the recipient in one tap. */
  customerName?: string;
  customerPhone?: string;
}

const field =
  'mt-1 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm';
const label = 'text-[11px] font-semibold uppercase tracking-wide text-muted-foreground';

/**
 * How the goods leave the counter.
 *
 * Handed over: the customer walks out with it — no address, no shipping
 * charge, and the sale closes itself once paid.
 *
 * Courier: the parcel goes through NimbusPost. A full address is needed, the
 * shipping charge applies, the order joins the shipping-approval queue, and
 * once paid the address is kept in the customer's profile (if they have, or
 * get, an account).
 */
export function FulfilmentPanel({
  value,
  address,
  onChange,
  onAddressChange,
  customerName,
  customerPhone,
}: Props) {
  const update = (patch: Partial<CourierAddress>) => onAddressChange({ ...address, ...patch });
  const canPrefill =
    Boolean(customerName || customerPhone) &&
    (address.full_name !== (customerName || '') || address.phone !== (customerPhone || ''));

  return (
    <div className="border-t border-border bg-card px-4 pt-4">
      <p className={label}>Delivery</p>
      <div className="mt-2 grid grid-cols-2 gap-2" role="radiogroup" aria-label="Delivery">
        {(
          [
            { id: 'carry_away', title: 'Handed over', hint: 'customer takes it now' },
            { id: 'ship', title: 'Courier', hint: 'ship to an address' },
          ] as const
        ).map((option) => {
          const selected = value === option.id;
          return (
            <button
              key={option.id}
              type="button"
              role="radio"
              aria-checked={selected}
              onClick={() => onChange(option.id)}
              className={
                selected
                  ? 'rounded-lg border-2 border-primary bg-primary/5 px-3 py-2.5 text-left text-sm font-semibold'
                  : 'rounded-lg border border-border px-3 py-2.5 text-left text-sm font-semibold'
              }
            >
              {option.title}
              <span className="block text-[10px] font-medium text-muted-foreground">{option.hint}</span>
            </button>
          );
        })}
      </div>

      {value === 'ship' && (
        <div className="mt-3 space-y-3">
          {canPrefill && (
            <button
              type="button"
              className="text-xs font-semibold text-primary underline-offset-4 hover:underline"
              onClick={() => update({ full_name: customerName || address.full_name, phone: customerPhone || address.phone })}
            >
              Use customer&apos;s name and phone
            </button>
          )}
          <div className="grid grid-cols-2 gap-3">
            <label className="block">
              <span className={label}>Recipient name</span>
              <input className={field} value={address.full_name} onChange={(e) => update({ full_name: e.target.value })} />
            </label>
            <label className="block">
              <span className={label}>Phone</span>
              <input
                className={field}
                inputMode="numeric"
                maxLength={10}
                value={address.phone}
                onChange={(e) => update({ phone: e.target.value.replace(/\D/g, '').slice(0, 10) })}
              />
            </label>
          </div>
          <label className="block">
            <span className={label}>Address line 1</span>
            <input
              className={field}
              placeholder="House / flat, street"
              value={address.line1}
              onChange={(e) => update({ line1: e.target.value })}
            />
          </label>
          <label className="block">
            <span className={label}>Address line 2 — optional</span>
            <input
              className={field}
              placeholder="Area, landmark"
              value={address.line2}
              onChange={(e) => update({ line2: e.target.value })}
            />
          </label>
          <div className="grid grid-cols-3 gap-3">
            <label className="block">
              <span className={label}>City</span>
              <input className={field} value={address.city} onChange={(e) => update({ city: e.target.value })} />
            </label>
            <label className="block">
              <span className={label}>State</span>
              <input className={field} value={address.state} onChange={(e) => update({ state: e.target.value })} />
            </label>
            <label className="block">
              <span className={label}>Pincode</span>
              <input
                className={field}
                inputMode="numeric"
                maxLength={6}
                value={address.pincode}
                onChange={(e) => update({ pincode: e.target.value.replace(/\D/g, '').slice(0, 6) })}
              />
            </label>
          </div>
          <p className="rounded-lg bg-muted px-3 py-2 text-[11px] text-muted-foreground">
            Shipping is charged on courier sales. Once paid, this address is saved to the
            customer&apos;s profile if they have an account (or one is created with their email).
          </p>
        </div>
      )}
    </div>
  );
}
