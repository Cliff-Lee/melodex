from __future__ import annotations

import json
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

UA = "Melodex/0.7 (+https://github.com/Cliff-Lee/melodex)"
PROVIDER_ID = "org.melodex.librivox"
NAME = "LibriVox"
VERSION = "0.1.5"

SEARCH_API = "https://archive.org/advancedsearch.php"
METADATA_API = "https://archive.org/metadata/"
COLLECTION = "librivoxaudio"

_cache: dict[str, dict] = {}


def _bytes(url: str, headers=None, timeout: float = 18.0, attempts: int = 2) -> bytes:
    merged = {
        "User-Agent": UA,
        "Accept-Encoding": "identity",
        "Connection": "close",
    }
    if headers:
        merged.update(headers)
    last = None
    for attempt in range(max(1, attempts)):
        try:
            req = Request(url, headers=merged, method="GET")
            with urlopen(req, timeout=timeout) as response:
                return response.read()
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            last = exc
            if attempt + 1 < attempts:
                time.sleep(0.8 * (attempt + 1))
    raise RuntimeError(f"Request failed: {last}")


def _json(url: str, headers=None):
    return json.loads(_bytes(url, headers=headers).decode("utf-8", "replace"))


def _rpc_loop(handle):
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        rid = None
        try:
            request = json.loads(line)
            rid = request.get("id")
            result = handle(
                str(request.get("method") or ""),
                dict(request.get("params") or {}),
            )
            out = {"jsonrpc": "2.0", "id": rid, "result": result}
        except Exception as exc:
            out = {
                "jsonrpc": "2.0",
                "id": rid,
                "error": {
                    "code": -32000,
                    "message": str(exc),
                    "data": {
                        "mpp_code": "PROVIDER_ERROR",
                        "retryable": True,
                    },
                },
            }
        print(
            json.dumps(out, ensure_ascii=False, separators=(",", ":")),
            flush=True,
        )


def _text(value) -> str:
    if isinstance(value, list):
        return ", ".join(str(item).strip() for item in value if str(item).strip())
    return str(value or "").strip()


def _lucene_phrase(value: str) -> str:
    cleaned = " ".join(str(value or "").split()).replace("\\", "\\\\").replace('"', '\\"')
    return cleaned[:180]


def _search_docs(query: str, limit: int) -> list[dict]:
    phrase = _lucene_phrase(query)
    if not phrase:
        return []
    expression = (
        f'collection:{COLLECTION} AND mediatype:audio AND '
        f'(title:"{phrase}" OR creator:"{phrase}" OR subject:"{phrase}")'
    )
    params = [
        ("q", expression),
        ("fl[]", "identifier"),
        ("fl[]", "title"),
        ("fl[]", "creator"),
        ("fl[]", "description"),
        ("fl[]", "language"),
        ("fl[]", "downloads"),
        ("sort[]", "downloads desc"),
        ("rows", str(max(1, min(int(limit), 25)))),
        ("page", "1"),
        ("output", "json"),
    ]
    payload = _json(
        SEARCH_API + "?" + urlencode(params),
        {"Accept": "application/json"},
    )
    response = payload.get("response") if isinstance(payload, dict) else None
    docs = response.get("docs") if isinstance(response, dict) else None
    return [row for row in (docs or []) if isinstance(row, dict)]


def _book_item(doc: dict) -> dict:
    identifier = _text(doc.get("identifier"))
    title = _text(doc.get("title")) or identifier or "LibriVox audiobook"
    creator = _text(doc.get("creator")) or "LibriVox"
    item = {
        "type": "track",
        "provider_id": PROVIDER_ID,
        "track_id": identifier,
        "provider_track_id": identifier,
        "title": title,
        "artist": creator,
        "album": "LibriVox audiobook",
        "artwork_url": (
            f"https://archive.org/services/img/{quote(identifier, safe='')}"
            if identifier
            else None
        ),
        "source_page": (
            f"https://archive.org/details/{quote(identifier, safe='')}"
            if identifier
            else "https://archive.org/details/librivoxaudio"
        ),
        "attribution": "Public-domain recording from LibriVox, hosted by Internet Archive",
        "metadata": {
            "archive_identifier": identifier,
            "language": _text(doc.get("language")),
            "description": _text(doc.get("description")),
            "librivox_collection": True,
        },
    }
    if identifier:
        _cache[identifier] = item
    return item


