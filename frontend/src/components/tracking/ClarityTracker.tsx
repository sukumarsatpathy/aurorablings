import { useEffect } from 'react';

interface ClarityTrackerProps {
  trackingId: string;
  enabled: boolean;
}

const CLARITY_SCRIPT_ID = 'aurora-tracking-clarity-runtime';

const ClarityTracker = ({ trackingId, enabled }: ClarityTrackerProps) => {
  useEffect(() => {
    if (typeof window === 'undefined' || typeof document === 'undefined') return;
    if (!enabled || !trackingId) return;

    const existingScript = document.getElementById(CLARITY_SCRIPT_ID) as HTMLScriptElement | null;
    const expectedSrc = `https://www.clarity.ms/tag/${encodeURIComponent(trackingId)}`;
    if (existingScript) {
      if (existingScript.src !== expectedSrc) {
        existingScript.src = expectedSrc;
      }
      return;
    }

    ((c: any, l: Document, a: string, r: string, i: string) => {
      c[a] =
        c[a] ||
        function clarityProxy(...args: unknown[]) {
          (c[a].q = c[a].q || []).push(args);
        };
      const script = l.createElement(r) as HTMLScriptElement;
      script.id = CLARITY_SCRIPT_ID;
      script.async = true;
      script.src = `https://www.clarity.ms/tag/${encodeURIComponent(i)}`;
      const firstScript = l.getElementsByTagName(r)[0];
      if (firstScript?.parentNode) {
        firstScript.parentNode.insertBefore(script, firstScript);
      } else {
        l.head.appendChild(script);
      }
    })(window, document, 'clarity', 'script', trackingId);
  }, [trackingId, enabled]);

  return null;
};

export default ClarityTracker;
