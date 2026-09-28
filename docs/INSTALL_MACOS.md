# Install Melodex on macOS

> **Release vs development:** this guide lives on the current `main` branch. The latest tagged binary can lag behind `main`; see [Releases, main, and version numbers](RELEASES_AND_MAIN.md) if a documented feature is missing from your installed build.

This guide is for ordinary users. You do **not** need Python, Homebrew, Terminal, or Xcode when using the release build.

## 1. Download the correct Mac version

Open:

**https://github.com/Cliff-Lee/melodex/releases/latest**

Download one of these files:

- **Apple Silicon Mac:** `Melodex-macOS-arm64.dmg`
- **Intel Mac:** `Melodex-macOS-intel.dmg`

### Not sure which Mac you have?

Choose **Apple menu → About This Mac**.

- If it says **Chip: Apple M1/M2/M3/M4…**, use `arm64`.
- If it says **Processor: Intel…**, use `intel`.

## 2. Install Melodex

1. Open the downloaded `.dmg` file.
2. Drag **Melodex** into your **Applications** folder.
3. Eject the Melodex disk image.
4. Open **Applications → Melodex**.

## 3. If macOS blocks the first launch

Public preview builds may not yet be Apple-notarized. macOS may therefore warn that it cannot verify the developer.

Try this first:

1. Open **Applications** in Finder.
2. Control-click or right-click **Melodex**.
3. Choose **Open**.
4. Choose **Open** again when macOS asks.

If macOS still blocks it:

1. Open **System Settings → Privacy & Security**.
2. Scroll to the security section.
3. Find the message saying Melodex was blocked.
4. Choose **Open Anyway**.
5. Confirm the launch.

Only bypass this warning for a Melodex build you downloaded from the official GitHub repository/release page.

## 4. Add your music

On first launch:

1. Open **Sources** in the left sidebar.
2. Click **Add local folder…**.
3. Choose a folder containing your music.
4. Wait for Melodex to index the files.
5. Open **My music** to check that tracks appear.

Your original files are not moved. Melodex indexes the folders you choose.

## 5. Start listening

The simplest path is:

1. Open **Play for me**.
2. Choose how familiar or surprising you want the selection to be.
3. Start playback.
4. Open **Queue** if you want to see what is coming next.
5. Press **Flow queue** to make the upcoming sequence more musically coherent.

Useful feedback controls:

- **Keep** — remember this track as part of your taste.
- **♥** — strong positive feedback.
- **••• → Save Moment** — remember a particular point in the track.

## 6. Optional: improve Flow analysis with FFmpeg

Normal playback does not require Homebrew or FFmpeg. Some deeper local audio analysis can benefit from FFmpeg.

Advanced users can install it with:

```bash
brew install ffmpeg
```

If you do not know what Homebrew is, skip this section. Melodex should still be usable.

## 7. Optional: Jamendo independent music

Melodex includes Jamendo as a lawful reference online provider, but it does not ship a shared developer key.

To use it:

1. Obtain your own Jamendo developer `client_id`.
2. In Melodex open **Sources → Jamendo settings…**.
3. Paste your `client_id`.
4. Save the setting.
5. Search/browse Jamendo through Melodex.

See [Jamendo reference provider](JAMENDO_REFERENCE_PROVIDER.md).

## 8. Optional: connect an Android phone

Your Mac can act as a Provider Bridge for the Android app.

1. Put the Mac and Android phone on the same trusted Wi-Fi network.
2. In desktop Melodex open **Sources → Provider Bridge…**.
3. When asked whether phones/computers on your LAN may connect, choose **Yes**.
4. Melodex enables LAN access and shows the Bridge's current port and bearer token. The port is chosen by the running app; do not assume it is 8766.
5. Find the Mac's local IP address:
   - **System Settings → Network → Wi-Fi → Details**, then look for **IP Address**.
6. On Android, enter a Bridge URL in this form:

   `http://MAC-IP-ADDRESS:DISPLAYED-PORT`

   Example:

   `http://192.168.1.42:54321`

7. Enter the bearer token shown by desktop Melodex.
8. Tap **Connect**.

Treat the token like a password. Melodex keeps it while the current app session changes Bridge bind mode; after quitting/relaunching Melodex, use the newly displayed port/token.

See the full [Android guide](INSTALL_ANDROID.md).

## 9. Updating Melodex

1. Quit Melodex.
2. Download the newer `.dmg` from GitHub Releases.
3. Drag the new Melodex app into **Applications**.
4. Choose **Replace** when Finder asks.
5. Reopen Melodex.

Your Melodex data is stored separately from the application at:

`~/Library/Application Support/Melodex/`

Replacing the app should therefore not remove your taste database or settings.

## 10. Uninstalling

To remove only the application:

1. Quit Melodex.
2. Move **Applications/Melodex** to Trash.

To also remove Melodex's local settings/taste data, remove:

`~/Library/Application Support/Melodex/`

Do this only if you deliberately want to erase the local Melodex state.

## Troubleshooting

### “Melodex cannot be opened because the developer cannot be verified”

Use the **right-click → Open** method described above.

### No tracks appear after adding a folder

- confirm the folder actually contains supported audio files;
- try adding the folder again from **Sources**;
- test with a small folder first;
- see [Troubleshooting](TROUBLESHOOTING.md).

### Android cannot connect to the Mac

- both devices must be on the same LAN/Wi-Fi;
- start the Provider Bridge with **LAN access = Yes**;
- use the Mac's LAN IP, not `127.0.0.1` or `localhost`;
- check that the URL uses the exact port currently displayed by Melodex;
- after relaunching Melodex, re-copy the current port and token;
- if macOS asks whether Melodex may accept incoming connections, allow it on your trusted local network.

### I want to run the source code instead

See [Build from source](BUILD_FROM_SOURCE.md).
