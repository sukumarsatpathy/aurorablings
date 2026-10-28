import { useEffect, useRef, useState } from 'react';

/**
 * Scan barcodes with the phone's camera, for when the handheld scanner isn't
 * with you (a stall, a phone order, a dead battery).
 *
 * Uses the browser's built-in BarcodeDetector where it exists (Chrome on
 * Android) and falls back to ZXing, loaded only when the camera is opened, for
 * everything else (Safari on iPhone). Both read Code 128 — what our labels
 * print — and EAN/UPC in case a supplier's barcode is scanned.
 *
 * The camera stays open so a whole basket can be scanned in one go. The same
 * code is ignored for a moment after it's read, otherwise one label held in
 * front of the lens adds five pieces.
 *
 * Needs HTTPS (the live site) and camera permission; both failures are shown
 * in plain words rather than a black box.
 */

interface Props {
  onCode: (code: string) => void;
  onClose: () => void;
  /** Last result, shown under the camera so the cashier needn't look away. */
  notice?: { kind: 'ok' | 'error'; text: string } | null;
}

const REPEAT_MS = 2000;

type Detector = { detect: (source: HTMLVideoElement) => Promise<Array<{ rawValue: string }>> };

export function CameraScanner({ onCode, onClose, notice }: Props) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [error, setError] = useState('');
  const [starting, setStarting] = useState(true);
  const onCodeRef = useRef(onCode);
  useEffect(() => {
    onCodeRef.current = onCode;
  }, [onCode]);

  useEffect(() => {
    let stopped = false;
    let stream: MediaStream | null = null;
    let timer = 0;
    let zxingControls: { stop: () => void } | null = null;
    let last = { code: '', at: 0 };

    const emit = (raw: string) => {
      const code = (raw || '').trim();
      if (!code) return;
      const now = Date.now();
      if (code === last.code && now - last.at < REPEAT_MS) return;
      last = { code, at: now };
      navigator.vibrate?.(60);
      onCodeRef.current(code);
    };

    const start = async () => {
      if (!navigator.mediaDevices?.getUserMedia) {
        setError('This browser cannot use the camera. Open the counter in Chrome or Safari over https.');
        setStarting(false);
        return;
      }
      const video = videoRef.current;
      if (!video) return;

      const Native = (window as unknown as { BarcodeDetector?: new (o: { formats: string[] }) => Detector }).BarcodeDetector;
      try {
        if (Native) {
          stream = await navigator.mediaDevices.getUserMedia({
            video: { facingMode: { ideal: 'environment' }, width: { ideal: 1280 } },
            audio: false,
          });
          if (stopped) return;
          video.srcObject = stream;
          await video.play();
          setStarting(false);
          const detector = new Native({ formats: ['code_128', 'ean_13', 'ean_8', 'upc_a', 'qr_code'] });
          const tick = async () => {
            if (stopped) return;
            try {
              if (video.readyState >= 2) {
                const found = await detector.detect(video);
                if (found[0]) emit(found[0].rawValue);
              }
            } catch {
              /* a dropped frame is not an error */
            }
            timer = window.setTimeout(tick, 150);
          };
          void tick();
          return;
        }

        // Safari and others: ZXing, fetched only now so the till doesn't pay for it.
        const { BrowserMultiFormatReader } = await import('@zxing/browser');
        if (stopped) return;
        const reader = new BrowserMultiFormatReader();
        zxingControls = await reader.decodeFromConstraints(
          { video: { facingMode: { ideal: 'environment' } }, audio: false },
          video,
          (result) => {
            if (result) emit(result.getText());
          },
        );
        if (stopped) zxingControls.stop();
        setStarting(false);
      } catch (err) {
        const name = (err as { name?: string })?.name;
        setError(
          name === 'NotAllowedError'
            ? 'Camera permission was refused. Allow the camera for this site in the browser settings, then try again.'
            : name === 'NotFoundError'
              ? 'No camera found on this device.'
              : 'Could not start the camera. Close other apps using it and try again.',
        );
        setStarting(false);
      }
    };

    void start();
    return () => {
      stopped = true;
      window.clearTimeout(timer);
      zxingControls?.stop();
      stream?.getTracks().forEach((t) => t.stop());
    };
  }, []);

  return (
    <div className="fixed inset-0 z-50 flex flex-col bg-black" role="dialog" aria-label="Scan with camera">
      <div className="relative flex-1 overflow-hidden">
        <video ref={videoRef} className="h-full w-full object-cover" playsInline muted />
        {/* Aim box: a wide, short window, the shape of a barcode. */}
        {!error && (
          <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
            <div className="h-28 w-[80%] max-w-md rounded-xl border-2 border-white/90 shadow-[0_0_0_9999px_rgba(0,0,0,0.45)]" />
          </div>
        )}
        <p className="absolute inset-x-0 top-4 text-center text-sm font-medium text-white drop-shadow">
          {starting && !error ? 'Starting camera…' : 'Hold the barcode inside the box'}
        </p>
        {error && (
          <div className="absolute inset-0 flex items-center justify-center p-6">
            <p className="rounded-xl bg-white p-4 text-center text-sm text-red-700">{error}</p>
          </div>
        )}
      </div>
      <div className="space-y-3 bg-black p-4 pb-[max(1rem,env(safe-area-inset-bottom))]">
        <div
          aria-live="polite"
          className={`min-h-[2.75rem] rounded-lg px-3 py-2.5 text-sm font-medium ${
            !notice
              ? 'bg-white/10 text-white/70'
              : notice.kind === 'ok'
                ? 'bg-emerald-500 text-white'
                : 'bg-red-500 text-white'
          }`}
        >
          {notice ? notice.text : 'Scanned pieces go straight into the cart.'}
        </div>
        <button
          type="button"
          onClick={onClose}
          className="w-full rounded-lg bg-white py-3 text-sm font-semibold text-black"
        >
          Done
        </button>
      </div>
    </div>
  );
}

export default CameraScanner;
