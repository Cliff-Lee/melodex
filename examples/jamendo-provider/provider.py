#!/usr/bin/env python3
"""Jamendo MPP reference provider.

Set JAMENDO_CLIENT_ID to your own developer client ID before launching.
The provider streams only; it intentionally does not implement offline download.
"""
from __future__ import annotations
import json, os, sys, urllib.parse, urllib.request

CLIENT_ID = os.environ.get("JAMENDO_CLIENT_ID", "").strip()
API = "https://api.jamendo.com/v3.0"


def api(path, **params):
    if not CLIENT_ID:
        raise RuntimeError("Set JAMENDO_CLIENT_ID to your own Jamendo developer client ID")
    params = {"client_id": CLIENT_ID, "format": "json", **params}
    url = f"{API}/{path}/?" + urllib.parse.urlencode(params, doseq=True)
    req = urllib.request.Request(url, headers={"User-Agent": "Melodex-MPP-Jamendo-Example/1.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)


def item(x):
    tid = str(x.get("id", ""))
    return {
        "id": tid,
        "track_id": tid,
        "title": x.get("name", "Unknown track"),
        "artist": x.get("artist_name", "Unknown artist"),
        "album": x.get("album_name", ""),
        "duration": x.get("duration", 0),
        "artwork": x.get("image") or x.get("album_image") or "",
        "license_url": x.get("license_ccurl", ""),
        "source_page": x.get("shareurl") or f"https://www.jamendo.com/track/{tid}",
        "attribution": f"{x.get('artist_name','Unknown artist')} — via Jamendo"
    }


def handle(method, params):
    if method == "provider.info":
        return {"id":"org.melodex.example.jamendo","name":"Jamendo Reference Provider","version":"1.0.0"}
    if method == "provider.health":
        return {"ok": bool(CLIENT_ID), "message": "ready" if CLIENT_ID else "JAMENDO_CLIENT_ID is not set"}
    if method == "catalog.search":
        data = api("tracks", search=params.get("query", ""), limit=min(200, int(params.get("limit",25))), include="licenses", audioformat="mp32")
        return {"items":[item(x) for x in data.get("results",[])], "next_cursor": None}
    if method == "catalog.get_track":
        data = api("tracks", id=params.get("track_id", ""), limit=1, include="licenses", audioformat="mp32")
        rows = data.get("results", [])
        return item(rows[0]) if rows else None
    if method == "playback.resolve":
        data = api("tracks", id=params.get("track_id", ""), limit=1, include="licenses", audioformat="mp32")
        rows = data.get("results", [])
        if not rows: raise RuntimeError("Track unavailable")
        x = rows[0]
        return {**item(x), "stream_url": x.get("audio", ""), "expires_at": None}
    raise RuntimeError(f"Unsupported method: {method}")


for line in sys.stdin:
    try:
        req = json.loads(line)
        result = handle(req.get("method", ""), req.get("params") or {})
        out = {"jsonrpc":"2.0","id":req.get("id"),"result":result}
    except Exception as exc:
        out = {"jsonrpc":"2.0","id":req.get("id") if 'req' in locals() else None,"error":{"code":-32000,"message":str(exc)}}
    print(json.dumps(out, ensure_ascii=False), flush=True)
