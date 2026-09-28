# Project-maintained reference providers

Melodex keeps the desktop core source-neutral. Project-maintained reference providers are
reference integrations built on the same public MPP interface available to
third-party developers.

## Internet Archive

Source: `official-providers/internet-archive/`

The `official-providers/` directory name is historical repository organization. It is **not** a registry trust status and does not imply publisher signing or blanket rights approval.

The Internet Archive provider searches audio items, reads public item metadata,
selects a preferred playable audio representation, preserves source/licence
metadata, and resolves playback through the Melodex Playback Gateway.

It does not require credentials for public content and does not bypass lending,
login, DRM, or restricted-item access controls.

Build and install instructions are in the provider's README.
