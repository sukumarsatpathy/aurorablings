import { sanitizeTrackingConfig, validateTrackingValue } from '@/utils/validators';

const SCRIPT_IDS = {
  gtm: 'aurora-tracking-gtm',
  gtmNoscript: 'aurora-tracking-gtm-noscript',
  gtmNoscriptIframe: 'aurora-tracking-gtm-noscript-iframe',
  gtag: 'aurora-tracking-gtag',
  ga4: 'aurora-tracking-ga4',
  googleAds: 'aurora-tracking-google-ads',
  meta: 'aurora-tracking-meta',
  clarity: 'aurora-tracking-clarity',
};

const loadedState = {
  gtm: false,
  gtag: false,
  ga4: false,
  google_ads: false,
  meta: false,
  clarity: false,
  ids: {
    gtm: null,
    gtag: null,
    ga4: null,
    google_ads: null,
    meta: null,
    clarity: null,
  },
};

const ensureScript = ({ id, src, async = true }) => {
  const existing = document.getElementById(id);
  if (existing) {
    if (existing.tagName === 'SCRIPT' && existing.getAttribute('src') !== src) {
      existing.setAttribute('src', src);
    }
    return;
  }

  const alreadyPresent = Array.from(document.getElementsByTagName('script')).some((node) => {
    const nodeSrc = String(node.getAttribute('src') || node.src || '');
    return nodeSrc === src || nodeSrc.includes(src);
  });
  if (alreadyPresent) return;

  const script = document.createElement('script');
  script.id = id;
  script.async = async;
  script.src = src;
  script.referrerPolicy = 'strict-origin-when-cross-origin';
  if (document.head.firstChild) {
    document.head.insertBefore(script, document.head.firstChild);
  } else {
    document.head.appendChild(script);
  }
};

const ensureGTMNoScript = (gtmId) => {
  const iframeSrc = `https://www.googletagmanager.com/ns.html?id=${encodeURIComponent(gtmId)}`;
  const existingNoScriptIframe = Array.from(document.querySelectorAll('noscript iframe')).find((iframe) => {
    const src = String(iframe.getAttribute('src') || '');
    return (
      src.includes('https://www.googletagmanager.com/ns.html') &&
      (src.includes(`id=${encodeURIComponent(gtmId)}`) || src.includes(`id=${gtmId}`))
    );
  });
  if (existingNoScriptIframe) return;

  const existingNoScript = document.getElementById(SCRIPT_IDS.gtmNoscript);
  if (existingNoScript) {
    const existingIframe = existingNoScript.querySelector(`#${SCRIPT_IDS.gtmNoscriptIframe}`);
    if (existingIframe && existingIframe.getAttribute('src') !== iframeSrc) {
      existingIframe.setAttribute('src', iframeSrc);
    }
    return;
  }

  const noScript = document.createElement('noscript');
  noScript.id = SCRIPT_IDS.gtmNoscript;

  const iframe = document.createElement('iframe');
  iframe.id = SCRIPT_IDS.gtmNoscriptIframe;
  iframe.src = iframeSrc;
  iframe.height = '0';
  iframe.width = '0';
  iframe.style.display = 'none';
  iframe.style.visibility = 'hidden';

  noScript.appendChild(iframe);

  if (document.body.firstChild) {
    document.body.insertBefore(noScript, document.body.firstChild);
  } else {
    document.body.appendChild(noScript);
  }
};

const ensureDataLayer = () => {
  window.dataLayer = window.dataLayer || [];
  return window.dataLayer;
};

export const loadGTM = (gtmId) => {
  const result = validateTrackingValue('gtm', gtmId);
  if (!result.isValid) return false;

  const safeId = result.sanitized;
  const sameContainerLoaded = loadedState.gtm && loadedState.ids.gtm === safeId;

  ensureDataLayer();
  if (!sameContainerLoaded) {
    window.dataLayer.push({
      'gtm.start': Date.now(),
      event: 'gtm.js',
    });
  }
  ensureScript({
    id: SCRIPT_IDS.gtm,
    src: `https://www.googletagmanager.com/gtm.js?id=${encodeURIComponent(safeId)}`,
  });
  ensureGTMNoScript(safeId);
  loadedState.gtm = true;
  loadedState.ids.gtm = safeId;

  return true;
};

export const loadMetaPixel = (pixelId) => {
  const result = validateTrackingValue('meta', pixelId);
  if (!result.isValid) return false;

  const safeId = result.sanitized;
  if (!loadedState.meta) {
    if (!window.fbq) {
      // Meta's official bootstrap snippet wrapped in an idempotent guard.
      window.fbq = function fbqProxy() {
        if (window.fbq.callMethod) {
          window.fbq.callMethod.apply(window.fbq, arguments);
        } else {
          window.fbq.queue.push(arguments);
        }
      };
      window.fbq.push = window.fbq;
      window.fbq.loaded = true;
      window.fbq.version = '2.0';
      window.fbq.queue = [];
    }

    ensureScript({
      id: SCRIPT_IDS.meta,
      src: 'https://connect.facebook.net/en_US/fbevents.js',
    });
    loadedState.meta = true;
  }

  if (loadedState.ids.meta !== safeId) {
    window.fbq('init', safeId);
    window.fbq('track', 'PageView');
    loadedState.ids.meta = safeId;
  }

  return true;
};

