# Aurora POS — Android app

A private Android app for the Aurora Blings counter. It is a native shell
(Capacitor 8) around the live POS at **https://aurorablings.com/pos**, so it is
not listed on the Play Store and every web deploy updates it automatically —
an APK rebuild is only needed when something in this folder changes.

## What the app adds over a browser tab

| | |
|---|---|
| Full screen, own launcher icon | "Aurora POS" with the AB monogram |
| Jewelry loading screen | Diamond-ring mark + wordmark while the counter loads (`brand/ring.svg`) |
| Screen stays on | Display never sleeps while the POS is open |
| Barcode camera | Camera permission is asked the first time the scanner opens |
| Bluetooth barcode scanner | Works as before (it types like a keyboard) |
| Safe back button | On the counter, Back never leaves the sale; a quick double-press only minimises the app |
| Invoices & WhatsApp | Invoice PDFs open in Chrome (print / share); WhatsApp and UPI links open their apps |
| Offline screen | If the server can't be reached, a reconnecting screen retries every 15 s and when the network returns |

## Install on a tablet or phone

1. Copy `aurora-pos-<version>.apk` to the device (WhatsApp to yourself, Drive or USB).
2. Open it. Android will ask to allow installs from that app (Files, Chrome or WhatsApp) — allow it once.
3. Open **Aurora POS**, sign in with a staff or admin account. The login stays on the device.

To update, install the newer APK over the old one. It keeps the login.

## Building

Needs JDK 21 and the Android SDK (Android Studio installs both).

```bash
cd pos-app
npm install
npm run apk          # signed release -> android/app/build/outputs/apk/release/app-release.apk
npm run apk:debug    # quick test build
```

Test against your Mac's dev server instead of production:

```bash
POS_URL=http://192.168.1.20:5173/pos npm run apk:debug
```

## Signing key — keep it safe

Release builds are signed with `android/aurora-pos-release.jks`, configured by
`android/keystore.properties`. **Both are git-ignored on purpose** (the repo is
public). Keep copies somewhere safe (password manager / Drive). If the key is
lost, the next APK cannot be installed over the existing app — you would have
to uninstall it first.

Before each new release, bump `versionCode` (+1) and `versionName` in
`android/app/build.gradle`.

## Changing the loading screen

`brand/ring.svg` is the source for the splash images, the Android 12+ launch
icon (`res/drawable-nodpi/splash_icon.png`) and the offline page. After editing
it, regenerate the PNGs with `python3 brand/render.py` (needs `pip install cairosvg pillow`).
