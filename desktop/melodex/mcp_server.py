from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Literal

from .control_client import MelodexControlClient, ControlError, load_or_create_mcp_http_token


def build_server(client: MelodexControlClient):
    try:
        from mcp.server import MCPServer
        from mcp.types import ToolAnnotations
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "The optional MCP dependency is not installed. Run: pip install -r requirements-mcp.txt"
        ) from exc

    mcp = MCPServer(
        "Melodex",
        instructions=(
            "Control the user's running Melodex music player. Search and resolve before claiming a track is playable. "
            "Use queue tools for playlist requests and playback tools for direct control."
        ),
    )

    read_only = ToolAnnotations(read_only_hint=True, open_world_hint=False)
    write_safe = ToolAnnotations(read_only_hint=False, destructive_hint=False, idempotent_hint=False, open_world_hint=False)

    @mcp.tool(name="melodex_status", title="Melodex status", annotations=read_only)
    def melodex_status() -> dict[str, Any]:
        """Get the current track, playback state, volume, position, and full queue."""
        return client.status()

    @mcp.tool(name="melodex_sources", title="List Melodex sources", annotations=read_only)
    def melodex_sources() -> list[dict[str, Any]]:
        """List connected music sources in resolver-priority order."""
        return client.providers()

    @mcp.tool(name="melodex_search", title="Search Melodex", annotations=read_only)
    def melodex_search(query: str, provider: str = "all", limit: int = 20) -> list[dict[str, Any]]:
        """Search connected Melodex providers for tracks. provider may be 'all' or a provider id."""
        return client.search(query, provider=provider, limit=limit)

    @mcp.tool(name="melodex_resolve", title="Resolve a track", annotations=read_only)
    def melodex_resolve(artist: str, title: str, album: str = "") -> dict[str, Any]:
        """Resolve artist/title/album metadata to Melodex's best playable source without changing playback."""
        return client.resolve(artist, title, album)

    @mcp.tool(name="melodex_resolution_candidates", title="Inspect resolver candidates", annotations=read_only)
    def melodex_resolution_candidates(artist: str, title: str, album: str = "", limit: int = 12) -> dict[str, Any]:
        """Show candidate matches, confidence components, variant flags, provider priority and remembered preference."""
        return client.resolve_candidates(artist, title, album, limit=limit)

    @mcp.tool(name="melodex_prefer_match", title="Prefer a resolver match", annotations=write_safe)
    def melodex_prefer_match(requested: dict[str, str], candidate: dict[str, Any]) -> dict[str, Any]:
        """Remember a specific provider result as the preferred match for one requested song."""
        return client.prefer_match(dict(requested), dict(candidate))

    @mcp.tool(name="melodex_wrong_match", title="Reject a resolver match", annotations=write_safe)
    def melodex_wrong_match(requested: dict[str, str], candidate: dict[str, Any]) -> dict[str, Any]:
        """Block one bad provider result for one requested song without disabling the provider."""
        return client.block_match(dict(requested), dict(candidate))

    @mcp.tool(name="melodex_reset_match_memory", title="Reset resolver memory", annotations=write_safe)
    def melodex_reset_match_memory(requested: dict[str, str]) -> dict[str, Any]:
        """Clear the preferred match and wrong-match blocks for one requested song."""
        return client.reset_match_memory(dict(requested))

    @mcp.tool(name="melodex_play", title="Play a track", annotations=write_safe)
    def melodex_play(artist: str, title: str, album: str = "") -> dict[str, Any]:
        """Resolve a track across connected sources, replace the queue with it, and start playback."""
        return client.play(artist, title, album)

    @mcp.tool(name="melodex_queue", title="Queue tracks", annotations=write_safe)
    def melodex_queue(
        tracks: list[dict[str, str]],
        replace: bool = True,
        autoplay: bool = True,
    ) -> dict[str, Any]:
        """Resolve and queue an ordered list of tracks. Each item should contain artist and title, with optional album."""
        cleaned = []
        for track in tracks:
            artist = str(track.get("artist") or "").strip()
            title = str(track.get("title") or "").strip()
            if not artist or not title:
                continue
            cleaned.append({"artist": artist, "title": title, "album": str(track.get("album") or "")})
        if not cleaned:
            raise ValueError("tracks must contain at least one item with artist and title")
        return client.queue_tracks(cleaned, replace=replace, autoplay=autoplay)

    @mcp.tool(name="melodex_playback", title="Playback control", annotations=write_safe)
    def melodex_playback(action: Literal["play_pause", "next", "previous", "stop", "clear_queue"]) -> dict[str, Any]:
        """Control playback or clear the queue."""
        return client.control(action)

    @mcp.tool(name="melodex_seek", title="Seek", annotations=write_safe)
    def melodex_seek(position_seconds: float) -> dict[str, Any]:
        """Seek the current track to an absolute position in seconds."""
        return client.control("seek_ms", value=max(0, int(float(position_seconds) * 1000)))

    @mcp.tool(name="melodex_volume", title="Set volume", annotations=write_safe)
    def melodex_volume(volume: float) -> dict[str, Any]:
        """Set playback volume from 0.0 to 1.0."""
        return client.control("set_volume", value=max(0.0, min(1.0, float(volume))))

    @mcp.tool(name="melodex_flow", title="Flow the queue", annotations=write_safe)
    def melodex_flow() -> dict[str, Any]:
        """Ask Melodex Flow to reorder the current queue for smoother musical transitions."""
        return client.control("flow_queue")

    @mcp.tool(name="melodex_feedback", title="Taste feedback", annotations=write_safe)
    def melodex_feedback(action: Literal["love", "dislike", "keep"]) -> dict[str, Any]:
        """Record taste feedback for the current track."""
        mapping = {"love": "love_current", "dislike": "dislike_current", "keep": "keep_current"}
        return client.control(mapping[action])

    @mcp.tool(name="melodex_save_moment", title="Save musical moment", annotations=write_safe)
    def melodex_save_moment(label: str = "") -> dict[str, Any]:
        """Bookmark the current playback position with an optional note."""
        return client.control("save_moment", label=label)

    return mcp


