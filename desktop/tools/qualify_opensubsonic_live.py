#!/usr/bin/env python3
"""Opt-in R1-3C live OpenSubsonic transport qualification.

Uses the real Melodex MPP subprocess and PlaybackGateway. Never prints credentials,
server URLs, stream URLs, song identities, metadata or exception messages.
Read-only. Audible Qt playback must be qualified separately.
"""
from __future__ import annotations

import getpass
import json
import os
import sys
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from melodex.playback_gateway import PlaybackGateway  # noqa: E402
from melodex.provider import ExternalProvider  # noqa: E402

PROVIDER = ROOT / "bundled_provider_sources" / "opensubsonic_personal"


def _report(steps: dict[str, bool], *, note: str) -> int:
    result = {
        "campaign": "R1-3C",
        "scope": "live private-server transport; no Qt audio output",
        "steps": steps,
        "passed": bool(steps) and all(steps.values()),
        "note": note,
    }
    print(json.dumps(result, indent=2, sort_keys=True), flush=True)
    return 0 if result["passed"] else 1


def qualify(
    *,
    server: str,
    username: str,
    password: str,
    allow_http: bool,
    query: str = "a",
) -> dict[str, bool]:
    """Return only coarse booleans. Do not return identifiers, URLs or errors."""
    manifest = json.loads((PROVIDER / "manifest.json").read_text("utf-8"))
    steps = {
        "provider_configured": False,
        "authenticated_health": False,
        "track_search": False,
        "track_lookup": False,
        "stream_resolution": False,
        "range_seek_206": False,
    }
    host = ExternalProvider(PROVIDER, manifest)
    gateway = PlaybackGateway()
    try:
        host.configure({
            "server_url": server,
            "username": username,
            "password": password,
            "allow_insecure_http": bool(allow_http),
        })
        steps["provider_configured"] = True
        health = host.health_check(timeout=10)
        if health.get("status") != "ready":
            return steps
        steps["authenticated_health"] = True
        songs = host.search(query, limit=5)
        if not songs:
            return steps
        steps["track_search"] = True
        track = songs[0]
        detailed = host._rpc("catalog.get_track", {
            "provider_track_id": track.get("provider_track_id") or track.get("track_id")
        }) or {}
        if not isinstance(detailed, dict) or not detailed.get("provider_track_id"):
            return steps
        steps["track_lookup"] = True
        resolved = host.resolve(track)
        if not resolved.get("url") and not resolved.get("stream_url"):
            return steps
        steps["stream_resolution"] = True
        playback_url = gateway.register(resolved)
        req = Request(playback_url, headers={"Range": "bytes=0-4095"})
        try:
            with urlopen(req, timeout=25) as reply:
                payload = reply.read(4096)
                steps["range_seek_206"] = (
                    reply.status == 206 and bool(payload)
                    and str(reply.headers.get("Content-Range") or "").startswith("bytes 0-")
                )
        except HTTPError:
            return steps
        return steps
    finally:
        gateway.close()
        host.close()


def main() -> int:
    print(
        "OpenSubsonic live transport probe (no URLs, track titles or tokens are logged).",
        file=sys.stderr,
    )
    server = os.environ.get("MELODEX_SUBSONIC_URL", "").strip()
    username = os.environ.get("MELODEX_SUBSONIC_USERNAME", "").strip()
    password = os.environ.get("MELODEX_SUBSONIC_PASSWORD", "")
    allow_http = os.environ.get("MELODEX_SUBSONIC_ALLOW_HTTP", "") == "1"
    query = os.environ.get("MELODEX_SUBSONIC_QUERY", "a")
    if not server or not username:
        return _report({"credentials_provided": False}, note="Set MELODEX_SUBSONIC_URL and MELODEX_SUBSONIC_USERNAME")
    if not password:
        if sys.stdin.isatty():
            password = getpass.getpass("Subsonic password (hidden input): ")
        if not password:
            return _report({"credentials_provided": False}, note="No password supplied")
    try:
        steps = qualify(
            server=server, username=username, password=password,
            allow_http=allow_http, query=query,
        )
    except Exception:
        # Untrusted urllib/HTTP exceptions can embed token-bearing query URLs.
        return _report({"live_probe_completed": False},
                       note="Live probe failed; error details intentionally suppressed")
    return _report(steps, note=(
        "Transport checks only; real Qt audio output and complete-track seeking remain untested"
    ))


if __name__ == "__main__":
    raise SystemExit(main())
