# Optional LLM integration

Melodex does not require AI. Flow and Play for Me work locally.

An LLM can be connected for natural-language control and playlist intent.

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

Melodex sends a compact context snapshot only when you ask the LLM something. It may include the current track, upcoming queue, taste summary and recent listening. Provider passwords, cookies and bearer tokens are not sent.

A local Ollama model can keep the entire LLM workflow on your machine.
