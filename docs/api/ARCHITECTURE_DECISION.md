# API Architecture Decision

## Decision

Do not make Melodex pretend to be an OpenAI-compatible model.

Melodex is a music application and tool provider.

Its public integration layers are:

```text
REST / OpenAPI
MCP
OpenAI function schemas
MPP provider protocol
```

Its optional model client can call OpenAI-compatible model endpoints.

## Why not expose a fake model endpoint?

An OpenAI-style model route convention means "model inference" to clients.

Melodex does not itself provide a language model. Mixing model selection, conversation state, tool orchestration and music control into one fake model endpoint would make the architecture harder to document, secure and evolve.

Instead:

- model clients use model-service endpoints;
- tool clients use MCP or Melodex REST/OpenAPI;
- OpenAI SDK developers can use Melodex's function schemas.
