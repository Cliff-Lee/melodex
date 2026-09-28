# Melodex API Changelog

This changelog describes the public integration surfaces on the repository's development line. It is separate from the Melodex app version.

## Unreleased / current `main`

- added `GET /v1/extensions` for installed capability extensions;
- provider and extension listings expose declared permission/install-provenance metadata where available;
- added resolver-candidate inspection and resolver-memory correction operations;
- OpenAI function tools and MCP now share the same high-level Melodex tool-name set;
- added `melodex_extensions`;
- added `melodex_prefer_match`, `melodex_wrong_match`, and `melodex_reset_match_memory` to OpenAI function tools;
- retained strict OpenAI schemas and authenticated local control boundaries.

## API platform v0.1

- documented the local REST control surface;
- added live OpenAPI 3.1 discovery at `GET /openapi.json`;
- added `GET /v1/openai/tools`;
- added strict OpenAI function definitions for core Melodex actions;
- added the `melodex-openai-tools` CLI;
- added OpenAI Responses API support to the internal LLM client;
- retained Chat Completions, OpenWebUI and Ollama compatibility;
- documented REST vs OpenAPI vs OpenAI vs MCP;
- documented token/security boundaries.

The API-platform version is documentation/history for the integration surface; it is not the same number as the Melodex app, Provider SDK or MPP protocol version.
