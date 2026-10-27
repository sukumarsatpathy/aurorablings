import { useEffect, useMemo, useState } from 'react';

import { usePaymentPolling } from '@/hooks/usePaymentPolling';
import posService, { type UpiCollection } from '@/services/api/pos';

import { money } from './money';

type Collection = UpiCollection;

interface Props {
  orderId: string;
  orderNumber: string;
  shiftId: string;
  collection: Collection;
  /** Already collected in cash on this sale, so the customer can see it. */
  paidSoFar: string;
  orderTotal: string;
  onSettled: () => void;
  onClose: () => void;
  onRegenerated: (next: Collection) => void;
}

/**
 * The customer's screen.
 *
 * At a stall this tablet gets physically turned around, so it carries one thing:
 * the amount and the code. On a split sale it also states what has already been
 * paid in cash — without that line, a customer looking at a second amount
 * reasonably assumes they are being charged twice.
 *
 * Two rails, one screen:
 *  - Razorpay (legacy): "Paid" is never decided here. It polls our backend,
 *    which only believes a signature-verified webhook.
 *  - Paytm (default): the money lands on the shop's Paytm merchant account and
 *    the Soundbox announces it. Paytm never tells our backend, so a staff member
 *    confirms it here with the UPI reference — and only that confirmation, not
 *    the code being on screen, moves the balance.
 */
