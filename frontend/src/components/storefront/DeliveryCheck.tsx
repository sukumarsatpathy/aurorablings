import React, { useEffect, useState } from 'react';
import { MapPin } from 'lucide-react';
import apiClient from '@/services/api/client';

interface DeliveryEstimate {
  pincode: string;
  serviceable: boolean | null;
  earliest_date: string | null;
  latest_date: string | null;
  city?: string;
  state?: string;
  reason?: string;
}

const STORAGE_KEY = 'aurora_delivery_pincode';

const readSavedPincode = (): string => {
  try {
    return localStorage.getItem(STORAGE_KEY) || '';
  } catch {
    return '';
  }
};

const savePincode = (pincode: string) => {
  try {
    localStorage.setItem(STORAGE_KEY, pincode);
  } catch {
    // private mode etc. — remembering the pincode is only a convenience
  }
};

const formatDay = (iso: string): string =>
  new Date(`${iso}T00:00:00`).toLocaleDateString('en-IN', { weekday: 'short', day: 'numeric', month: 'short' });

/**
 * "Check delivery" pincode field for the product page:
 * Delivery by Thu, 24 Oct – Sat, 26 Oct to Puri.
 * Remembers the last pincode so returning shoppers see their date straight away.
 */
export const DeliveryCheck: React.FC = () => {
  const [pincode, setPincode] = useState(readSavedPincode);
  const [estimate, setEstimate] = useState<DeliveryEstimate | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const check = async (value: string) => {
    if (!/^[1-9]\d{5}$/.test(value)) {
      setError('Enter a valid 6-digit pincode.');
      setEstimate(null);
      return;
    }
    setLoading(true);
    setError('');
    try {
      const response = await apiClient.get('/v1/logistics/delivery-estimate/', { params: { pincode: value } });
      setEstimate(response?.data?.data || null);
      savePincode(value);
    } catch (err: unknown) {
      const message = (err as { response?: { data?: { message?: string } } } | null)?.response?.data?.message;
      setError(message || 'Could not check this pincode right now.');
      setEstimate(null);
    } finally {
      setLoading(false);
    }
  };

  // Returning visitor: show their date without making them type again.
  useEffect(() => {
    const saved = readSavedPincode();
    if (saved) void check(saved);
  }, []);

  const place = estimate?.city ? ` to ${estimate.city}` : '';

  return (
    <div className="rounded-2xl border border-border bg-white/70 p-4">
      <form
        className="flex items-center gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          void check(pincode);
        }}
      >
        <MapPin size={16} className="shrink-0 text-primary" aria-hidden="true" />
        <label htmlFor="delivery-pincode" className="sr-only">Delivery pincode</label>
        <input
          id="delivery-pincode"
          inputMode="numeric"
          autoComplete="postal-code"
          maxLength={6}
          placeholder="Enter pincode"
          value={pincode}
          onChange={(e) => setPincode(e.target.value.replace(/\D/g, '').slice(0, 6))}
          className="h-9 min-w-0 flex-1 rounded-lg border border-border bg-white px-3 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
        />
        <button
          type="submit"
          disabled={loading}
          className="h-9 shrink-0 rounded-lg px-3 text-sm font-semibold text-primary hover:bg-primary/10 disabled:opacity-60"
        >
          {loading ? 'Checking…' : 'Check'}
        </button>
      </form>

      <div className="mt-2 text-sm" aria-live="polite">
        {error ? <p className="text-red-600">{error}</p> : null}
        {!error && estimate ? (
          estimate.serviceable === false ? (
            <p className="text-amber-700">
              {estimate.reason === 'unknown_pincode'
                ? "We couldn't find this pincode — please check it."
                : `Sorry, we can't deliver to ${estimate.pincode} yet. Message us on WhatsApp and we'll try to help.`}
            </p>
          ) : estimate.earliest_date && estimate.latest_date ? (
            <p className="text-foreground">
              {estimate.earliest_date === estimate.latest_date ? (
                <>Delivery by <strong>{formatDay(estimate.earliest_date)}</strong>{place}</>
              ) : (
                <>
                  Delivery <strong>{formatDay(estimate.earliest_date)} – {formatDay(estimate.latest_date)}</strong>{place}
                </>
              )}
            </p>
          ) : null
        ) : null}
        {!error && !estimate ? (
          <p className="text-muted-foreground">Check when it reaches you.</p>
        ) : null}
      </div>
    </div>
  );
};

export default DeliveryCheck;
