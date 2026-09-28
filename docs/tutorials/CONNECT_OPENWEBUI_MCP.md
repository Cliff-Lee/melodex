# Tutorial — Connect OpenWebUI to Melodex with MCP

MCP is the recommended AI-tool path for OpenWebUI.

## 1. Start Melodex

The desktop app must be running.

## 2. Install optional MCP dependencies

From `desktop/`:

```bash
python -m pip install -r requirements-mcp.txt
```

## 3. Start the MCP server

```bash
python -m melodex.mcp_server \
  --transport streamable-http \
  --host 0.0.0.0 \
  --port 8787
```

## 4. Get the bearer token

```bash
python -m melodex.mcp_server --show-token
```

## 5. Configure OpenWebUI

In OpenWebUI:

```text
Settings
→ Admin
→ Integrations
→ External Tool Servers
→ Add Connection
→ MCP (Streamable HTTP)
```

For OpenWebUI running in Docker on the same machine:

```text
http://host.docker.internal:8787/mcp
```

Use Bearer authentication and paste the MCP token.

Linux Docker may require:

```yaml
extra_hosts:
  - "host.docker.internal:host-gateway"
```

## What the model can do

The MCP server exposes high-level tools for search, resolution, playback, queueing, Flow, feedback and Moments.

It does not give the model arbitrary filesystem access.

## Security

Do not run unauthenticated MCP on a non-loopback address. Treat the MCP bearer token like a password.

See [MCP control](../MCP_CONTROL.md).
