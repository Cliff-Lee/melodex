# OpenAI API Compatibility

Melodex is an **OpenAI API client**, not an OpenAI model server.

## Responses API

New OpenAI configurations default to:

```text
https://api.openai.com/v1/responses
```

OpenAI recommends the Responses API for new projects while Chat Completions remains supported.

Melodex sends the compact Ask Melodex conversation/context as a stateless Responses request with `store: false`.

Official migration guide:

https://developers.openai.com/api/docs/guides/migrate-to-responses

## Chat Completions compatibility

Melodex still supports configured `/chat/completions` endpoints, including compatible local/proxy servers.

Typical OpenWebUI endpoint:

```text
http://localhost:3000/api/chat/completions
```

## Ollama

Ollama uses its native endpoint:

```text
http://localhost:11434/api/chat
```

## Authentication

OpenAI-compatible model endpoints commonly use bearer authentication.

Do not commit model credentials to Git or provider packages.

## What Ask Melodex sends

The model receives Melodex system instructions, the compact current context and the current prompt. The current desktop Ask Melodex UI passes no prior conversation history between requests.

Provider credentials, playback cookies and Bridge/MCP tokens should never be placed in model context.

## Tool calling is separate

Ask Melodex's outbound model connection is different from exposing Melodex's application actions as tools.

See [OpenAI function calling](OPENAI_FUNCTION_CALLING.md).


## Local API-key storage

In the current desktop implementation, an LLM API key entered through the GUI is stored in the local Melodex SQLite preferences database rather than an OS credential vault.

This is a documented current limitation; do not treat the local application-data directory as secret-proof storage.
