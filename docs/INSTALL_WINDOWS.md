# Install Melodex on Windows

This guide is for Windows 10/11 users. You do **not** need Python, Git, PowerShell commands, or developer tools when using the normal installer.

## 1. Download Melodex

Open:

**https://github.com/Cliff-Lee/melodex/releases/latest**

For the easiest installation download:

**`Melodex-Windows-x64-Setup.exe`**

A portable version is also available:

**`Melodex-Windows-portable.zip`**

Use the installer unless you specifically want a no-install portable copy.

## 2. Install with the Setup file

1. Double-click `Melodex-Windows-x64-Setup.exe`.
2. Follow the installer steps.
3. Launch **Melodex** from the Start menu or desktop shortcut if one is created.

### If Windows SmartScreen appears

Public preview builds may not yet have a commercial code-signing certificate. Windows can therefore show **Windows protected your PC**.

If — and only if — you downloaded Melodex from the official GitHub repository/release page:

1. Click **More info**.
2. Check that the file shown is the Melodex installer you downloaded.
3. Click **Run anyway**.

Do not bypass SmartScreen for copies obtained from random download sites.

## 3. Portable installation instead

If you downloaded `Melodex-Windows-portable.zip`:

1. Right-click the ZIP and choose **Extract All…**.
2. Extract it somewhere permanent, for example:

   `C:\Users\YOUR-NAME\Apps\Melodex\`

3. Open the extracted folder.
4. Run the Melodex executable inside it.

Do not run the application while it is still inside the ZIP archive.

## 4. Add your music

1. Open **My Music**.
2. Click **+ Add music**.
3. Choose a folder containing music you are allowed to play.
4. Wait while the folder is indexed.

Your audio files remain in their original folders.

## 5. Start listening

For the easiest first session:

1. Open **Home**.
2. Choose **Play something**, or choose **Comfort**, **Explore**, or **Rediscover** first.
3. Use **Tune it…** if you want to adjust the Familiar — Adventurous control.
4. Open **Queue** to see upcoming tracks.
5. Use **Flow queue** to arrange the queue into a smoother sequence.

Useful feedback controls:

- **Keep** — tells Melodex the track belongs in your taste memory.
- **♥** — strong positive feedback.
- **••• → Save Moment** — remembers a point inside the current track.

## 6. Windows Firewall prompt

When you enable the Provider Bridge, Windows may ask whether Melodex is allowed through Windows Defender Firewall.

If you want to connect an Android phone on your home/school LAN:

- allow Melodex on **Private networks**;
- you normally do **not** need to enable **Public networks**.

If you use Melodex only on the PC, you can leave incoming LAN access disabled.

## 7. Optional: connect Android

1. Put the Windows PC and Android phone on the same trusted Wi-Fi/LAN.
2. In desktop Melodex open **Sources → Provider Bridge…**.
3. Choose **Yes** when asked whether devices on your LAN may connect.
4. Copy the bearer token Melodex displays.
5. Find the Windows PC's IPv4 address. Either:
   - open **Settings → Network & internet → Wi-Fi/Ethernet → Properties**, or
   - open Command Prompt and run `ipconfig`.
6. Look for an address such as `192.168.1.42` or `10.0.0.25`.
7. On Android set the Bridge URL to:

   `http://WINDOWS-IP:8766`

   Example:

   `http://192.168.1.42:8766`

8. Enter the current Bridge token.
9. Tap **Connect**.

Treat the token like a password. The current preview generates a new token when the Bridge is restarted.

See [Install on Android](INSTALL_ANDROID.md).

## 8. Optional: FFmpeg

Melodex can run without you manually installing FFmpeg. Deeper Flow/audio analysis may benefit from having FFmpeg available on Windows PATH.

This is an advanced optional step. If normal playback and Flow work for you, skip it.

## 9. Optional: Jamendo independent music

1. Obtain your own Jamendo developer `client_id`.
2. Open **Sources → Jamendo settings…**.
3. Paste the `client_id` and save.
4. Use Melodex search/discovery with that source.

See [Jamendo reference provider](JAMENDO_REFERENCE_PROVIDER.md).

## 10. Updating

### Installer version

1. Quit Melodex.
2. Download the newest Setup `.exe` from GitHub Releases.
3. Run it over the existing installation.

### Portable version

1. Quit Melodex.
2. Download the new portable ZIP.
3. Extract it to a new folder or replace the old program files.

Melodex's local user data is stored separately at:

`%APPDATA%\Melodex\`

Updating the program should therefore leave your local taste/settings database intact.

## 11. Uninstalling

For an installed copy, use:

**Settings → Apps → Installed apps → Melodex → Uninstall**

For a portable copy, delete the extracted program folder.

To also erase local Melodex state, delete:

`%APPDATA%\Melodex\`

Do this only if you deliberately want to remove taste history/settings.

## Troubleshooting

### SmartScreen blocks the installer

Use **More info → Run anyway** only for the official GitHub release file.

### Android cannot connect

Check:

- the PC and phone are on the same network;
- Provider Bridge was started with LAN access enabled;
- Windows Firewall allows Melodex on **Private** networks;
- Android uses the PC's IPv4 address rather than `localhost`;
- the URL includes port `8766`;
- the token is the current token from this Bridge session.

### Music does not play

Try one known-good local MP3/M4A/FLAC file first. If the issue persists, see [Troubleshooting](TROUBLESHOOTING.md).

### I want to run from source

See [Build from source](BUILD_FROM_SOURCE.md).
