# Melodex API Platform

The live OpenAPI document currently identifies the local control API as **0.2**.

API-platform versions are separate from the Melodex app version, Provider SDK version, MPP version and capability-contract versions.


Melodex has several integration surfaces. They are related, but they are not the same API and they do not necessarily expose identical tool lists.

Documentation normally describes current `main`; the latest packaged release can lag. See [Release status](../RELEASE_STATUS.md).

## 1. Local REST control API

**Direction:** external program → Melodex

Use it to search sources, resolve tracks, inspect resolver candidates, control the queue/player, record feedback and stream resolved media.

Read [Local REST API](LOCAL_REST_API.md).

## 2. OpenAPI

**Direction:** client/tool discovers Melodex's REST surface

A running Melodex bridge exposes:

```text
GET /openapi.json
```

Read [OpenAPI](OPENAPI.md).

## 3. OpenAI-compatible LLM client

**Direction:** Melodex → model server

Ask Melodex can call:

- OpenAI Responses API;
- OpenAI Chat Completions-compatible endpoints;
- OpenWebUI;
- Ollama;
- custom compatible servers.

Melodex is **not** itself an OpenAI model server.

Read [OpenAI compatibility](OPENAI_COMPATIBILITY.md).

## 4. OpenAI function tools

Melodex publishes a high-level application-action catalog as function schemas for OpenAI Responses and Chat Completions tool calling:

```text
GET /v1/openai/tools
```

Read [OpenAI function calling](OPENAI_FUNCTION_CALLING.md).

## 5. MCP

MCP is the easiest current path for OpenWebUI and other MCP-capable clients.

MCP and the OpenAI-function catalog overlap substantially, but MCP currently also exposes resolver-memory actions such as preferring/rejecting a specific match. Do not assume the two catalogs are byte-for-byte identical.

Read [MCP and OpenWebUI](MCP_AND_OPENWEBUI.md).

## Which surface should I use?

| Goal | Best surface |
| --- | --- |
| Write your own controller/app | REST API |
| Generate a typed client | OpenAPI |
| Let OpenWebUI control Melodex | MCP |
| Let an OpenAI application call Melodex functions | OpenAI function tools |
| Use OpenAI as Ask Melodex's model | Responses API |
| Use Ollama locally | Ollama `/api/chat` |
| Build a music-source integration | MPP Provider SDK |
| Build identity/metadata/artwork/lyrics enrichment | Capability Broker + `melodex-extension` |
| Inspect installed enrichment capabilities | REST `GET /v1/extensions` or `melodex_extensions` tool |
