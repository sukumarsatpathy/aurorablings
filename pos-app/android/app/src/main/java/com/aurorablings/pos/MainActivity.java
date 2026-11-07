package com.aurorablings.pos;

import android.content.ActivityNotFoundException;
import android.content.Intent;
import android.net.Uri;
import android.os.Bundle;
import android.os.SystemClock;
import android.view.WindowManager;
import android.webkit.JavascriptInterface;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.widget.Toast;

import androidx.activity.OnBackPressedCallback;

import com.getcapacitor.Bridge;
import com.getcapacitor.BridgeActivity;
import com.getcapacitor.BridgeWebViewClient;

/**
 * Aurora POS — native shell around the web counter at server.url
 * (https://aurorablings.com/pos by default, see capacitor.config.ts).
 *
 * Everything POS-specific lives in the web app; this class only adds what a
 * counter device needs from the OS:
 *
 *  - The screen stays on while the app is in front.
 *  - Back never leaves the counter mid-sale. On /pos it does nothing on the
 *    first press and minimises the app on a quick second press.
 *  - Invoice PDFs and other /api or /media files open in the browser (which can
 *    print and share them) instead of a blank WebView. wa.me, upi:// and other
 *    sites already go to their own apps via Capacitor's allowNavigation rules.
 *  - A tiny JS hook (window.AuroraPos) lets the offline page retry.
 *
 * Camera access for the barcode camera needs no code here: the CAMERA
 * permission in the manifest plus Capacitor's WebChromeClient prompt for it.
 */
public class MainActivity extends BridgeActivity {

    private static final long DOUBLE_BACK_WINDOW_MS = 2000;
    private long lastBackAt = 0;

    @Override
    public void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);

        final Bridge bridge = getBridge();
        final WebView webView = bridge.getWebView();

        WebSettings settings = webView.getSettings();
        // The counter UI is designed for its own sizes; ignore the OS font scale
        // so a phone set to "large text" doesn't push buttons off-screen.
        settings.setTextZoom(100);
        settings.setUserAgentString(settings.getUserAgentString() + " AuroraPOS/" + BuildConfig.VERSION_NAME);

        bridge.setWebViewClient(new PosWebViewClient(bridge));
        webView.setDownloadListener((url, userAgent, contentDisposition, mimeType, length) -> openExternally(Uri.parse(url)));
        webView.addJavascriptInterface(new PosJsHook(), "AuroraPos");

        getOnBackPressedDispatcher().addCallback(this, new OnBackPressedCallback(true) {
            @Override
            public void handleOnBackPressed() {
                onBack(webView);
            }
        });
    }

    private void onBack(WebView webView) {
        String current = webView.getUrl();
        Uri uri = current == null ? null : Uri.parse(current);
        String path = uri == null || uri.getPath() == null ? "" : uri.getPath();
        boolean onCounter = path.startsWith("/pos");

        // Off the counter (login page, offline page): normal history back.
        if (!onCounter && webView.canGoBack()) {
            webView.goBack();
            return;
        }

        long now = SystemClock.elapsedRealtime();
        if (now - lastBackAt < DOUBLE_BACK_WINDOW_MS) {
            lastBackAt = 0;
            // Keep the app (and the open sale) alive in the background.
            moveTaskToBack(true);
        } else {
            lastBackAt = now;
            Toast.makeText(this, "Press back again to minimise the POS", Toast.LENGTH_SHORT).show();
        }
    }

    /** Files and API responses belong in the browser, not the counter WebView. */
    static boolean shouldOpenOutside(Uri url) {
        String path = url.getPath();
        if (path == null) return false;
        String lower = path.toLowerCase();
        return lower.startsWith("/api/") || lower.startsWith("/media/") || lower.endsWith(".pdf");
    }

    void openExternally(Uri url) {
        try {
            Intent intent = new Intent(Intent.ACTION_VIEW, url);
            intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            startActivity(intent);
        } catch (ActivityNotFoundException e) {
            Toast.makeText(this, "No app can open this link", Toast.LENGTH_SHORT).show();
        }
    }

    private class PosWebViewClient extends BridgeWebViewClient {
        PosWebViewClient(Bridge bridge) {
            super(bridge);
        }

        @Override
        public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
            Uri url = request.getUrl();
            String scheme = url.getScheme();
            if (request.isForMainFrame() && ("http".equals(scheme) || "https".equals(scheme)) && shouldOpenOutside(url)) {
                openExternally(url);
                return true;
            }
            return super.shouldOverrideUrlLoading(view, request);
        }
    }

    /** Exposed to page JS as window.AuroraPos (used by www/offline.html). */
    private class PosJsHook {
        @JavascriptInterface
        public void retry() {
            runOnUiThread(() -> {
                String serverUrl = getBridge().getServerUrl();
                if (serverUrl != null) getBridge().getWebView().loadUrl(serverUrl);
            });
        }

        @JavascriptInterface
        public String version() {
            return BuildConfig.VERSION_NAME;
        }
    }
}
