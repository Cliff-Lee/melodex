from __future__ import annotations

import json
import sys
import time
from urllib.parse import quote

import requests

PROVIDER_ID = "org.melodex.internetarchive.audio"
NAME = "Internet Archive Audio"
VERSION = "0.1.2"
SEARCH = "https://archive.org/advancedsearch.php"
UA = "Melodex-InternetArchive/0.1.2 (+https://github.com/Cliff-Lee/melodex)"
AUDIO_EXT = (".mp3", ".ogg", ".oga", ".flac", ".wav", ".m4a", ".aac", ".opus")

_SESSION = requests.Session()
_SESSION.headers.update({
    "User-Agent": UA,
    "Accept": "application/json",
    "Accept-Encoding": "identity",
})
_CACHE: dict[str, dict] = {}
_META_CACHE: dict[str, dict] = {}


def _json(url: str, *, params: list[tuple[str, str]] | dict | None = None, timeout: float = 12.0):
    last: Exception | None = None
    for attempt in range(2):
        try:
            response = _SESSION.get(url, params=params, timeout=timeout)
            if response.status_code == 429:
                retry = response.headers.get("Retry-After") or "later"
                raise RuntimeError(f"Internet Archive rate limited; retry {retry}")
            response.raise_for_status()
            return response.json()
        except (requests.exceptions.RequestException, ValueError, RuntimeError) as exc:
            last = exc
            if attempt == 0:
                time.sleep(0.35)
    raise RuntimeError(f"Internet Archive request failed: {last}")


def _metadata(identifier: str) -> dict:
    identifier = str(identifier or "").strip()
    if not identifier:
        raise RuntimeError("Missing Internet Archive identifier")
    cached = _META_CACHE.get(identifier)
    if cached is not None:
        return cached
    data = _json("https://archive.org/metadata/" + quote(identifier, safe=""))
    if not isinstance(data, dict):
        raise RuntimeError("Internet Archive returned invalid metadata")
    _META_CACHE[identifier] = data
    return data


def _best_file(meta: dict):
    candidates = []
    for row in meta.get("files") or []:
        if not isinstance(row, dict):
            continue
        name = str(row.get("name") or "")
        lower = name.casefold()
        if not lower.endswith(AUDIO_EXT):
            continue
        fmt = str(row.get("format") or "").casefold()
        score = 0
        if lower.endswith(".mp3"):
            score += 100
        elif lower.endswith((".ogg", ".oga", ".opus")):
            score += 80
        elif lower.endswith(".flac"):
            score += 70
        if "vbr mp3" in fmt:
            score += 20
        if str(row.get("source") or "").casefold() == "original":
            score += 8
        try:
            if int(row.get("size") or 0) > 0:
                score += 2
        except (TypeError, ValueError):
            pass
        candidates.append((score, row))
    return max(candidates, key=lambda item: item[0])[1] if candidates else None


def _value(value, default="") -> str:
    if isinstance(value, list):
        return "; ".join(str(x) for x in value if str(x).strip())
    text = str(value or "").strip()
    return text or default


def _search_track(doc: dict) -> dict | None:
    identifier = str(doc.get("identifier") or "").strip()
    if not identifier:
        return None
    item = {
        "type": "track",
        "provider_id": PROVIDER_ID,
        "track_id": identifier,
        "provider_track_id": identifier,
        "title": _value(doc.get("title"), identifier),
        "artist": _value(doc.get("creator"), "Internet Archive contributor"),
        "album": "Internet Archive",
        "source_page": "https://archive.org/details/" + quote(identifier, safe=""),
        "artwork_url": "https://archive.org/services/img/" + quote(identifier, safe=""),
        "attribution": "Internet Archive item — check the item page for rights/licence information",
        "metadata": {"archive_identifier": identifier},
    }
    _CACHE[identifier] = item
    return item


