# Official / Reference Provider Source

This page describes provider source code maintained in the Melodex repository.

**Availability is separate from source presence.** A provider listed here is not necessarily built into the player or listed in the canonical Plugin Directory.


Melodex keeps the desktop core source-neutral. Optional official providers are
reference integrations built on the same public MPP interface available to
third-party developers.

## Internet Archive

Source: `official-providers/internet-archive/`

Current status: source/test integration is present in the repository. It is **not built into desktop Core and is not currently an entry in the canonical Plugin Directory**.

The Internet Archive provider searches audio items, reads public item metadata,
selects a preferred playable audio representation, preserves source/licence
metadata, and resolves playback through the Melodex Playback Gateway.

It does not require credentials for public content and does not bypass lending,
login, DRM, or restricted-item access controls.

Build and install instructions are in the provider's README.
