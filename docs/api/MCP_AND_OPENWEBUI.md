# MCP and OpenWebUI

MCP is the recommended AI-tool integration for OpenWebUI.

## Start the Melodex MCP server

```bash
python -m pip install -r requirements-mcp.txt

python -m melodex.mcp_server \
  --transport streamable-http \
  --host 0.0.0.0 \
  --port 8787
```

Get the bearer token:

```bash
python -m melodex.mcp_server --show-token
```

## OpenWebUI

For OpenWebUI in Docker on the same machine, the MCP URL is typically:

```text
http://host.docker.internal:8787/mcp
```

Use bearer authentication.

On Linux Docker, you may need:

```yaml
extra_hosts:
  - "host.docker.internal:host-gateway"
```

## Trust / plugin visibility

MCP exposes both `melodex_sources` and `melodex_extensions`.

Those read-only tools can surface declared permissions and installation provenance without exposing provider credentials.

## REST/OpenAPI versus MCP

Use MCP for model-driven tool use.

Use REST/OpenAPI for ordinary applications, automations, generated clients and non-MCP systems.

## Security

Do not expose unauthenticated MCP on a non-loopback interface. Treat the MCP bearer token as a password.
