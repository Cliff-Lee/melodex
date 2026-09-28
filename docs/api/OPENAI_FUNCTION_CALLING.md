# OpenAI Function Calling with Melodex

Melodex publishes function definitions for its high-level application controls.

Authenticated request:

```text
GET /v1/openai/tools
```

The response contains equivalent tool sets for:

```json
{
  "chat_completions": [],
  "responses": []
}
```

This is a **Melodex convenience endpoint**, not an OpenAI-standard discovery route.

## Current high-level functions

```text
melodex_status
melodex_sources
melodex_extensions
melodex_search
melodex_resolve
melodex_resolution_candidates
melodex_play
melodex_queue
melodex_playback
melodex_seek
melodex_volume
melodex_flow
melodex_feedback
melodex_save_moment
```

## Strict schemas

Melodex function schemas use strict mode and set `additionalProperties: false`. Optional inputs are represented as nullable required properties so they satisfy OpenAI strict-function schema requirements.

Official guide:

https://developers.openai.com/api/docs/guides/function-calling

## CLI

```bash
melodex-openai-tools list --format responses
melodex-openai-tools list --format chat
```

Execute a tool against the running app:

```bash
melodex-openai-tools call melodex_search \
  '{"query":"ambient","provider":null,"limit":10}'
```

## Architecture rule

Models get a stable high-level vocabulary. They should not need to know which provider is installed, how provider authentication works, where local files live, or which playback URL is temporary.