class BearerAuthMiddleware:
    def __init__(self, app, token: str):
        self.app = app
        self.token = token.encode("utf-8")

    async def __call__(self, scope, receive, send):
        if scope.get("type") == "http":
            headers = {k.lower(): v for k, v in scope.get("headers", [])}
            supplied = headers.get(b"authorization", b"")
            expected = b"Bearer " + self.token
            import secrets
            if not secrets.compare_digest(supplied, expected):
                body = b'{"error":"unauthorized"}'
                await send({"type": "http.response.start", "status": 401, "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())]})
                await send({"type": "http.response.body", "body": body})
                return
        await self.app(scope, receive, send)


def _run_http(mcp, host: str, port: int, token: str | None) -> None:
    try:
        import uvicorn
        from mcp.server.transport_security import TransportSecuritySettings
    except ModuleNotFoundError as exc:
        raise RuntimeError("MCP HTTP dependencies are missing. Run: pip install -r requirements-mcp.txt") from exc

    if host in {"127.0.0.1", "localhost", "::1"}:
        security = None
    else:
        # Bearer auth is enforced by our outer middleware. Disabling the SDK's
        # localhost Host allowlist lets OpenWebUI Docker reach host.docker.internal.
        security = TransportSecuritySettings(enable_dns_rebinding_protection=False)
    app = mcp.streamable_http_app(json_response=True, stateless_http=True, host=host, transport_security=security)
    if token:
        app = BearerAuthMiddleware(app, token)
    print(f"Melodex MCP: http://{host}:{port}/mcp", file=sys.stderr)
    if token:
        print("Bearer authentication: enabled", file=sys.stderr)
    uvicorn.run(app, host=host, port=int(port), log_level="info")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Expose a running Melodex desktop app through MCP.")
    parser.add_argument("--transport", choices=["stdio", "streamable-http"], default="stdio")
    parser.add_argument("--host", default="127.0.0.1", help="HTTP bind host (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8787, help="HTTP port (default: 8787)")
    parser.add_argument("--bridge-state", type=Path, default=None, help="Override the running Melodex bridge state file")
    parser.add_argument("--no-auth", action="store_true", help="Disable bearer auth for MCP HTTP (localhost use only)")
    parser.add_argument("--show-token", action="store_true", help="Print/create the MCP HTTP bearer token and exit")
    args = parser.parse_args(argv)

    if args.show_token:
        print(load_or_create_mcp_http_token())
        return 0

    try:
        client = MelodexControlClient.from_state(args.bridge_state)
        client.health()
        mcp = build_server(client)
        if args.transport == "stdio":
            mcp.run(transport="stdio")
        else:
            token = None if args.no_auth else load_or_create_mcp_http_token()
            if args.no_auth and args.host not in {"127.0.0.1", "localhost", "::1"}:
                raise RuntimeError("Refusing --no-auth on a non-loopback host")
            _run_http(mcp, args.host, args.port, token)
        return 0
    except (ControlError, RuntimeError) as exc:
        print(f"Melodex MCP error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
