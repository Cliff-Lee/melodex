# Install Melodex on Android

## Two ways to listen

- **On this phone:** play audio that Android has indexed on the device. No
  computer or Bridge setup is needed.
- **Connect a Melodex:** search and play sources configured on a Mac, Windows
  PC, NAS, or home server through its Provider Bridge.

Melodex does not run downloaded provider code on Android. Local playback opens
the selected audio item through Android's media library. Bridge access is
optional.

This release includes P19a, the first Android standalone-player slice. Choose **On this phone**, grant audio access when requested, then play an indexed track or use **Play something**. Provider Bridge remains an optional second path.

## 1. Download the Android APK

On the Android device open:

**https://github.com/Cliff-Lee/melodex/releases/latest**

Download **`Melodex-Android.apk`**.

Do **not** download `Melodex-Android.aab`. An `.aab` is an app-store publishing
bundle, not the file normal users install directly.

## 2. Allow installation of the APK

Android may say that your browser or file manager is not allowed to install
unknown apps. The exact wording varies by manufacturer, but normally:

1. Tap the downloaded APK.
2. When Android blocks it, choose **Settings**.
3. Enable **Allow from this source** for the browser/file manager you used.
4. Go back, tap the APK again, then choose **Install**.

Only install APKs downloaded from the official Melodex GitHub release page.

## 3. Play music stored on the phone

1. Open Melodex and choose **On this phone**.
2. Tap **Allow music access**. Android will ask for permission to list audio
   stored on the device.
3. Tap **Play something** to start a randomly selected track, or tap a track to
   choose it yourself.
4. Use **Play / Pause** or **Restart** at the bottom.
5. Use **Refresh** after adding music to the device.

Melodex lists audio Android has indexed in its media library. If the list is
empty, check that the files are stored on the device in a music folder, allow
Melodex audio access in Android Settings, then return and tap **Refresh**.

If you deny access, you can still use **Connect a Melodex**. To allow local
music later, open **Settings → Apps → Melodex → Permissions → Music and audio**
(the exact label varies by Android version).

## 4. Optional: connect to another Melodex

For this path, the phone and computer should be on the same trusted Wi-Fi/LAN.
First confirm that the computer's Melodex can play the source you want to use.

### Start the Provider Bridge

On the Mac or Windows computer:

1. Open Melodex.
2. Open **Sources**.
3. Click **Provider Bridge…**.
4. When asked **Allow phones/computers on your LAN to connect?**, choose **Yes**.
5. Keep the displayed bearer token available. You will enter it on Android.

The token is a password for this Bridge session. Do not post it publicly.

### Find the computer's local IP address

On macOS, open **System Settings → Network → Wi-Fi → Details** and look for
**IP Address**.

On Windows, open **Settings → Network & internet → Wi-Fi/Ethernet → Properties**
and look for **IPv4 address**. Or run `ipconfig` in Command Prompt.

For example, the address may look like `192.168.1.42` or `10.0.0.25`. Do not
use `127.0.0.1` or `localhost` on the phone; those refer to the phone itself.

### Connect and play

1. In Android Melodex, choose **Connect a Melodex**.
2. For **Bridge URL**, enter `http://COMPUTER-IP:8766`, for example
   `http://192.168.1.42:8766`.
3. Enter the desktop Melodex bearer token and tap **Connect**.
4. Search for a song, artist, or other term, then tap a result to play it.

The preview asks for the Bridge address and token manually. QR pairing and
automatic LAN discovery are not available yet.

## 5. If Android cannot connect to the Bridge

Work through these checks in order.

### Confirm desktop playback and network access

If the computer cannot play/search the source, Android will not be able to
either. Guest Wi-Fi networks often prevent devices from talking to each other;
try a normal home/private LAN if possible.

### Check the Bridge URL

It must look like `http://192.168.x.x:8766` or `http://10.x.x.x:8766`.
Do not use `localhost`, `127.0.0.1`, the computer's public internet IP, or
`https://` unless you have deliberately put the Bridge behind HTTPS yourself.

### Check the token and firewall

Restarting the Bridge generates a new bearer token in the current preview. If
the computer runs Windows, allow Melodex on **Private networks** when Windows
Defender Firewall asks. If macOS asks whether Melodex may accept incoming
connections, allow it on your trusted local network.

### Test the Bridge health page

From the Android browser, while on the same LAN, open
`http://COMPUTER-IP:8766/health`. A reachable Bridge returns a small healthy
status response. If it does not load, check the network, Bridge, and firewall.

## 6. Security

The Provider Bridge is intended for a **trusted local network**.

- Treat the bearer token like a password.
- Do not post screenshots containing the token.
- Do not directly expose port `8766` to the public internet.
- For remote access, use an HTTPS reverse proxy or trusted VPN rather than raw
  port forwarding.

## 7. Background playback

Playback continues when you leave Melodex or lock the screen. Use Android's
media notification or lock-screen controls to pause or resume. Headset/Bluetooth
play/pause buttons are supported, and unplugging headphones pauses playback.

## 8. Current preview limitations

The local library still shows title, artist, and album with basic playback
controls. A persistent queue, local search, artwork, QR pairing, and Flow/taste
features are later campaign work.

## 8. Update or uninstall

To update, download the new `Melodex-Android.apk` from the official GitHub
Releases page, open it, and confirm the update.

To uninstall, use **Settings → Apps → Melodex → Uninstall**.

For other problems see [Troubleshooting](TROUBLESHOOTING.md).
