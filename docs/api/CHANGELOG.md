# Melodex API Changelog

API-platform versions are independent of the Melodex application and Provider SDK versions.

## API platform v0.2

Current on `main`:

- OpenAPI document reports API version `0.2`;
- added `GET /v1/extensions`;
- provider/extension listings expose version, declared permissions and installation provenance where available;
- `melodex_sources` and `melodex_extensions` expose the same trust/provenance information to OpenAI-function clients;
- MCP now exposes `melodex_extensions`;
- resolver-candidate inspection and resolver-memory endpoints/tools are documented explicitly;
- package/plugin secrets remain excluded from the high-level tool surfaces.

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
