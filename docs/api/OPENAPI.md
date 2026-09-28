# OpenAPI Support

Melodex exposes an OpenAPI 3.1 description of its local control API.

With Melodex running:

```text
http://127.0.0.1:<bridge-port>/openapi.json
```

No bearer token is required to fetch the schema. Protected operations described by the schema still require authentication.

## Why this matters

OpenAPI lets developers:

- generate clients;
- inspect routes in Swagger-compatible tooling;
- connect systems that import OpenAPI;
- validate docs against implementation;
- avoid reverse-engineering the bridge source.

## OpenAPI is not OpenAI

**OpenAPI** describes an HTTP API.

**OpenAI API** provides model inference and tool calling.

Melodex supports both concepts, but they solve different problems.

For OpenWebUI, prefer MCP when available because Melodex already exposes typed application tools through MCP.
