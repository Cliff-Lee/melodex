# Install Melodex on macOS

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

## 3. macOS security warning (unsigned public beta)

> **Before you open Melodex:** The current macOS GitHub builds are **not signed with an Apple Developer ID or notarized by Apple**. You may see “Apple cannot check it for malicious software” or “the developer cannot be verified.” This does **not** mean that macOS found malware, but it does mean Apple has **not verified** the build. Only proceed if you trust its source and accept that risk.

### How to open Melodex if macOS blocks it

Apple's recommended app-specific exception method on current macOS versions is:

1. Download Melodex **only from the [official GitHub Releases page](https://github.com/Cliff-Lee/melodex/releases/latest)**, and install it using step 2 above. Do not use third-party mirrors or unexpected downloads.
2. In **Applications**, double-click **Melodex** once. If macOS blocks it, dismiss the warning with **Done** or **Cancel** (the wording depends on your macOS version).
3. Open **Apple menu → System Settings → Privacy & Security**.
4. Scroll down to **Security** and find the message about Melodex being blocked. Click **Open Anyway**. This option is normally available for roughly an hour after the blocked launch attempt.
5. Read the confirmation carefully. If you decide to continue, click **Open** and authenticate if prompted.

macOS normally remembers this **one-app exception**. You do **not** need to switch off Gatekeeper or reduce security settings for other apps.

If **Open Anyway** is not visible, retry opening Melodex once and then revisit **Privacy & Security**. On a school/work-managed Mac, an administrator may prevent exceptions.

**Important:** If macOS says **“will damage your computer,” reports malware, or says the app is damaged**, do **not** assume this is the ordinary unidentified-developer warning. Do not bypass the warning. Stop, check the download/source, and [report the issue](https://github.com/Cliff-Lee/melodex/issues/new?template=bug_report.yml) with the exact message. Never use blanket Terminal commands such as disabling Gatekeeper or stripping quarantine from all downloads.

Read [Apple's official explanation of macOS app security](https://support.apple.com/en-us/102445).

### Privacy and permissions on your Mac

- **Local music stays local during normal local playback.** Melodex indexes folders you choose; it does not move or upload your music files for local playback. An account, subscription or AI service is not required.
- **Melodex saves some local application data**, including library folder locations, listening history, preferences, playlists, and taste/Flow information under `~/Library/Application Support/Melodex/`. See the [Privacy Policy](PRIVACY.md).
- **Optional features can use the network**, including streaming providers, cover-art/metadata lookups, Plugin Directory downloads, an external AI model, or a phone Bridge. The privacy terms of those external services may apply.
- **Only grant permissions you need.** macOS may ask for access to music folders or permission to accept incoming network connections. Only allow the folders you want indexed, and enable LAN Bridge access only when using it on a trusted network. You do not need to give Melodex Full Disk Access for ordinary use.
- **Treat third-party plugins as executable software.** Melodex's desktop plugins are not fully sandboxed from your user account. Install only packages you trust. See [Security](../SECURITY.md).
- **Optional remote-LLM API keys:** If you enter an API key in Ask Melodex, the current desktop implementation stores it in local preferences rather than the macOS Keychain. See [Privacy Policy](PRIVACY.md) before entering a sensitive key.

The [Privacy Policy](PRIVACY.md) explains exactly when data can be sent to external services. Open-source code and official GitHub hosting do not replace independent security verification.

## 4. Add your music

On first launch:

1. Open **My Music**.
2. Click **+ Add music**.
3. Choose a folder containing your music.
4. Wait for Melodex to index the files.

Your original files are not moved. Melodex indexes the folders you choose.

## 5. Start listening

The simplest path is:

1. Open **Home**.
2. Choose **Play something**, or choose **Comfort**, **Explore**, or **Rediscover** first.
3. Use **Tune it…** if you want to adjust the Familiar — Adventurous control.
4. Open **Queue** if you want to see what is coming next.
5. Press **Flow queue** to arrange the upcoming tracks into a smoother sequence.

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
4. In Android Melodex choose **Connect a Melodex → Scan desktop QR code** and scan the code shown on the Mac.
5. Allow camera access when Android asks.

The code expires after two minutes and works once. The phone receives its own saved connection; you can revoke it from the desktop **Paired phones** list.

For manual setup, open **Show advanced manual setup** in the desktop pairing dialog, then use **Advanced setup** in Android. The dialog shows the Bridge URL and session token. Treat the token like a password; it changes when the Bridge restarts.

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

Follow the **System Settings → Privacy & Security → Open Anyway** instructions in section 3. Do not disable Gatekeeper.

### No tracks appear after adding a folder

- confirm the folder actually contains supported audio files;
- try adding the folder again from **Sources**;
- test with a small folder first;
- see [Troubleshooting](TROUBLESHOOTING.md).

### Android cannot connect to the Mac

- both devices must be on the same LAN/Wi-Fi;
- start the Provider Bridge with **LAN access = Yes**;
- use the Mac's LAN IP, not `127.0.0.1` or `localhost`;
- check that the URL ends in `:8766`;
- re-copy the current token if the Bridge was restarted;
- if macOS asks whether Melodex may accept incoming connections, allow it on your trusted local network.

### I want to run the source code instead

See [Build from source](BUILD_FROM_SOURCE.md).
