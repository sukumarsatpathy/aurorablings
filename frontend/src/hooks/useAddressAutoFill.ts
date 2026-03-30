import { useEffect, useMemo, useRef, useState } from 'react';
import addressService, { type AddressLookupResult } from '@/services/api/address';

interface UseAddressAutoFillOptions {
  pincode: string;
  onResolved: (payload: AddressLookupResult, source: 'pincode' | 'gps') => void;
  debounceMs?: number;
  enabled?: boolean;
}

const EMPTY_RESULT: AddressLookupResult = {
  city: '',
  state: '',
  area: '',
  areas: [],
  pincode: '',
};

const hasUsableAddress = (payload: AddressLookupResult) =>
  Boolean(payload.city || payload.state || payload.area || payload.pincode);

export const useAddressAutoFill = ({
  pincode,
  onResolved,
  debounceMs = 350,
  enabled = true,
}: UseAddressAutoFillOptions) => {
  const [isLoading, setIsLoading] = useState(false);
  const [isGpsLoading, setIsGpsLoading] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState<AddressLookupResult>(EMPTY_RESULT);
  const requestCounter = useRef(0);
  const suppressNextPincodeError = useRef(false);
  const previousPincode = useRef('');
  const hasResolvedAddressRef = useRef(false);

  const normalizedPincode = useMemo(
    () => String(pincode || '').replace(/\D/g, '').slice(0, 6),
    [pincode],
  );

  useEffect(() => {
    if (previousPincode.current !== normalizedPincode) {
      suppressNextPincodeError.current = false;
      hasResolvedAddressRef.current = false;
      previousPincode.current = normalizedPincode;
    }
  }, [normalizedPincode]);

  useEffect(() => {
    if (!enabled) return;
    if (normalizedPincode.length !== 6) {
      setError('');
      setResult(EMPTY_RESULT);
      setIsLoading(false);
      return;
    }

    const requestId = ++requestCounter.current;
    const timer = window.setTimeout(async () => {
      setIsLoading(true);
      setError('');
      const payload = await addressService.getFromPincode(normalizedPincode);
      if (requestCounter.current !== requestId) return;

      setResult((prev) => (hasUsableAddress(payload) ? payload : prev));
      if (hasUsableAddress(payload)) {
        hasResolvedAddressRef.current = true;
        setError('');
        onResolved(payload, 'pincode');
      } else {
        if (suppressNextPincodeError.current) {
          setError('');
          suppressNextPincodeError.current = false;
        } else if (hasResolvedAddressRef.current) {
          setError('');
        } else {
          setError('Could not auto-detect location. You can enter address manually.');
        }
      }
      setIsLoading(false);
    }, debounceMs);

    return () => {
      window.clearTimeout(timer);
    };
  }, [debounceMs, enabled, normalizedPincode, onResolved]);

  const detectFromGps = async () => {
    if (!enabled || !navigator?.geolocation) return;
    requestCounter.current += 1;
    setIsGpsLoading(true);
    setError('');

    const handleFail = () => {
      setError('GPS lookup was unavailable. You can continue with manual entry.');
      setIsGpsLoading(false);
    };

    navigator.geolocation.getCurrentPosition(
      async (position) => {
        const gpsPayload = await addressService.getFromCoordinates(
          position.coords.latitude,
          position.coords.longitude,
        );

        let payload = gpsPayload;
        // Canonicalize city/state via pincode lookup when GPS gives a valid postal code.
        if (String(gpsPayload.pincode || '').length === 6) {
          const pincodePayload = await addressService.getFromPincode(gpsPayload.pincode);
          if (hasUsableAddress(pincodePayload)) {
            payload = {
              ...gpsPayload,
              city: pincodePayload.city || gpsPayload.city,
              state: pincodePayload.state || gpsPayload.state,
              area: gpsPayload.area || pincodePayload.area,
              areas: gpsPayload.areas?.length ? gpsPayload.areas : pincodePayload.areas,
              pincode: pincodePayload.pincode || gpsPayload.pincode,
            };
          }
        }

        setResult((prev) => (hasUsableAddress(payload) ? payload : prev));
        if (hasUsableAddress(payload)) {
          hasResolvedAddressRef.current = true;
          setError('');
          suppressNextPincodeError.current = true;
          onResolved(payload, 'gps');
        } else {
          setError('GPS lookup did not return a usable address.');
        }
        setIsGpsLoading(false);
      },
      () => {
        handleFail();
      },
      { enableHighAccuracy: false, timeout: 8000, maximumAge: 300000 },
    );
  };

  return {
    isLoading,
    isGpsLoading,
    error: hasUsableAddress(result) ? '' : error,
    result,
    locationLabel: result.city || result.state ? `📍 ${result.city}, ${result.state}` : '',
    detectFromGps,
  };
};