def _enriched_track(identifier: str) -> dict:
    base = dict(_CACHE.get(identifier) or _search_track({"identifier": identifier}) or {})
    meta = _metadata(identifier)
    file_row = _best_file(meta)
    if not file_row:
        raise RuntimeError("Archive item has no playable audio file")

    md = meta.get("metadata") if isinstance(meta.get("metadata"), dict) else {}
    filename = str(file_row.get("name") or "")
    media = (
        "https://archive.org/download/"
        + quote(identifier, safe="")
        + "/"
        + quote(filename)
    )
    base.update({
        "title": _value(md.get("title"), base.get("title") or identifier),
        "artist": _value(md.get("creator"), base.get("artist") or "Internet Archive contributor"),
        "metadata": {
            **dict(base.get("metadata") or {}),
            "media_url": media,
            "format": str(file_row.get("format") or ""),
            "description": _value(md.get("description")),
        },
    })
    _CACHE[identifier] = base
    return base


def _search(query: str, limit: int) -> list[dict]:
    limit = max(1, min(int(limit), 25))
    q = str(query or "").strip()
    if not q:
        return []
    # Important: do not fetch /metadata for every search hit. That was the
    # source of the old provider's timeouts. Resolve file metadata lazily.
    params = [
        ("q", f"mediatype:audio AND ({q})"),
        ("fl[]", "identifier"),
        ("fl[]", "title"),
        ("fl[]", "creator"),
        ("rows", str(limit)),
        ("page", "1"),
        ("output", "json"),
    ]
    data = _json(SEARCH, params=params)
    docs = ((data.get("response") or {}).get("docs") or []) if isinstance(data, dict) else []
    out = []
    for doc in docs:
        if not isinstance(doc, dict):
            continue
        track = _search_track(doc)
        if track:
            out.append(track)
    return out[:limit]


def _get(identifier: str) -> dict:
    return _enriched_track(str(identifier or "").strip())


def _resolve(identifier: str) -> dict:
    track = _enriched_track(str(identifier or "").strip())
    url = str((track.get("metadata") or {}).get("media_url") or "").strip()
    if not url:
        raise RuntimeError("Archive item has no playable media URL")
    lower = url.casefold()
    mime = "audio/mpeg" if lower.endswith(".mp3") else None
    return {
        "kind": "http",
        "url": url,
        "stream_url": url,
        "headers": {"User-Agent": UA},
        "mime_type": mime,
        "expires_at": None,
        "seekable": True,
        "cache_policy": "session",
        "refresh_token": identifier,
        "request_timeout_seconds": 25,
    }


def respond(request: dict):
    method = str(request.get("method") or "")
    params = dict(request.get("params") or {})
    if method == "provider.info":
        return {
            "id": PROVIDER_ID,
            "name": NAME,
            "version": VERSION,
            "protocol_version": "1.0",
            "description": "Search publicly accessible Internet Archive audio; rights vary item by item.",
            "capabilities": ["search", "track", "playback"],
        }
    if method == "provider.health":
        try:
            data = _json(
                SEARCH,
                params={"q": "mediatype:audio", "fl[]": "identifier", "rows": "1", "output": "json"},
                timeout=8.0,
            )
            ready = isinstance(data, dict) and isinstance((data.get("response") or {}).get("docs"), list)
            return {
                "status": "ready" if ready else "degraded",
                "message": "Internet Archive search is reachable" if ready else "Internet Archive returned an unexpected response",
            }
        except Exception as exc:
            return {"status": "unavailable", "message": f"Internet Archive unavailable: {exc}"}
    if method == "catalog.search":
        return {
            "items": _search(str(params.get("query") or ""), int(params.get("limit") or 20)),
            "next_cursor": None,
        }
    if method == "catalog.get_track":
        return _get(str(params.get("provider_track_id") or params.get("track_id") or params.get("id") or ""))
    if method in {"playback.resolve", "playback.refresh"}:
        return _resolve(str(params.get("provider_track_id") or params.get("track_id") or params.get("id") or ""))
    raise RuntimeError(f"Unsupported method: {method}")


if __name__ == "__main__":
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
        print(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), flush=True)
