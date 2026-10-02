from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from urllib.error import HTTPError, URLError
from pathlib import Path

PROVIDER_ID = "org.melodex.example.openverse-audio"
API = "https://api.openverse.org/v1/audio/"
USER_AGENT = os.getenv(
    "MELODEX_USER_AGENT",
    "Melodex-Openverse-Example/0.1 (https://github.com/Cliff-Lee/melodex)",
)
CACHE: dict[str, dict] = {}


def _fixture():
    return json.loads((Path(__file__).parent / "fixtures" / "search.json").read_text(encoding="utf-8"))


def _get_json(params):
    if os.getenv("MELODEX_EXAMPLE_FIXTURES") == "1":
        return _fixture()
    url = API + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=20) as response:
        return json.load(response)


def _final_media_url(url):
    """Resolve third-party media redirects before Melodex applies host policy."""
    value = str(url or "").strip()
    if not value.startswith(("http://", "https://")):
        raise RuntimeError("Openverse item has no playable HTTP media URL")
    if os.getenv("MELODEX_EXAMPLE_FIXTURES") == "1":
        return value

    common = {
        "User-Agent": USER_AGENT,
        "Accept-Encoding": "identity",
    }

    def probe(method, extra=None):
        headers = dict(common)
        headers.update(extra or {})
        request = urllib.request.Request(value, headers=headers, method=method)
        with urllib.request.urlopen(request, timeout=20) as response:
            final = str(response.geturl() or value).strip()
            content_type = str(response.headers.get("Content-Type") or "").casefold()
            if not final.startswith(("http://", "https://")):
                raise RuntimeError("Openverse media redirected to a non-HTTP URL")
            if "text/html" in content_type:
                raise RuntimeError("Openverse media URL returned a web page instead of audio")
            return final

    try:
        return probe("HEAD")
    except HTTPError as exc:
        if exc.code not in {400, 403, 405, 501}:
            raise RuntimeError(f"Openverse media check failed: HTTP {exc.code}") from exc
    except (URLError, TimeoutError, OSError):
        pass

    try:
        return probe("GET", {"Range": "bytes=0-0"})
    except HTTPError as exc:
        raise RuntimeError(f"Openverse media check failed: HTTP {exc.code}") from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise RuntimeError(f"Openverse media check failed: {exc}") from exc


def _tags(row):
    out = []
    for item in row.get("tags") or []:
        if isinstance(item, dict):
            value = str(item.get("name") or "").strip()
        else:
            value = str(item or "").strip()
        if value and value not in out:
            out.append(value)
    return out


def _license_label(row):
    code = str(row.get("license") or "").strip()
    version = str(row.get("license_version") or "").strip()
    return " ".join(x for x in [code.upper() if code else "", version] if x).strip() or None


def _to_track(row):
    track_id = str(row.get("id") or "").strip()
    if not track_id:
        raise RuntimeError("Openverse result has no id")
    CACHE[track_id] = row
    audio_set = row.get("audio_set") if isinstance(row.get("audio_set"), dict) else {}
    return {
        "type": "track",
        "provider_id": PROVIDER_ID,
        "provider_track_id": track_id,
        "title": str(row.get("title") or "Untitled"),
        "artist": str(row.get("creator") or "Unknown creator"),
        "album": str(audio_set.get("title") or "Openverse"),
        "duration_ms": row.get("duration"),
        "artwork_url": row.get("thumbnail") or None,
        "metadata": {
            "openverse": True,
            "landing_url": row.get("foreign_landing_url"),
            "creator_url": row.get("creator_url"),
            "provider": row.get("provider"),
            "source": row.get("source"),
            "category": row.get("category"),
            "genres": row.get("genres") or [],
            "tags": _tags(row),
            "filetype": row.get("filetype"),
            "bit_rate": row.get("bit_rate"),
            "sample_rate": row.get("sample_rate"),
            "license": _license_label(row),
            "license_url": row.get("license_url"),
            "attribution": row.get("attribution"),
            "mature": bool(row.get("mature")),
        },
    }


def _find(track_id):
    row = CACHE.get(track_id)
    if row:
        return row
    if os.getenv("MELODEX_EXAMPLE_FIXTURES") == "1":
        rows = _fixture().get("results") or []
        row = next((x for x in rows if str(x.get("id")) == track_id), None)
        if row:
            CACHE[track_id] = row
            return row
    url = f"https://api.openverse.org/v1/audio/{urllib.parse.quote(track_id, safe='')}/"
    req = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=20) as response:
        row = json.load(response)
    CACHE[track_id] = row
    return row


def respond(request):
    method = request.get("method")
    params = request.get("params") or {}

    if method == "provider.info":
        return {
            "id": PROVIDER_ID,
            "name": "Openverse Audio Example",
            "version": "0.1.2",
            "protocol_version": "1.0",
            "capabilities": ["search", "track", "playback"],
        }

    if method == "provider.health":
        if os.getenv("MELODEX_EXAMPLE_FIXTURES") == "1":
            return {"status":"ready","message":"Openverse fixture is available"}
        try:
            data = _get_json({"q":"music","page_size":"1","mature":"false"})
            ready = isinstance(data, dict) and isinstance(data.get("results"), list)
            return {
                "status":"ready" if ready else "degraded",
                "message":"Openverse API is reachable" if ready else "Openverse returned an unexpected response",
            }
        except Exception as exc:
            return {"status":"unavailable","message":f"Openverse unavailable: {exc}"}

    if method == "catalog.search":
        query = str(params.get("query") or "").strip()
        raw_limit = params.get("limit")
        limit = 25 if raw_limit is None else max(1, min(int(raw_limit), 50))
        data = _get_json({"q": query, "page_size": str(limit), "mature": "false"})
        rows = data.get("results") or []
        items = []
        for row in rows[:limit]:
            if not isinstance(row, dict):
                continue
            try:
                items.append(_to_track(row))
            except RuntimeError:
                continue
        return {"items": items, "next_cursor": None}

    if method == "catalog.get_track":
        track_id = str(params.get("provider_track_id") or params.get("track_id") or "")
        return _to_track(_find(track_id))

    if method in {"playback.resolve", "playback.refresh"}:
        track_id = str(params.get("provider_track_id") or params.get("track_id") or "")
        row = _find(track_id)
        url = _final_media_url(row.get("url"))
        filetype = str(row.get("filetype") or "").casefold()
        mime = {
            "mp3": "audio/mpeg",
            "ogg": "audio/ogg",
            "opus": "audio/ogg",
            "wav": "audio/wav",
            "flac": "audio/flac",
            "m4a": "audio/mp4",
        }.get(filetype)
        return {
            "kind": "http",
            "url": url,
            "stream_url": url,
            "headers": {"User-Agent": USER_AGENT},
            "cookies": {},
            "mime_type": mime,
            "expires_at": None,
            "seekable": True,
            "cache_policy": "session",
            "refresh_token": track_id,
            "request_timeout_seconds": 30,
        }

    raise RuntimeError(f"Unsupported method: {method}")


if __name__ == "__main__":
    import sys
    for line in sys.stdin:
        if not line.strip():
            continue
        request = None
        try:
            request = json.loads(line)
            payload = {"jsonrpc": "2.0", "id": request.get("id"), "result": respond(request)}
        except Exception as exc:
            payload = {
                "jsonrpc": "2.0",
                "id": request.get("id") if isinstance(request, dict) else None,
                "error": {"code": -32000, "message": str(exc)},
            }
        print(json.dumps(payload, ensure_ascii=False), flush=True)
