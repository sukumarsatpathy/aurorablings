import { useEffect, useState } from 'react';
import apiClient from '@/services/api/client';

export interface ShippingSummary {
  /** Delivery charge for an order of the given value (before address-specific rules). */
  shippingTotal: number;
  /** Order value at which delivery becomes free; 0 when no threshold applies. */
  freeShippingThreshold: number;
}

const cache = new Map<number, ShippingSummary>();

/**
 * Delivery charge for an order worth `subtotal`, from the backend shipping rules
 * (GET /v1/surcharge/shipping-summary/). Returns null until loaded or on error,
 * so callers can simply render nothing.
 */
export function useShippingSummary(subtotal: number): ShippingSummary | null {
  const key = Math.max(0, Math.round(subtotal * 100) / 100);
  const [summary, setSummary] = useState<ShippingSummary | null>(() => cache.get(key) ?? null);

  useEffect(() => {
    if (!(key > 0)) return undefined;
    let mounted = true;
    const run = async () => {
      const cached = cache.get(key);
      if (cached) {
        setSummary(cached);
        return;
      }
      try {
        const response = await apiClient.get('/v1/surcharge/shipping-summary/', { params: { subtotal: key } });
        const data = response?.data?.data || {};
        const next: ShippingSummary = {
          shippingTotal: Number(data.shipping_total || 0),
          freeShippingThreshold: Number(data.free_shipping_threshold || 0),
        };
        cache.set(key, next);
        if (mounted) setSummary(next);
      } catch {
        if (mounted) setSummary(null);
      }
    };
    void run();
    return () => {
      mounted = false;
    };
  }, [key]);

  return key > 0 ? summary : null;
}

export default useShippingSummary;
