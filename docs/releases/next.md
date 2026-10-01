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
