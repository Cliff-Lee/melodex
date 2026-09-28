# Tutorial — Use Melodex with OpenAI Function Calling

Use this when **your application** calls an OpenAI model and you want the model to operate Melodex through structured functions.

## Melodex's high-level tool vocabulary

The platform is designed around stable actions such as:

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

## Function-calling flow

1. Give the model the Melodex function definitions.
2. Receive one or more structured function calls.
3. Execute those calls locally against Melodex.
4. Return tool outputs to the model.
5. Receive the final user-facing answer.

The model should not need provider passwords, cookies, local filesystem paths or temporary CDN internals.

## Why high-level tools?

The model should ask Melodex to:

```text
search
resolve
play
queue
control
```

Melodex's resolver chooses the actual installed provider.

## Ask Melodex is separate

The built-in Ask Melodex interface can itself use OpenAI-compatible model endpoints. That outbound model connection is separate from exposing Melodex operations as tools to your own application.

See [OpenAI compatibility](../api/OPENAI_COMPATIBILITY.md).


## Tool-catalog scope

The OpenAI function catalog and MCP intentionally share a high-level vocabulary but are not guaranteed to expose every identical operation.

For example, current MCP also exposes resolver-memory mutation tools. Use the live `GET /v1/openai/tools` response rather than copying a stale function list into a long-lived client.

See [OpenAI function calling](../api/OPENAI_FUNCTION_CALLING.md).
