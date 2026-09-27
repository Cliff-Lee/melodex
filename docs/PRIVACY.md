# Privacy

Melodex is designed to be local-first.

## Stored locally

- music folder locations;
- local analysis/fingerprints;
- listening history;
- completion and skip events;
- Love / Keep feedback;
- Moments;
- saved playlists and Vibes;
- provider configuration;
- resolver preferences and wrong-match blocks.

## LLM

Nothing is sent to an LLM unless you configure one and submit a request.

When you do, Melodex sends a compact context snapshot needed for that request. Playback-only secrets are redacted from LLM/control responses, including:

- request headers;
- cookies;
- refresh/access tokens;
- signed playback URLs;
- local file paths;
- internal gateway/host-permission state.

A local Ollama model can keep the LLM workflow on your machine.

## Provider Bridge

The Bridge uses a randomly generated bearer token. Anyone who can reach the Bridge and knows that token can query exposed sources, so treat it like a password.

Do not expose the raw Bridge directly to the public internet.

## Providers

Third-party providers are executable code. Their own network behaviour and privacy practices are outside Melodex Core. Review a provider before installation.
