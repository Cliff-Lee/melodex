# First-party Reference Providers

Melodex keeps desktop Core source-neutral.

This page documents provider implementations maintained in the Melodex repository but **not built into Core**. They use the same public MPP interface available to third-party developers.

“First-party reference” means maintained as a Melodex example/integration. It is not a claim that Melodex owns, endorses, or grants rights in the upstream service or media.

## Internet Archive

Source: `official-providers/internet-archive/`

The Internet Archive provider searches audio items, reads public item metadata,
selects a preferred playable audio representation, preserves source/licence
metadata, and resolves playback through the Melodex Playback Gateway.

It does not require credentials for public content and does not bypass lending,
login, DRM, or restricted-item access controls.

Build and install instructions are in the provider's README.
