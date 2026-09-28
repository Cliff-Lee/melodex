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
melodex_sources      # source/version/permission/install metadata
melodex_extensions   # capability/permission/install metadata
melodex_search
melodex_resolve
melodex_resolution_candidates
melodex_prefer_match
melodex_wrong_match
melodex_reset_match_memory
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


## Trust/provenance visibility

`melodex_sources` and `melodex_extensions` expose installation metadata when available.

This lets an AI/controller distinguish a registry-verified install from a manual/older install without receiving provider credentials or private package contents.


## MCP parity

The public MCP server exposes the same high-level application-action vocabulary for source/extension inspection, search/resolution, resolver memory, playback, Flow, feedback and Moments.

Transport/authentication differ; the music/application concepts should not.