export function UpiQrScreen({
  orderId,
  orderNumber,
  shiftId,
  collection,
  paidSoFar,
  orderTotal,
  onSettled,
  onClose,
  onRegenerated,
}: Props) {
  const { state, error, refresh } = usePaymentPolling(orderId, true);
  const [checking, setChecking] = useState(false);
  const [regenerating, setRegenerating] = useState(false);
  // Razorpay serves the code from rzp.io. If that image fails to load — offline
  // stall, blocked host, a URL that isn't an image — the screen would otherwise
  // show an empty space with no explanation, which is indistinguishable from
  // the button having done nothing.
  const [imageBroken, setImageBroken] = useState(false);
  const [secondsLeft, setSecondsLeft] = useState(() =>
    collection.close_by ? Math.max(collection.close_by - Math.floor(Date.now() / 1000), 0) : 15 * 60,
  );
  const [reference, setReference] = useState('');
  const [confirming, setConfirming] = useState(false);
  const [confirmError, setConfirmError] = useState('');
  const [confirmedRef, setConfirmedRef] = useState('');

  // Paytm: no webhook, no expiry — a person confirms what the Soundbox said.
  const manual = Boolean(
    collection.requires_confirmation || collection.kind === 'upi_intent' || collection.kind === 'device',
  );
  const cleanRef = reference.replace(/[^0-9a-z]/gi, '');

  const settled = state ? Number(state.balance_due) <= 0 : false;

  const confirmReceived = async () => {
    if (cleanRef.length < 4) {
      setConfirmError('Enter the UPI reference from the Paytm app (at least the last 4 digits).');
      return;
    }
    setConfirming(true);
    setConfirmError('');
    try {
      const result = await posService.upiTender(shiftId, { order: orderId, reference: cleanRef });
      setConfirmedRef(result.reference);
      await refresh();
    } catch (err: any) {
      setConfirmError((err?.response?.data?.detail || err?.response?.data?.message) || 'Could not record the payment.');
    } finally {
      setConfirming(false);
    }
  };

  useEffect(() => {
    if (settled) onSettled();
  }, [settled, onSettled]);

  useEffect(() => {
    if (settled || manual) return;
    const t = window.setInterval(() => setSecondsLeft((s) => Math.max(s - 1, 0)), 1000);
    return () => window.clearInterval(t);
  }, [settled, manual]);

  const clock = useMemo(() => {
    const m = Math.floor(secondsLeft / 60);
    const s = secondsLeft % 60;
    return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
  }, [secondsLeft]);

  const cashAlready = Number(paidSoFar || 0);

  const regenerate = async () => {
    setRegenerating(true);
    try {
      // Closes the previous QR upstream first, so an expired code and its
      // replacement can never both be paid.
      const next = await posService.upiCollection(orderId, shiftId, collection.transaction_id);
      onRegenerated(next);
      setSecondsLeft(next.close_by ? Math.max(next.close_by - Math.floor(Date.now() / 1000), 0) : 900);
    } finally {
      setRegenerating(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex flex-col bg-[#0d0d13] text-[#f4f4f8]">
      <header className="flex items-center gap-3 border-b border-white/10 px-5 py-3">
        <span className="font-semibold">
          Aurora <span className="text-emerald-400">Blings</span>
        </span>
        <span className="ml-auto font-mono text-xs text-white/50">
          {settled
            ? orderNumber
            : manual
              ? 'Paytm UPI'
              : secondsLeft > 0
                ? `expires in ${clock}`
                : 'QR expired'}
        </span>
      </header>

      <div className="grid flex-1 place-items-center overflow-y-auto p-6 text-center">
        {settled ? (
          <div className="flex flex-col items-center gap-4">
            <div className="grid h-20 w-20 place-items-center rounded-full bg-emerald-400">
              <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="#04231b" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
                <path d="M20 6 9 17l-5-5" />
              </svg>
            </div>
            <h2 className="text-3xl font-semibold">Paid</h2>
            <p className="text-2xl font-semibold tabular-nums">{money(orderTotal)}</p>
            <p className="text-xs uppercase tracking-widest text-white/50">
              {manual
                ? `confirmed at the counter${confirmedRef ? ` · ref ${confirmedRef}` : ''}`
                : 'confirmed by the payment gateway'}
            </p>
          </div>
        ) : (
          <div className="flex flex-col items-center gap-5">
            {/*
              A code, not a URL — whichever path produced it. The link fallback
              used to render the Razorpay URL as text, which is unusable at a
              stall: nobody reads a link off a tablet and types it into their
              phone. The server now renders that link as a QR too, so this only
              needs to know whether it got an image.
            */}
            {collection.kind === 'device' ? (
              <div className="max-w-sm rounded-2xl bg-white/5 p-6">
                <p className="text-lg font-semibold">Scan the Paytm QR at the counter</p>
                <p className="mt-2 text-sm text-white/60">
                  Pay the amount below using any UPI app.
                </p>
              </div>
            ) : collection.image_url && !imageBroken ? (
              <>
                <img
                  src={collection.image_url}
                  alt="Scan to pay"
                  onError={() => setImageBroken(true)}
                  className="w-[230px] rounded-2xl bg-white p-3"
                />
                {collection.kind === 'link' && (
                  <p className="-mt-2 max-w-xs text-xs text-white/50">
                    Payment link, shown as a code — QR codes aren't enabled on this
                    Razorpay account.
                  </p>
                )}
              </>
            ) : (
              <div className="max-w-sm rounded-2xl bg-white/5 p-5">
                <p className="text-sm text-white/70">
                  {imageBroken
                    ? "The code image wouldn't load from the payment gateway. Use this link instead:"
                    : "Couldn't draw a code for this collection. Open the payment link instead:"}
                </p>
                <a
                  href={collection.payment_url || collection.image_url}
                  target="_blank"
                  rel="noreferrer"
                  className="mt-3 block break-all font-mono text-xs text-emerald-300 underline"
                >
                  {collection.payment_url || collection.image_url}
                </a>
              </div>
            )}

            <div>
              <p className="text-4xl font-semibold tabular-nums">{money(collection.amount)}</p>
              <p className="mt-1 text-xs uppercase tracking-widest text-white/50">
                {orderNumber} · scan with any UPI app
              </p>
              {collection.kind === 'upi_intent' && collection.payee && (
                <p className="mt-1 text-xs text-white/40">Paying {collection.payee}</p>
              )}
              {cashAlready > 0 && (
                <p className="mt-3 inline-flex rounded-full bg-emerald-400/10 px-4 py-1.5 text-sm font-medium text-emerald-300">
                  ✓ {money(cashAlready)} already paid in cash · order total {money(orderTotal)}
                </p>
              )}
            </div>

            <p className="flex items-center gap-2 text-xs text-white/50">
              <span className="h-2 w-2 animate-pulse rounded-full bg-emerald-400" />
              {manual
                ? `Staff: wait for the Soundbox to announce ${money(collection.amount)}, then enter the UPI reference below.`
                : 'Waiting for the payment gateway…'}
            </p>
            {error && <p className="text-xs text-amber-300">{error}</p>}
          </div>
        )}
      </div>

      <footer className="flex flex-wrap items-center gap-2 border-t border-white/10 px-5 py-3">
        <button
          type="button"
          className="rounded-lg border border-white/20 bg-white/5 px-3 py-2 text-sm font-semibold"
          onClick={onClose}
        >
          {settled ? 'Done' : 'Back'}
        </button>

        {!settled && manual && (
          <form
            className="ml-auto flex w-full flex-wrap items-center gap-2 sm:w-auto"
            onSubmit={(e) => {
              e.preventDefault();
              void confirmReceived();
            }}
          >
            <label htmlFor="upi-ref" className="sr-only">
              UPI reference
            </label>
            <input
              id="upi-ref"
              value={reference}
              onChange={(e) => {
                setReference(e.target.value);
                setConfirmError('');
              }}
              inputMode="numeric"
              autoComplete="off"
              placeholder="UPI ref (last 4+ digits)"
              className="min-w-0 flex-1 rounded-lg border border-white/20 bg-white/5 px-3 py-2 font-mono text-sm text-white placeholder:text-white/30 sm:w-56 sm:flex-none"
            />
            <button
              type="submit"
              disabled={confirming || cleanRef.length < 4}
              className="rounded-lg bg-emerald-400 px-4 py-2 text-sm font-semibold text-[#04231b] disabled:opacity-40"
            >
              {confirming ? 'Recording…' : `Received ${money(collection.amount)}`}
            </button>
            {confirmError && <p className="w-full text-xs text-amber-300">{confirmError}</p>}
          </form>
        )}

        {!settled && !manual && (
          <>
            <button
              type="button"
              disabled={checking}
              className="rounded-lg border border-white/20 bg-white/5 px-3 py-2 text-sm font-semibold"
              onClick={async () => {
                setChecking(true);
                try {
                  await refresh();
                } finally {
                  setChecking(false);
                }
              }}
            >
              {checking ? 'Checking…' : 'Check status'}
            </button>
            <button
              type="button"
              disabled={regenerating}
              className="ml-auto rounded-lg border border-white/20 bg-white/5 px-3 py-2 text-sm font-semibold"
              onClick={() => void regenerate()}
            >
              {regenerating ? 'Regenerating…' : 'Regenerate QR'}
            </button>
          </>
        )}
      </footer>
    </div>
  );
}
