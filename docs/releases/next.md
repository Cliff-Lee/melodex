# Next release — draft notes

**Development after Melodex v0.7.5.**

This file tracks changes intended for the next release after **v0.7.5**.

## Search source cleanup

- Older SDK example copies of Radio Browser and LibriVox are hidden automatically when the newer included providers are available.
- Existing example packages are left on disk rather than deleted, but they no longer appear in Search, All Sources, or provider ordering.
- Reinstalling a superseded example provider is blocked with a message pointing to the included replacement.

## Provider playback reliability

- Live provider checks now verify real media bytes through the same local Playback Gateway used by the desktop player, not only by probing provider URLs directly.
- Radio-style servers get a Melodex user agent automatically, and servers that reject `HEAD` can be probed safely with a one-byte `GET`.
- LibriVox 0.1.5 allows normal Internet Archive CDN redirects such as regional `*.archive.org` hosts.
- Openverse Audio 0.1.2 resolves a selected item's final public HTTP(S) media origin before playback while keeping the gateway restricted to that concrete host.
- The live audit retries transient upstream 5xx responses and tries all returned candidates before declaring a source unavailable.
