# Optional LLM integration

Melodex does not require AI. Flow and Play for Me work locally.

An LLM can be connected for natural-language control and playlist intent.

If you use ChatGPT, Claude, Gemini or another AI separately, you can copy its playlist into **Playlists → Paste from AI…** without connecting an LLM to Melodex. That workflow is separate from **Ask Melodex → Connect LLM**; see [Playlist interchange](PLAYLIST_INTERCHANGE.md).

Supported wire formats:

- OpenWebUI / OpenAI-compatible chat completions
- Ollama `/api/chat`
- OpenAI
- custom OpenAI-compatible endpoint

Open **Ask Melodex → Connect LLM** and provide provider, endpoint, model and optional API key.

## Good prompts

- “Keep this mood but make the next hour stranger.”
- “Give me a 90-minute session with less vocal music.”
- “Flow this queue.”
- “Save this moment as ‘great bass entrance’.”
- “Search for music by this artist.”

## Privacy

Melodex sends model context only when you submit an Ask Melodex prompt.

The current GUI context can include the current track, up to 12 upcoming queue items, current page, taste summary, up to 15 recent tracks and up to 10 saved Vibes.

The current GUI does not persist/send prior Ask Melodex chat history between requests.

Pasted playlists are parsed in Melodex and are not sent to an AI service. To find playable matches, Melodex may send artist/title search requests to the music providers you have connected.

Track dictionaries are reduced through a positive allowlist before model submission. Absolute local paths, provider-local track IDs, playback URLs, request headers, cookies, refresh tokens, Bridge/MCP tokens and API keys are excluded from track context.

**Current credential-storage limitation:** an LLM API key entered in the GUI is stored in Melodex's local SQLite preferences database, not an OS credential vault. See [Privacy](PRIVACY.md).

A local Ollama model can keep model inference on your machine.
