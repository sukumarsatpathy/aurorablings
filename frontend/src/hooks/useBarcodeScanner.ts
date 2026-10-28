import { useEffect, useRef } from 'react';

/**
 * Catch a handheld barcode scanner on the counter.
 *
 * Scanners in keyboard (HID) mode — USB, 2.4 GHz dongle or Bluetooth — "type"
 * the code very quickly and press Enter. Nothing needs installing; the page
 * just sees keystrokes. This hook tells a scan apart from a person:
 *
 * - keys arrive close together (a Bluetooth scanner can burst unevenly, so the
 *   gap allowed is generous at ~100 ms rather than the 30 ms a USB one needs);
 * - the burst ends in Enter;
 * - it's at least `minLength` characters long.
 *
 * Only keystrokes outside text fields are watched. Inside an input the person
 * may well be typing a phone number, and the field's own Enter handling wins —
 * the catalogue search box handles a scan typed into it itself. When a burst
 * does qualify, the Enter is swallowed so it can't also "click" whatever button
 * last had focus (otherwise tapping a tile and then scanning adds that tile
 * again).
 */
export interface BarcodeScannerOptions {
  onScan: (code: string) => void;
  enabled?: boolean;
  /** Longest pause between two keys of one scan, in ms. */
  maxGapMs?: number;
  minLength?: number;
}

const isEditable = (target: EventTarget | null): boolean => {
  if (!(target instanceof HTMLElement)) return false;
  if (target.isContentEditable) return true;
  const tag = target.tagName;
  if (tag === 'TEXTAREA' || tag === 'SELECT') return true;
  if (tag !== 'INPUT') return false;
  const type = (target as HTMLInputElement).type;
  // Checkboxes, radios and buttons don't take text.
  return !['checkbox', 'radio', 'button', 'submit', 'reset', 'range', 'color', 'file'].includes(type);
};

export function useBarcodeScanner({
  onScan,
  enabled = true,
  maxGapMs = 100,
  minLength = 4,
}: BarcodeScannerOptions) {
  // The latest callback without re-subscribing the listener on every render.
  const onScanRef = useRef(onScan);
  useEffect(() => {
    onScanRef.current = onScan;
  }, [onScan]);

  useEffect(() => {
    if (!enabled) return;
    let buffer = '';
    let last = 0;

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.ctrlKey || event.altKey || event.metaKey) return;
      if (isEditable(event.target)) {
        buffer = '';
        return;
      }

      const now = performance.now();
      const gap = now - last;
      last = now;

      if (event.key === 'Enter') {
        const code = buffer.trim();
        buffer = '';
        if (code.length >= minLength && gap <= maxGapMs) {
          event.preventDefault();
          event.stopPropagation();
          onScanRef.current(code);
        }
        return;
      }

      if (event.key.length !== 1) return; // Shift, Tab, arrows…
      // A long pause means a new burst: what came before was a person.
      buffer = gap > maxGapMs ? event.key : buffer + event.key;
      if (buffer.length > 64) buffer = buffer.slice(-64);
    };

    // Capture phase, so the Enter is caught before a focused button acts on it.
    window.addEventListener('keydown', onKeyDown, true);
    return () => window.removeEventListener('keydown', onKeyDown, true);
  }, [enabled, maxGapMs, minLength]);
}

// ─────────────────────────────────────────────────────────────
//  Feedback
// ─────────────────────────────────────────────────────────────

let audio: AudioContext | null = null;

/**
 * A short beep: high for "added", low double for "not found". A counter is
 * noisy and the cashier is looking at the customer, not the screen — the
 * sound is what tells them to scan the next piece or look up.
 *
 * Browsers only allow sound after the page has been tapped once; the till has
 * been tapped long before the first scan (opening the shift), so in practice
 * this always plays. If it can't, it stays silent rather than throwing.
 */
export function scanBeep(kind: 'ok' | 'error') {
  try {
    const Ctx =
      window.AudioContext || (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
    if (!Ctx) return;
    audio = audio || new Ctx();
    if (audio.state === 'suspended') void audio.resume();
    const tones = kind === 'ok' ? [[1400, 0, 0.08]] : [[320, 0, 0.12], [320, 0.18, 0.12]];
    for (const [freq, start, duration] of tones) {
      const osc = audio.createOscillator();
      const gain = audio.createGain();
      osc.type = 'square';
      osc.frequency.value = freq;
      gain.gain.value = 0.06;
      osc.connect(gain);
      gain.connect(audio.destination);
      const t = audio.currentTime + start;
      osc.start(t);
      osc.stop(t + duration);
    }
  } catch {
    /* sound is a nicety; never let it break a sale */
  }
}
