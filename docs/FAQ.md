# FAQ

## Why does macOS warn when opening Melodex?

The current public-beta Mac builds are not signed with an Apple Developer ID or notarized by Apple. macOS may block the first launch because Apple has not verified the app. If you trust the official download and choose to proceed, follow the [Mac installation guide](INSTALL_MACOS.md#3-macos-security-warning-unsigned-public-beta) for Apple's app-specific **System Settings → Privacy & Security → Open Anyway** procedure. Do **not** disable Gatekeeper globally. For data handling, see the [Privacy Policy](PRIVACY.md).

## Does Melodex need an LLM?
No. Home sessions, Flow, taste memory, lyrics browsing, and local playback work without one.

## Does Melodex include a music subscription?
No. Melodex plays music from sources you connect.

## What sources are built into the desktop app?
For streaming, the desktop app includes ccMixter, SomaFM, Radio Browser, Wikimedia Commons Audio, LibriVox, and Internet Archive Audio. Their catalogues and audio remain hosted by the original services. Local music is added from My Music. Jamendo is optional and requires your own developer client ID.

Additional project-maintained examples and community packages may be available through the repository or Plugin Directory; that does not mean they are built into the application.

## Can I add my own provider?
Yes on desktop through MPP v1 `.mdxprovider` packages. See the Provider SDK.

## Does Android need a computer or Bridge?
No. Android can play audio indexed on the phone. Provider Bridge is optional and connects Android to sources configured on another Melodex installation. Android intentionally avoids executing arbitrary downloaded provider code.

## Is my listening history uploaded?
No, unless you explicitly send relevant context to a configured external LLM as part of a prompt.

## Why is Flow better with FFmpeg installed?
FFmpeg lets Melodex decode local audio for BPM/key/energy/structure analysis. Without it, Flow degrades gracefully.

## Can I use Melodex with any third-party website?
Only if a compatible provider exists and your use of that provider complies with the source's terms and applicable law.