def _search(query: str, limit: int) -> list[dict]:
    return [
        _book_item(doc)
        for doc in _search_docs(query, max(1, min(int(limit), 25)))
        if _text(doc.get("identifier"))
    ]


def _metadata(identifier: str) -> dict:
    identifier = str(identifier or "").strip()
    if not identifier:
        raise RuntimeError("Missing LibriVox archive identifier")
    payload = _json(
        METADATA_API + quote(identifier, safe=""),
        {"Accept": "application/json"},
    )
    if not isinstance(payload, dict):
        raise RuntimeError("Internet Archive returned invalid metadata")
    return payload


def _get(identifier: str) -> dict:
    identifier = str(identifier or "").strip()
    if identifier in _cache:
        return _cache[identifier]
    payload = _metadata(identifier)
    meta = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
    doc = {
        "identifier": identifier,
        "title": meta.get("title"),
        "creator": meta.get("creator"),
        "description": meta.get("description"),
        "language": meta.get("language"),
    }
    return _book_item(doc)


def _track_order(row: dict) -> tuple:
    track = _text(row.get("track"))
    digits = "".join(ch for ch in track if ch.isdigit())
    track_number = int(digits) if digits else 999999
    return track_number, _text(row.get("name")).casefold()


def _mp3_rank(row: dict) -> tuple:
    fmt = _text(row.get("format")).casefold()
    source = _text(row.get("source")).casefold()
    if source == "original" and "mp3" in fmt:
        quality = 0
    elif "vbr mp3" in fmt or "128" in fmt:
        quality = 1
    elif "64" in fmt and "mp3" in fmt:
        quality = 3
    else:
        quality = 2
    return quality, *_track_order(row)


def _select_audio_file(payload: dict) -> dict:
    files = payload.get("files") if isinstance(payload, dict) else None
    candidates = []
    for row in files or []:
        if not isinstance(row, dict):
            continue
        name = _text(row.get("name"))
        if not name.casefold().endswith(".mp3"):
            continue
        if not name:
            continue
        candidates.append(row)
    if not candidates:
        raise RuntimeError("No playable MP3 files were found for this LibriVox audiobook")
    candidates.sort(key=_mp3_rank)
    return candidates[0]


def _resolve(identifier: str) -> dict:
    identifier = str(identifier or "").strip()
    payload = _metadata(identifier)
    selected = _select_audio_file(payload)
    name = _text(selected.get("name"))
    url = (
        "https://archive.org/download/"
        + quote(identifier, safe="")
        + "/"
        + quote(name, safe="/")
    )
    return {
        "kind": "http",
        "url": url,
        "stream_url": url,
        "mime_type": "audio/mpeg",
        "expires_at": None,
        "seekable": True,
        "cache_policy": "session",
        "headers": {"User-Agent": UA},
    }


def _track_id(params: dict) -> str:
    return str(
        params.get("provider_track_id")
        or params.get("track_id")
        or params.get("id")
        or ""
    )


def _handle(method: str, params: dict):
    if method == "provider.info":
        return {
            "id": PROVIDER_ID,
            "name": NAME,
            "version": VERSION,
            "protocol_version": "1.0",
            "description": (
                "Public-domain LibriVox audiobooks indexed through the "
                "Internet Archive LibriVox collection."
            ),
            "capabilities": ["search", "track", "playback"],
        }
    if method == "provider.health":
        return {
            "status": "ready",
            "message": "LibriVox catalogue path is configured",
            "check_scope": "provider",
        }
    if method == "catalog.search":
        return {
            "items": _search(
                str(params.get("query") or ""),
                int(params.get("limit") or 50),
            ),
            "next_cursor": None,
        }
    if method == "catalog.get_track":
        return _get(_track_id(params))
    if method in {"playback.resolve", "playback.refresh"}:
        return _resolve(_track_id(params))
    raise RuntimeError(f"Unsupported method: {method}")


if __name__ == "__main__":
    _rpc_loop(_handle)
