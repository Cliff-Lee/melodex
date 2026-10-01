# Next release — draft notes

**Development after Melodex v0.7.2.**

This file tracks changes intended for **v0.7.3**.

## K1 — Lyrics readability

- Fixed synchronized lyrics rendering dark/black text in the dark theme.
- Clickable synchronized lyric lines now receive explicit light colours instead of relying on unsupported CSS colour inheritance in Qt rich text.
- Active, nearby and distant lyric lines keep distinct contrast levels while remaining readable.
- The same explicit colours are used in full-screen synchronized lyrics.
- Text-selection colours in the normal and full-screen lyrics browsers are explicitly dark-theme safe.

