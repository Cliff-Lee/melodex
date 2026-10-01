# Next release — draft notes

**Development after Melodex v0.7.2.**

This file tracks changes intended for **v0.7.3**.

## Campaign K — Now Playing polish

- Fix synchronized lyric contrast in the dark theme.
- Persist online lyric results locally so revisiting a track does not refetch.
- Strengthen album-art cache aliases so artwork survives raw/enriched metadata changes.
- Make Context useful even when optional context extensions are unavailable.
- Replace Artist / Releases / Credits text-browser panels with compact native presentation.
- Remove the duplicated artist photo from the Artist tab.
- Keep photo attribution clear without letting credits visually overlap artwork.
- Context plugins running in isolated packaged child processes now inherit Melodex's trusted certifi CA bundle when the OS environment does not provide one.
- Plugin Centre distinguishes temporary network/TLS failures as **Unavailable** rather than presenting every failed remote call as a broken-plugin **Error**.
- Online LRCLIB results are cached privately on-device for fast revisits and remain read-only; they are never written into the audio file.

