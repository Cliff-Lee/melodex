# 6. LLM integration

## 6.1 Rule: the LLM never talks directly to providers

The existing Melodex v15 constrained-action model should remain the boundary.

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

## 6.3 Recommended LLM actions

Keep the high-level vocabulary:

- `search_music`
- `play_track`
- `queue_track`
- `make_session`
- `flow_queue`
- `save_moment`
- `stay_here`
- `import_playlist`
- `open_view`

Optional advanced action:

```json
{
  "action": "search_music",
  "args": {
    "query": "...",
    "source": "home-server"
  }
}
```

If `source` is omitted, Melodex searches globally.

## 6.4 Why this is better than provider tools in the LLM

If every provider is exposed directly to the model, the prompt/tool surface becomes unstable and leaks infrastructure details. A single Melodex music API gives the model stable semantics and lets the resolver choose lawful/available sources.

## 6.5 OpenWebUI / Ollama

The existing Melodex OpenAPI bridge should expose high-level commands only. Provider management endpoints should not be exposed to an LLM by default.

A separate user-approved admin tool could later expose:

- list source status;
- reconnect a source;
- run source health check.

Installing new provider code should always require explicit human action.
