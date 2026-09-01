import { useEffect, useRef, useState } from 'react';

import posService, { type PaymentState } from '@/services/api/pos';

/**
 * Watch a sale while the customer is scanning.
 *
 * This polls *our* backend, never Razorpay. The server only believes a
 * signature-verified webhook, so the till turning green is always downstream of
 * a real payment — a screen that can be talked into showing PAID by a slow or
 * lying gateway response is the whole failure this design exists to avoid.
 *
 * Two seconds is chosen to feel instant at a counter without hammering the API;
 * polling stops the moment the balance reaches zero.
 */
export function usePaymentPolling(orderId: string | null, active: boolean) {
  const [state, setState] = useState<PaymentState | null>(null);
  const [error, setError] = useState('');
  const timer = useRef<number | null>(null);

  useEffect(() => {
    if (!orderId || !active) return;

    let mounted = true;
    const tick = async () => {
      try {
        const next = await posService.paymentState(orderId);
        if (!mounted) return;
        setState(next);
        setError('');
        if (Number(next.balance_due) <= 0) return; // settled — stop asking
      } catch {
        if (mounted) setError('Lost contact with the counter service.');
      }
      if (mounted) timer.current = window.setTimeout(tick, 2000);
    };

    void tick();
    return () => {
      mounted = false;
      if (timer.current) window.clearTimeout(timer.current);
    };
  }, [orderId, active]);

  const refresh = async () => {
    if (!orderId) return null;
    const next = await posService.paymentState(orderId);
    setState(next);
    return next;
  };

  return { state, error, refresh };
}
