import type { CapacitorConfig } from '@capacitor/cli';

/**
 * Aurora Blings POS — Android shell.
 *
 * The app does not bundle the POS UI. It opens the live counter at
 * https://aurorablings.com/pos, so every web deploy reaches the tablet with no
 * APK rebuild. The native side (MainActivity.java) only adds what a browser
 * tab can't do well at a counter: screen kept on, camera permission for the
 * barcode camera, a back button that can't exit mid-sale, and handing invoice
 * PDFs / WhatsApp links to the right app.
 *
 * Point a test build at another server with:
 *   POS_URL=http://192.168.1.20:5173/pos npm run apk:debug
 */
const POS_URL = process.env.POS_URL || 'https://aurorablings.com/pos';
const host = new URL(POS_URL).hostname;
const isHttp = POS_URL.startsWith('http://');

const config: CapacitorConfig = {
  appId: 'com.aurorablings.pos',
  appName: 'Aurora POS',
  webDir: 'www',
  server: {
    url: POS_URL,
    // Login (/login?next=/pos) and the POS share one origin. Anything else
    // (wa.me, upi://, other sites) is opened outside the app.
    allowNavigation: [host, `*.${host}`],
    cleartext: isHttp,
    // Shown from the APK when the server can't be reached.
    errorPath: 'offline.html',
  },
  android: {
    allowMixedContent: isHttp,
    // Light status bar matches the counter's white chrome.
    backgroundColor: '#ffffff',
  },
};

export default config;
