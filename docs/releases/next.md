# Next release — draft notes

**Development after Melodex v0.7.2.**

This file tracks changes intended for **v0.7.3**.

## K1 — Lyrics readability

- Fixed synchronized lyrics rendering dark/black text in the dark theme.
- Clickable synchronized lyric lines now receive explicit light colours instead of relying on unsupported CSS colour inheritance in Qt rich text.
- Active, nearby and distant lyric lines keep distinct contrast levels while remaining readable.
- The same explicit colours are used in full-screen synchronized lyrics.
- Text-selection colours in the normal and full-screen lyrics browsers are explicitly dark-theme safe.

## K2 — Persistent Now Playing cache

- Online LRCLIB results are cached privately on-device so revisiting a track or reopening Melodex does not immediately refetch the same lyrics.
- Cached online lyrics remain read-only and are never written into the audio file.
- Now Playing warms remembered lyrics and artwork immediately before background metadata enrichment begins.
- Album artwork cache keys now include year-independent artist/album aliases so covers survive raw-versus-enriched metadata differences.
- Explicit lyric refresh still bypasses cached results when the listener asks for a fresh lookup.

## K3 — Compact artist and credit details

- Artist, Releases and Credits now use lightweight native summary panels instead of nested text-browser boxes.
- The artist photo appears once in the Now Playing hero rather than being duplicated inside the Artist tab.
- Artist membership, related projects and external links are deliberately capped to keep the tab glanceable.
- Releases show the first six release groups with direct MusicBrainz links instead of an exhaustive scrolling timeline.
- Credits are grouped by role and duplicate names are collapsed.
- Artist-photo attribution is shortened beneath the portrait, with the full attribution retained in a tooltip.

## K4 — Native Context

- Context is now a native Melodex surface rather than a plugin-owned empty state.
- Core recording, artist and relationship information is shown even when no context extension is installed.
- Optional context cards are layered underneath Core instead of replacing it.
- A temporary plugin/network failure leaves Core context visible and is reported as an optional-source problem.
- Context source management moves to a compact **Sources…** action.
- **Refresh context** retries optional enrichment without disturbing playback or the rest of Now Playing.

## K5 — Plugin health and packaged TLS

- Packaged Python provider/extension workers inherit Melodex's trusted certifi CA bundle when the parent environment has no explicit CA path.
- Existing user/system `SSL_CERT_FILE` settings remain authoritative and are not overwritten.
- TLS certificate failures, DNS/network failures and timeouts are classified as temporary **Unavailable** states rather than broken-plugin errors.
- Explicit extension health checks use the same transient-failure classification as normal capability calls.
- Plugin Centre health messaging now distinguishes temporary upstream availability from genuine extension/protocol failures.
