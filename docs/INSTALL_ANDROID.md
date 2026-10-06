# Install Melodex on Android

Melodex for Android works in two ways:

- **Play music on this phone** — browse and play audio files already stored on the device. This works without a Melodex desktop or an internet connection.
- **Connect to another Melodex** — search and play sources shared by Melodex on a computer, NAS, or home server.

The first screen offers both paths. Choose **Play something** and allow music access to start with files on the phone. Choose **Connect to another Melodex** only when you want to use a library on another device.

## What you need

For local playback, you need an Android phone with music files on it.

For a Bridge connection, also have:

- Melodex running on a Mac, Windows PC, NAS, or home server, with at least one working music source;
- both devices on the same trusted Wi-Fi/LAN;
- the computer's LAN address and the Bridge token shown by Melodex.

## Optional: prepare a computer or NAS source

Follow one of these guides:

- [Install on macOS](INSTALL_MACOS.md)
- [Install on Windows](INSTALL_WINDOWS.md)

Then open desktop Melodex and add some music:

**Sources → Add local folder…**

Confirm that the music plays on the computer before trying Android.

## Download the Android APK

On the Android device open:

**https://github.com/Cliff-Lee/melodex/releases/latest**

Download:

**`Melodex-Android.apk`**

Do **not** download `Melodex-Android.aab`. An `.aab` is an app-store publishing bundle, not the file normal users install directly.

## Allow installation of the APK

Android may say that your browser or file manager is not allowed to install unknown apps.

The exact wording varies by Android manufacturer, but normally:

1. Tap the downloaded APK.
2. When Android blocks it, choose **Settings**.
3. Enable **Allow from this source** for the browser/file manager you used for the download.
4. Go back.
5. Tap the APK again.
6. Choose **Install**.

After installation you may disable **Allow from this source** again if you prefer.

Only install APKs downloaded from the official Melodex GitHub release page.

## Connect to another Melodex (optional)

On the Mac/Windows computer:

1. Open Melodex.
2. Open **Sources**.
3. Click **Provider Bridge…**.
4. Melodex asks:

   **Allow phones/computers on your LAN to connect?**

5. Choose **Yes**.
6. Melodex starts the Bridge on port `8766`.
7. Keep the displayed **Bearer token** available — you will enter it on Android.

The token is a password for this Bridge session. Do not post it publicly.

### Find the computer's local IP address

You need the computer's LAN address so the phone knows where to connect.

### macOS

Open:

**System Settings → Network → Wi-Fi → Details**

Look for **IP Address**, for example:

`192.168.1.42`

### Windows

Open:

**Settings → Network & internet → Wi-Fi/Ethernet → Properties**

Look for **IPv4 address**.

Or open Command Prompt and run:

```text
ipconfig
```

Look for an IPv4 address similar to:

`192.168.1.42`

or

`10.0.0.25`

Do not use `127.0.0.1` or `localhost` on the phone — those refer to the phone itself.

### Connect Android to the Bridge

Open Melodex on Android.

On the **Connect** tab, enter the **Melodex address** and **Bridge token**. The address must include the port, for example `http://192.168.1.42:8766`. The token is kept only in the current app session; reconnect and enter the current token after restarting the Bridge.

### Melodex address

Enter:

`http://COMPUTER-IP:8766`

For example:

`http://192.168.1.42:8766`

### Bridge token

Paste/type the bearer token shown by desktop Melodex.

Then tap **Connect**.

A successful connection checks the token and shows the available source count. If the Bridge restarts, its token can change; enter the new token and reconnect.

### Search and play

1. Type a song, artist, or album into **Search connected music**.
2. Tap **Search**.
3. Tap a result to start playback.
4. Use **Play / Pause** and **Restart** at the bottom of the screen.

The Android preview intentionally keeps the interface simple while the richer Flow/taste UI is developed.

## 8. If Android cannot connect

Work through these checks in order.

### A. Confirm desktop playback works

If the computer cannot play/search the source, Android will not be able to either.

### B. Confirm both devices are on the same network

Guest Wi-Fi networks often prevent devices from talking to each other. If you are on school/hotel/guest Wi-Fi, client isolation may block the Bridge even when both devices appear to be on the same Wi-Fi.

Try a normal home/private LAN if possible.

### C. Check the Bridge URL

It must look like:

`http://192.168.x.x:8766`

or

`http://10.x.x.x:8766`

Do not use:

- `localhost`;
- `127.0.0.1`;
- the computer's public internet IP;
- `https://` unless you have deliberately put the Bridge behind HTTPS yourself.

### D. Check the token

The current preview generates a new bearer token when the Provider Bridge is restarted. If you closed/restarted Melodex or restarted the Bridge, copy the new token.

### E. Check Windows Firewall

If the computer runs Windows, allow Melodex on **Private networks** when Windows Defender Firewall asks.

### F. Check macOS incoming connections

If macOS asks whether Melodex may accept incoming network connections, allow it on your trusted local network.

### G. Test the Bridge health page

From the Android browser, while on the same LAN, try:

`http://COMPUTER-IP:8766/health`

For example:

`http://192.168.1.42:8766/health`

If the Bridge is reachable you should receive a small response indicating that the Melodex Provider Bridge is healthy.

If this page does not load, the problem is network/Bridge/firewall related rather than the Android search UI.

## 9. Security

The Provider Bridge is intended for a **trusted local network**.

- Treat the bearer token like a password.
- Do not post screenshots containing the token.
- Do not directly expose port `8766` to the public internet.
- For remote access, use an HTTPS reverse proxy or trusted VPN rather than raw port forwarding.

## 10. Updating Android

1. Download the new `Melodex-Android.apk` from the official GitHub Releases page.
2. Open the APK.
3. Android should offer to update the existing app.
4. Confirm the update.

## 11. Uninstalling Android

Use the normal Android path:

**Settings → Apps → Melodex → Uninstall**

## Current preview limitation

The Android preview currently requires you to enter the Bridge address/token manually. A future goal is one-step pairing (for example QR-code pairing and automatic LAN discovery), which will remove most of the network setup above.

For other problems see [Troubleshooting](TROUBLESHOOTING.md).
