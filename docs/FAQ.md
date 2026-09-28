# FAQ

## Does Melodex need an LLM?

No. Local playback, Flow, Play for Me and taste memory do not require an LLM.

## Does Melodex include a music subscription?

No. Melodex plays music from sources you connect or install.

## What sources are built into the desktop source tree?

The current desktop Core initializes:

- **Local Files**;
- **Jamendo (reference provider)** — requires your own developer client ID;
- **User Streams** — URLs/stream playlists you explicitly add.

Additional providers/extensions can be installed separately, including entries exposed through the Plugin Directory on current `main`.

## Why does the documentation mention something I cannot find in my installed release?

The documentation normally describes current `main`, while the latest packaged release can lag behind it.

See [Release status](RELEASE_STATUS.md).

## Can I add my own provider?

Yes on desktop through `.mdxprovider` packages using the MPP **1.0 preview** contract.

Start with the [5-minute developer quickstart](DEVELOPER_QUICKSTART.md).

## Can I add only artwork/metadata/lyrics without writing a playback provider?

Yes. Current `.mdxplugin` capability contracts cover identity, metadata, artwork and lyrics.

Those contracts are **experimental v0.1**, not yet a stable long-term compatibility promise.

## Why does Android use a Bridge?

The Android preview intentionally avoids executing arbitrary downloaded provider/plugin code.

It connects to a Melodex Bridge running on a computer/server and currently offers a deliberately small search/resolve/playback experience.

## Is my listening history uploaded to Melodex?

The current public code has no Melodex-operated telemetry/account backend.

Connected third-party services receive requests needed to use them, and an LLM receives context only when you configure/use that integration.

See [Privacy](PRIVACY.md).

## Why is Flow better with FFmpeg installed?

FFmpeg lets Melodex decode local audio for deeper analysis. Without it, Flow can operate with reduced analysis.

## Can I use Melodex with any third-party website?

Only if a compatible integration exists and your use complies with the source's terms, permissions and applicable law.

Melodex's extension architecture is not a permission to bypass a service's access controls.

## Is a “registry-verified” plugin signed by its publisher?

No.

Registry verification currently means the downloaded package matched registry size/SHA-256 plus package ID/version.

Cryptographic publisher signing is planned but not implemented.