export const loadGA4 = (gaId) => {
  const result = validateTrackingValue('ga4', gaId);
  if (!result.isValid) return false;

  const safeId = result.sanitized;
  if (!loadedState.ga4 || loadedState.ids.ga4 !== safeId) {
    ensureDataLayer();
    if (!window.gtag) {
      window.gtag = function gtag() {
        window.dataLayer.push(arguments);
      };
    }

    if (!loadedState.gtag) {
      ensureScript({
        id: SCRIPT_IDS.gtag,
        src: `https://www.googletagmanager.com/gtag/js?id=${encodeURIComponent(safeId)}`,
      });
      loadedState.gtag = true;
      loadedState.ids.gtag = safeId;
    }

    window.gtag('js', new Date());
    window.gtag('config', safeId, { send_page_view: true });
    loadedState.ga4 = true;
    loadedState.ids.ga4 = safeId;
  }

  return true;
};

export const loadGoogleAds = (adsId) => {
  const result = validateTrackingValue('google_ads', adsId);
  if (!result.isValid) return false;

  const safeId = result.sanitized;
  if (!loadedState.google_ads || loadedState.ids.google_ads !== safeId) {
    ensureDataLayer();
    if (!window.gtag) {
      window.gtag = function gtag() {
        window.dataLayer.push(arguments);
      };
    }

    if (!loadedState.gtag) {
      ensureScript({
        id: SCRIPT_IDS.gtag,
        src: `https://www.googletagmanager.com/gtag/js?id=${encodeURIComponent(safeId)}`,
      });
      loadedState.gtag = true;
      loadedState.ids.gtag = safeId;
    }

    window.gtag('js', new Date());
    window.gtag('config', safeId);
    loadedState.google_ads = true;
    loadedState.ids.google_ads = safeId;
  }

  return true;
};

export const loadClarity = (clarityId) => {
  const result = validateTrackingValue('clarity', clarityId);
  if (!result.isValid) return false;

  const safeId = result.sanitized;
  if (!loadedState.clarity || loadedState.ids.clarity !== safeId) {
    ensureScript({
      id: SCRIPT_IDS.clarity,
      src: `https://www.clarity.ms/tag/${encodeURIComponent(safeId)}`,
    });
    loadedState.clarity = true;
    loadedState.ids.clarity = safeId;
  }

  return true;
};

const applyProvider = (provider, enabled, idValue) => {
  if (!enabled || !idValue) return false;

  switch (provider) {
    case 'gtm':
      return loadGTM(idValue);
    case 'meta':
      return loadMetaPixel(idValue);
    case 'ga4':
      return loadGA4(idValue);
    case 'google_ads':
      return loadGoogleAds(idValue);
    case 'clarity':
      return loadClarity(idValue);
    default:
      return false;
  }
};

export const init = (trackingConfig) => {
  if (typeof window === 'undefined' || typeof document === 'undefined') {
    return { loaded: [], skipped: ['server_environment'] };
  }

  const safe = sanitizeTrackingConfig(trackingConfig);
  const loaded = [];
  const skipped = [];
  const mappings = [
    ['gtm', safe.enabled.gtm, safe.gtm_id],
    ['meta', safe.enabled.meta, safe.meta_pixel_id],
    ['ga4', safe.enabled.ga4, safe.ga4_id],
    ['google_ads', safe.enabled.google_ads, safe.google_ads_id],
    ['clarity', safe.enabled.clarity, safe.clarity_id],
  ];

  mappings.forEach(([provider, enabled, idValue]) => {
    const didLoad = applyProvider(provider, enabled, idValue);
    if (didLoad) loaded.push(provider);
    else skipped.push(provider);
  });

  return { loaded, skipped };
};

export const testTracking = (provider) => {
  const safeProvider = String(provider || '').trim().toLowerCase();
  const eventName = `tracking_test_${safeProvider || 'unknown'}`;
  const payload = {
    event: eventName,
    source: 'admin_tracking_settings',
    ts: Date.now(),
  };

  ensureDataLayer().push(payload);

  if ((safeProvider === 'ga4' || safeProvider === 'google_ads') && typeof window.gtag === 'function') {
    window.gtag('event', eventName, { debug_mode: true });
  }

  if (safeProvider === 'meta' && typeof window.fbq === 'function') {
    window.fbq('trackCustom', eventName, payload);
  }

  if (safeProvider === 'clarity' && typeof window.clarity === 'function') {
    window.clarity('event', eventName);
  }

  console.info(`[Tracking Test] ${safeProvider || 'unknown'} event fired`, payload);
  return payload;
};

export const initGTMConfig = (config) => {
  const enabled = Boolean(config?.is_gtm_enabled);
  const gtmId = String(config?.gtm_container_id || '').trim();
  if (!enabled || !gtmId) {
    return { loaded: false };
  }
  return { loaded: loadGTM(gtmId) };
};

export const testGTMEvent = () => {
  const payload = { event: 'gtm_test_event', source: 'admin_gtm_settings', ts: Date.now() };
  ensureDataLayer().push(payload);
  console.info('[GTM Test] Event pushed to dataLayer', payload);
  return payload;
};

const trackingLoader = {
  init,
  testTracking,
  initGTMConfig,
  testGTMEvent,
  loadGTM,
  loadMetaPixel,
  loadGA4,
  loadGoogleAds,
  loadClarity,
};

export default trackingLoader;
