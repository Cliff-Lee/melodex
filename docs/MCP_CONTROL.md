# Melodex MCP / external AI control

Melodex now separates AI control into two layers:

1. the desktop app automatically starts a private authenticated control bridge on `127.0.0.1`;
2. `melodex.mcp_server` exposes that running app as standard Model Context Protocol tools.

This keeps Qt/playback inside the Melodex process while allowing OpenWebUI and desktop MCP clients to control it safely.

## Available MCP tools

- `melodex_status` — current track, queue, position, volume and playback state
- `melodex_sources` — connected source/resolver priority
- `melodex_search` — search connected providers
- `melodex_resolve` — resolve artist/title/album without playing
- `melodex_play` — resolve and play one track
- `melodex_queue` — resolve an ordered playlist and replace/append the queue
- `melodex_playback` — play/pause, next, previous, stop, clear queue
- `melodex_seek` — seek by seconds
- `melodex_volume` — set 0.0–1.0 volume
- `melodex_flow` — ask Flow to reorder the queue
- `melodex_feedback` — love/dislike/keep the current track
- `melodex_save_moment` — bookmark the current playback position

## Install the optional MCP dependency

From the `desktop` folder, activate Melodex's virtual environment and run:

```bash
python -m pip install -r requirements-mcp.txt
```

The ordinary Melodex player does **not** require MCP, so this dependency stays optional.

## OpenWebUI (recommended on the Ubuntu AI workstation)

Current OpenWebUI documentation supports native MCP using Streamable HTTP. Start Melodex first, then from `desktop` run:

```bash
python -m melodex.mcp_server --transport streamable-http --host 0.0.0.0 --port 8787
```

Get the bearer token in another terminal:

```bash
python -m melodex.mcp_server --show-token
```

In OpenWebUI, use **Settings → Admin → Integrations → External Tool Servers → Add Connection** and choose **MCP (Streamable HTTP)**.

For OpenWebUI running in Docker on the same computer, use:

```text
http://host.docker.internal:8787/mcp
```

Choose Bearer authentication and paste the token from `--show-token`.

On Linux Docker, `host.docker.internal` may need this Compose entry on the OpenWebUI service:

```yaml
extra_hosts:
  - "host.docker.internal:host-gateway"
```

Restart/recreate the OpenWebUI container after adding that entry.

The MCP HTTP server requires bearer authentication by default. Do not use `--no-auth` with `0.0.0.0`; Melodex refuses that combination.

## stdio MCP clients

For clients that launch a local MCP process, point them at the same Python environment as Melodex:

```json
{
  "mcpServers": {
    "melodex": {
      "command": "/absolute/path/to/melodex/desktop/.venv/bin/python",
      "args": ["-m", "melodex.mcp_server", "--transport", "stdio"],
      "cwd": "/absolute/path/to/melodex/desktop"
    }
  }
}
```

Melodex itself must already be running. The MCP process discovers its private control bridge automatically through Melodex's application-data directory.

## Security model

- The internal bridge binds to loopback automatically and uses a random bearer token saved with user-only permissions where the OS supports it.
- The public MCP HTTP process uses a separate persistent bearer token.
- Local filesystem paths are stripped from control/MCP responses.
- The HTTP MCP process only needs to bind `0.0.0.0` when another container or device must reach it.
- Treat the MCP bearer token like a password.

## Resolver transparency tools

With the Resolver Inspector update, MCP also exposes:

- `melodex_resolution_candidates` — inspect ranked source matches and score explanations.
- `melodex_prefer_match` — remember one provider result for one requested song.
- `melodex_wrong_match` — reject one bad result without disabling its provider.
- `melodex_reset_match_memory` — clear the per-song preference and wrong-match blocks.

These tools change resolver memory only; they do not grant an external model direct filesystem access.
