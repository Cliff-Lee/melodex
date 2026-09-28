# Internet Archive provider for Melodex

A project-maintained reference `.mdxprovider` that searches and plays publicly accessible
audio from the Internet Archive.

## What it demonstrates

- public JSON search;
- item metadata lookup;
- expansion of Internet Archive items into playable audio files;
- source-page, rights and licence metadata;
- redirect-safe playback through the Melodex Playback Gateway;
- a descriptive User-Agent and conservative request pacing.

No Internet Archive account or credential is required for public metadata and
public downloads.

## Build

From the Melodex repository root:

```bash
PYTHONPATH=provider-sdk/src desktop/.venv/bin/python \
  -m melodex_provider_sdk.cli validate official-providers/internet-archive

PYTHONPATH=provider-sdk/src desktop/.venv/bin/python \
  -m melodex_provider_sdk.cli doctor official-providers/internet-archive \
  --query "Grateful Dead"

PYTHONPATH=provider-sdk/src desktop/.venv/bin/python \
  -m melodex_provider_sdk.cli pack official-providers/internet-archive \
  -o dist/internet-archive.mdxprovider
```

## Install in Melodex

1. Open **Sources**.
2. Enable **Show power tools**.
3. Choose **Install .mdxprovider…**.
4. Select `dist/internet-archive.mdxprovider`.
5. Search **Internet Archive** from Discover, or search **All sources**.

## Content rights

The provider itself is MIT-licensed. Internet Archive content has item-specific
rights and licence information. Melodex preserves the source page and available
licence/rights metadata; this provider does not claim that every Internet
Archive item is public domain.

The provider only uses public metadata/download endpoints and does not bypass
login, lending, DRM, access controls, or restricted-item protections.
