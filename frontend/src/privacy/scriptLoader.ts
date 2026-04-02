import type { ConsentCategory, ConsentPayload } from './consentManager';

interface DeferredScript {
  id: string;
  category: Exclude<ConsentCategory, 'necessary'>;
  src?: string;
  content?: string;
  attrs?: Record<string, string>;
  onDisable?: () => void;
}

const loadedScripts = new Set<string>();
const deferredScripts: DeferredScript[] = [];

const appendScript = (script: DeferredScript): void => {
  if (loadedScripts.has(script.id)) return;

  const el = document.createElement('script');
  el.async = true;
  el.dataset.cookieScriptId = script.id;

  if (script.src) {
    el.src = script.src;
  }
  if (script.content) {
    el.text = script.content;
  }
  Object.entries(script.attrs || {}).forEach(([key, value]) => {
    el.setAttribute(key, value);
  });

  document.head.appendChild(el);
  loadedScripts.add(script.id);
};

const removeScript = (scriptId: string): void => {
  document.querySelectorAll(`script[data-cookie-script-id="${scriptId}"]`).forEach((node) => {
    node.parentElement?.removeChild(node);
  });
  loadedScripts.delete(scriptId);
};

export const registerDeferredScript = (script: DeferredScript): void => {
  if (deferredScripts.some((item) => item.id === script.id)) return;
  deferredScripts.push(script);
};

export const loadDeferredScripts = (consent: ConsentPayload | null): void => {
  if (!consent) return;

  deferredScripts.forEach((script) => {
    if (consent.categories[script.category]) {
      appendScript(script);
    }
  });
};

export const applyConsentSideEffects = (current: ConsentPayload | null, previous: ConsentPayload | null): void => {
  deferredScripts.forEach((script) => {
    const had = previous?.categories[script.category] ?? false;
    const hasNow = current?.categories[script.category] ?? false;

    if (!had && hasNow) {
      appendScript(script);
    }

    if (had && !hasNow) {
      removeScript(script.id);
      script.onDisable?.();
    }
  });
};

const readEnv = (key: string): string => {
  const value = import.meta.env[key as keyof ImportMetaEnv];
  return typeof value === 'string' ? value.trim() : '';
};

const gaMeasurementId = readEnv('VITE_GA_MEASUREMENT_ID');
if (gaMeasurementId) {
  registerDeferredScript({
    id: 'google-analytics-tag',
    category: 'analytics',
    src: `https://www.googletagmanager.com/gtag/js?id=${encodeURIComponent(gaMeasurementId)}`,
    attrs: { crossorigin: 'anonymous' },
  });
  registerDeferredScript({
    id: 'google-analytics-init',
    category: 'analytics',
    content: `window.dataLayer=window.dataLayer||[];function gtag(){dataLayer.push(arguments);}gtag('js', new Date());gtag('config', '${gaMeasurementId}');`,
    onDisable: () => {
      const key = `ga-disable-${gaMeasurementId}`;
      (window as unknown as Record<string, unknown>)[key] = true;
    },
  });
}

const metaPixelId = readEnv('VITE_META_PIXEL_ID');
if (metaPixelId) {
  registerDeferredScript({
    id: 'meta-pixel-bootstrap',
    category: 'marketing',
    content: `!function(f,b,e,v,n,t,s){if(f.fbq)return;n=f.fbq=function(){n.callMethod?n.callMethod.apply(n,arguments):n.queue.push(arguments)};if(!f._fbq)f._fbq=n;n.push=n;n.loaded=!0;n.version='2.0';n.queue=[];t=b.createElement(e);t.async=!0;t.src=v;s=b.getElementsByTagName(e)[0];s.parentNode.insertBefore(t,s)}(window, document,'script','https://connect.facebook.net/en_US/fbevents.js');fbq('init', '${metaPixelId}');fbq('track', 'PageView');`,
    onDisable: () => {
      const globalRef = window as unknown as Record<string, unknown>;
      if (typeof globalRef.fbq === 'function') {
        try {
          (globalRef.fbq as (...args: unknown[]) => void)('consent', 'revoke');
        } catch {
          // no-op
        }
      }
      delete globalRef.fbq;
      delete globalRef._fbq;
    },
  });
}
