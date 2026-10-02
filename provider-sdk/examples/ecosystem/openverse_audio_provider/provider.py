from __future__ import annotations

import json
import os
from pathlib import Path

import requests

PROVIDER_ID = "org.melodex.example.openverse-audio"
API = "https://api.openverse.org/v1/audio/"
USER_AGENT = os.getenv(
    "MELODEX_USER_AGENT",
    "Melodex-Openverse-Example/0.1.2 (https://github.com/Cliff-Lee/melodex)",
)
CACHE: dict[str, dict] = {}
_SESSION = requests.Session()
_SESSION.headers.update({
    "User-Agent": USER_AGENT,
    "Accept": "application/json",
})


def _fixture():
    return json.loads(
        (Path(__file__).parent / "fixtures" / "search.json").read_text(
            encoding="utf-8"
        )
    )


def _get_json(params):
    if os.getenv("MELODEX_EXAMPLE_FIXTURES") == "1":
        return _fixture()
    try:
        response = _SESSION.get(API, params=params, timeout=20)
        response.raise_for_status()
        payload = response.json()
    except requests.exceptions.RequestException as exc:
        raise RuntimeError(f"Openverse request failed: {exc}") from exc
    except ValueError as exc:
        raise RuntimeError("Openverse returned invalid JSON") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("Openverse returned an invalid response")
    return payload


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
    return " ".join(
        x for x in [code.upper() if code else "", version] if x
    ).strip() or None


def _to_track(row):
    track_id = str(row.get("id") or "").strip()
    if not track_id:
        raise RuntimeError("Openverse result has no id")
    CACHE[track_id] = row
    audio_set = (
        row.get("audio_set")
        if isinstance(row.get("audio_set"), dict)
        else {}
    )
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
        row = next(
            (x for x in rows if str(x.get("id")) == track_id),
            None,
        )
        if row:
            CACHE[track_id] = row
            return row

    url = API + str(track_id).strip("/") + "/"
    try:
        response = _SESSION.get(url, timeout=20)
        response.raise_for_status()
        row = response.json()
    except requests.exceptions.RequestException as exc:
        raise RuntimeError(f"Openverse item request failed: {exc}") from exc
    except ValueError as exc:
        raise RuntimeError("Openverse returned invalid item JSON") from exc
    if not isinstance(row, dict):
        raise RuntimeError("Openverse item response was invalid")
    CACHE[track_id] = row
    return row


def _final_media_url(row: dict) -> str:
    """Resolve source/CDN redirects before handing media to Melodex.

    Openverse indexes media hosted by many upstream sites. Those URLs commonly
    redirect to a CDN host. Melodex's playback gateway intentionally restricts
    cross-host redirects, so return the final HTTPS location selected by the
    upstream server rather than making the gateway discover an undeclared host.
    """
    original = str(row.get("url") or "").strip()
    if not original:
        raise RuntimeError("Openverse item has no media URL")
    if os.getenv("MELODEX_EXAMPLE_FIXTURES") == "1":
        return original

    attempts = [
        {"Range": "bytes=0-0", "Accept": "audio/*,*/*;q=0.8"},
        {"Accept": "audio/*,*/*;q=0.8"},
    ]
    last: Exception | None = None
    for headers in attempts:
        try:
            response = _SESSION.get(
                original,
                headers=headers,
                allow_redirects=True,
                stream=True,
                timeout=20,
            )
            try:
                if response.status_code == 416 and "Range" in headers:
                    continue
                response.raise_for_status()
                final = str(response.url or original).strip()
                if final.startswith(("http://", "https://")):
                    return final
            finally:
                response.close()
        except requests.exceptions.RequestException as exc:
            last = exc

    if last is not None:
        raise RuntimeError(f"Openverse media URL could not be resolved: {last}") from last
    return original


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
            return {
                "status": "ready",
                "message": "Openverse fixture is available",
            }
        try:
            data = _get_json(
                {"q": "music", "page_size": "1", "mature": "false"}
            )
            ready = isinstance(data, dict) and isinstance(
                data.get("results"), list
            )
            return {
                "status": "ready" if ready else "degraded",
                "message": (
                    "Openverse API is reachable"
                    if ready
                    else "Openverse returned an unexpected response"
                ),
            }
        except Exception as exc:
            return {
                "status": "unavailable",
                "message": f"Openverse unavailable: {exc}",
            }

    if method == "catalog.search":
        query = str(params.get("query") or "").strip()
        raw_limit = params.get("limit")
        limit = 25 if raw_limit is None else max(
            1, min(int(raw_limit), 50)
        )
        data = _get_json(
            {
                "q": query,
                "page_size": str(limit),
                "mature": "false",
            }
        )
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
        track_id = str(
            params.get("provider_track_id")
            or params.get("track_id")
            or ""
        )
        return _to_track(_find(track_id))

    if method in {"playback.resolve", "playback.refresh"}:
        track_id = str(
            params.get("provider_track_id")
            or params.get("track_id")
            or ""
        )
        row = _find(track_id)
        url = _final_media_url(row)
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
            payload = {
                "jsonrpc": "2.0",
                "id": request.get("id"),
                "result": respond(request),
            }
        except Exception as exc:
            payload = {
                "jsonrpc": "2.0",
                "id": request.get("id")
                if isinstance(request, dict)
                else None,
                "error": {"code": -32000, "message": str(exc)},
            }
        print(json.dumps(payload, ensure_ascii=False), flush=True)
