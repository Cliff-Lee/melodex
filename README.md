# Melodex

**Don't shuffle. Flow.**

Melodex is a source-neutral music player that turns the music you already have access to into continuous, personalised listening journeys. It combines local audio analysis, Flow sequencing, taste memory, optional LLM control, and an open provider system.

## What ships in this repository

- **Desktop app** for macOS and Windows (Python + PySide6)
- **Android app** that connects safely to a Melodex Provider Bridge
- **Local Files provider** built in
- **Jamendo reference provider** built in (requires your own Jamendo developer client ID)
- **Provider Bridge** for Android / LAN clients
- **Melodex Provider SDK (MPP v1)** for third-party music sources
- complete user, LLM, provider-user, build, privacy and troubleshooting documentation
- GitHub Actions workflows for macOS, Windows and Android release artifacts

## Core features

- Flow queue: local DSP analysis chooses genre-appropriate sequencing and transitions
- Play for Me: local taste learning, rediscovery, recency control and controlled surprise
- Familiar ↔ Surprising control
- Moments and playlists
- local taste memory
- optional OpenWebUI / Ollama / OpenAI-compatible assistant
- source-neutral search
- installable `.mdxprovider` packages on desktop
- authenticated Provider Bridge for Android and other clients

## Quick start — desktop

```bash
cd desktop
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
python run.py
```

Then choose **Sources → Add local folder**.

For online independent music, add your own Jamendo developer `client_id` under **Sources → Jamendo settings**.

## Quick start — Android

The Android app is a Provider Bridge client. Start Melodex on a desktop/NAS, choose **Sources → Provider Bridge**, then enter the displayed URL and bearer token in the Android app.

See [`docs/INSTALL_ANDROID.md`](docs/INSTALL_ANDROID.md).

## Providers

Melodex Core does not know about arbitrary music websites. Providers implement the public Melodex Provider Protocol (MPP).

Developer docs: [`docs/PROVIDER_DEVELOPMENT.md`](docs/PROVIDER_DEVELOPMENT.md)

Full SDK: [`provider-sdk/`](provider-sdk/)

## Privacy

Local listening history, Flow fingerprints and taste memory stay on your device. LLM data is sent only if you explicitly configure an LLM connection. Provider credentials stay with the provider configuration and are never included in LLM context.

## Responsible source policy

Melodex is a general-purpose player and provider framework. The public project ships only with Local Files and a Jamendo reference integration. Third-party providers are separate software; provider authors and users are responsible for having permission to access and expose media from their source.

See [`RESPONSIBLE_USE.md`](RESPONSIBLE_USE.md) for the repository's full source, security and contribution policy.

## Releases

Push a tag such as `v0.1.0` to run the native GitHub Actions release builds for:

- macOS `.dmg` / app archive
- Windows `.exe` installer / portable archive
- Android `.apk` and `.aab`

See [`docs/RELEASING.md`](docs/RELEASING.md).

## License

MIT for Melodex code in this repository unless a subdirectory states otherwise. Third-party dependencies retain their own licences.
