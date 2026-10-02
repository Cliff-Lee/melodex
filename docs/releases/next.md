# Next release — draft notes

**Development after Melodex v0.7.5.**

This file tracks changes intended for the next release after **v0.7.5**.

## Search source cleanup

- Older SDK example copies of Radio Browser and LibriVox are hidden automatically when the newer included providers are available.
- Existing example packages are left on disk rather than deleted, but they no longer appear in Search, All Sources, or provider ordering.
- Reinstalling a superseded example provider is blocked with a message pointing to the included replacement.
