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


The same high-level action vocabulary is also exposed through MCP; choose the transport that best fits your client rather than learning a second Melodex action model.
