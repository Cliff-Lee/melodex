# 6. LLM integration

## 6.1 Rule: the LLM never talks directly to providers

Melodex's current high-level application-action boundary should remain the boundary. External AI integrations use REST/OpenAPI, MCP, or OpenAI function schemas; models do not call provider internals directly.

```text
LLM
 │ constrained Melodex action
 ▼
Melodex action executor
 │
ProviderManager / Resolver
 │
Provider(s)
```

This is important for security, portability and user experience.

## 6.2 LLM-visible source capabilities

The context may include a compact source summary:

```json
{
  "sources": [
    {"name": "This computer", "status": "ready", "search": true},
    {"name": "Home server", "status": "ready", "search": true}
  ]
}
```

Do not expose provider credentials, raw signed playback URLs or provider implementation details.

## 6.3 Current external AI actions

The public MCP/OpenAI tool vocabulary uses names such as:

- `melodex_status`
- `melodex_sources`
- `melodex_extensions`
- `melodex_search`
- `melodex_resolve`
- `melodex_resolution_candidates`
- `melodex_prefer_match`
- `melodex_wrong_match`
- `melodex_reset_match_memory`
- `melodex_play`
- `melodex_queue`
- `melodex_playback`
- `melodex_seek`
- `melodex_volume`
- `melodex_flow`
- `melodex_feedback`
- `melodex_save_moment`

The built-in Ask Melodex UI has its own constrained internal action vocabulary. That is an implementation detail of the in-app assistant, not the public external-tool contract.

For external integrations, source selection is an optional argument to `melodex_search`. If no provider is chosen, Melodex searches globally.

## 6.4 Why this is better than provider tools in the LLM

If every provider is exposed directly to the model, the prompt/tool surface becomes unstable and leaks infrastructure details. A single Melodex music API gives the model stable semantics and lets the resolver choose lawful/available sources.

## 6.5 OpenWebUI / Ollama

The Melodex REST/OpenAPI and MCP surfaces expose high-level commands only. Provider management endpoints should not be exposed to an LLM by default.

A future user-approved admin surface could expose:

- list source status;
- reconnect a source;
- run source health check.

Installing new provider code should always require explicit human action.
