# Melodex API Changelog

## API platform v0.1

- documented the existing local REST control surface;
- added live OpenAPI 3.1 discovery at `GET /openapi.json`;
- added `GET /v1/openai/tools`;
- added strict OpenAI function definitions for core Melodex actions;
- added the `melodex-openai-tools` CLI;
- added OpenAI Responses API support to the internal LLM client;
- retained Chat Completions, OpenWebUI and Ollama compatibility;
- documented REST vs OpenAPI vs OpenAI vs MCP;
- documented token/security boundaries.
