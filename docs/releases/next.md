# Next release — draft notes

**Planned target: Melodex v0.6.0. This release has not been tagged or published.** The latest downloadable release remains [v0.5.0](v0.5.0.md); its binaries do not include the changes below.

## Now Playing and Living Canvas

- Give the built-in visualizer scenes a more considered presentation, with a restrained track-colour backdrop, clearer track hierarchy and consistent scene labels.
- Combine the Musical Journey waveform and playback progress into one seekable control. Clicking, dragging and keyboard seeking remain available.
- Keep visual work bounded and separate from playback: the scenes use cached Flow data when available, do not analyse audio during playback, and retain the existing quality controls.

## Paste playlists from AI chats

- Add **Playlists → Paste from AI…** for playlists copied from ChatGPT, Claude, Gemini or another AI chat. No AI connection or API key is required.
- Accept Melodex JSON, common JSON track lists, Markdown lists or tables, plain text, CSV/TSV and M3U text. File import also supports JSON, text/CSV, XSPF and M3U/M3U8.
- Offer **Copy ChatGPT Prompt**, **Paste Clipboard**, and **Analyse Playlist** actions.
- Match artist/title requests against connected music sources, save the playlist, queue available matches and retain unmatched requests for later matching. Pasted text is not sent to an AI service; connected providers may receive search requests during matching.

## Release preparation

These notes are a development summary, not release authorization or a record of tested release binaries. Before tagging v0.6.0, check the final version surfaces, run the full repository and platform tests, verify the release assets, then move this summary to `docs/releases/v0.6.0.md` and remove this draft section. See [Releasing Melodex](../RELEASING.md).
