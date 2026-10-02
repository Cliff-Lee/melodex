# Wikimedia Commons Audio for Melodex

Search audio files on Wikimedia Commons and preserve source/licence attribution metadata.

**Try searching:** `Bach`, `piano`, `bird song`, `Apollo 11`, `speech`, `field recording`, `pronunciation`.

Licensing varies by file. Melodex surfaces the Commons source page and machine-readable licence information when available.

Version 0.1.2 sends Melodex's descriptive User-Agent with the actual media request as required by Wikimedia's robot policy. This fixes searches that succeeded but playback returned HTTP 403 through the guarded desktop playback gateway.
