from __future__ import annotations

import html
import json
import re
import sys
import time
from pathlib import PurePosixPath
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

PROVIDER_ID = "org.melodex.wikimedia.commons.audio"
NAME = "Wikimedia Commons Audio"
VERSION = "0.1.2"
API = "https://commons.wikimedia.org/w/api.php"
UA = "Melodex-Wikimedia-Commons-Audio/0.1.2 (+https://github.com/Cliff-Lee/melodex)"
AUDIO_EXT = {
    ".ogg",
    ".oga",
    ".opus",
    ".mp3",
    ".flac",
    ".wav",
    ".wave",
    ".mid",
    ".midi",
    ".webm",
}
_cache: dict[str, dict] = {}


def _bytes(url, headers=None, timeout=22, attempts=3):
    merged = {
        "User-Agent": UA,
        "Accept-Encoding": "identity",
        "Connection": "close",
    }
    if headers:
        merged.update(headers)
    last = None
    for attempt in range(attempts):
        try:
            request = Request(url, headers=merged, method="GET")
            with urlopen(request, timeout=timeout) as response:
                return response.read()
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            last = exc
            if attempt + 1 < attempts:
                time.sleep(0.45 * (2**attempt))
    raise RuntimeError(f"Request failed: {last}")


def _json(url, headers=None):
    return json.loads(_bytes(url, headers=headers).decode("utf-8", "replace"))


def _clean(value):
    if isinstance(value, dict):
        value = value.get("value", "")
    text = html.unescape(str(value or ""))
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _is_audio(info):
    mime = str(info.get("mime") or "").lower()
    media = str(info.get("mediatype") or "").upper()
    ext = PurePosixPath(
        urlsplit(str(info.get("url") or "")).path
    ).suffix.lower()
    return (
        mime.startswith("audio/")
        or media == "AUDIO"
        or ext in AUDIO_EXT
    )


def _query(params):
    params = {"format": "json", "formatversion": "2", **params}
    return _json(
        API + "?" + urlencode(params),
        {"Accept": "application/json"},
    )


def _track(page):
    info = (page.get("imageinfo") or [{}])[0]
    if not _is_audio(info):
        return None
    extmetadata = info.get("extmetadata") or {}
    page_id = str(page.get("pageid") or "")
    title = str(page.get("title") or "").removeprefix("File:")
    artist = (
        _clean(extmetadata.get("Artist"))
        or _clean(extmetadata.get("Credit"))
        or "Wikimedia Commons contributor"
    )
    license_name = (
        _clean(extmetadata.get("LicenseShortName"))
        or _clean(extmetadata.get("UsageTerms"))
    )
    license_url = _clean(extmetadata.get("LicenseUrl"))
    description = _clean(extmetadata.get("ImageDescription"))
    item = {
        "type": "track",
        "provider_id": PROVIDER_ID,
        "track_id": page_id,
        "provider_track_id": page_id,
        "title": title,
        "artist": artist,
        "album": "Wikimedia Commons",
        "source_page": str(
            info.get("descriptionurl")
            or (
                "https://commons.wikimedia.org/wiki/"
                + str(page.get("title") or "").replace(" ", "_")
            )
        ),
        "artwork_url": None,
        "attribution": " / ".join(
            value
            for value in (artist, "Wikimedia Commons", license_name)
            if value
        ),
        "license": license_name or None,
        "license_url": license_url or None,
        "metadata": {
            "description": description,
            "mime": str(info.get("mime") or ""),
            "media_url": str(info.get("url") or ""),
        },
    }
    _cache[page_id] = item
    return item


def _search(query, limit):
    data = _query(
        {
            "action": "query",
            "generator": "search",
            "gsrsearch": query,
            "gsrnamespace": "6",
            "gsrlimit": str(max(10, min(50, limit * 3))),
            "prop": "imageinfo",
            "iiprop": "url|mime|mediatype|extmetadata",
            "iiextmetadatalanguage": "en",
        }
    )
    out = []
    for page in (data.get("query") or {}).get("pages", []) or []:
        track = _track(page)
        if track:
            out.append(track)
        if len(out) >= limit:
            break
    return out


def _get(page_id):
    if page_id in _cache:
        return _cache[page_id]
    data = _query(
        {
            "action": "query",
            "pageids": page_id,
            "prop": "imageinfo",
            "iiprop": "url|mime|mediatype|extmetadata",
            "iiextmetadatalanguage": "en",
        }
    )
    pages = (data.get("query") or {}).get("pages", []) or []
    track = _track(pages[0]) if pages else None
    if not track:
        raise RuntimeError("Commons audio file not found")
    return track


def _resolve(page_id):
    track = _get(page_id)
    url = str((track.get("metadata") or {}).get("media_url") or "")
    if not url:
        raise RuntimeError("Commons file has no playable media URL")
    mime = str((track.get("metadata") or {}).get("mime") or "audio/ogg")
    return {
        "kind": "http",
        "url": url,
        "stream_url": url,
        "headers": {
            "User-Agent": UA,
            "Accept-Encoding": "identity",
            "Connection": "close",
        },
        "mime_type": mime,
        "expires_at": None,
        "seekable": True,
        "cache_policy": "session",
        "request_timeout_seconds": 30,
    }


def _track_id(params):
    return str(
        params.get("provider_track_id")
        or params.get("track_id")
        or params.get("id")
        or ""
    )


def _handle(method, params):
    if method == "provider.info":
        return {
            "id": PROVIDER_ID,
            "name": NAME,
            "version": VERSION,
            "protocol_version": "1.0",
            "description": (
                "Openly licensed and public-domain audio from Wikimedia Commons. "
                "Search subjects, people, music, speeches and sounds."
            ),
            "capabilities": ["search", "track", "playback"],
        }
    if method == "provider.health":
        return {"status": "ready"}
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


def _rpc_loop(handle):
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        request_id = None
        try:
            request = json.loads(line)
            request_id = request.get("id")
            result = handle(
                str(request.get("method") or ""),
                dict(request.get("params") or {}),
            )
            response = {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": result,
            }
        except Exception as exc:
            response = {
                "jsonrpc": "2.0",
                "id": request_id,
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
            json.dumps(
                response,
                ensure_ascii=False,
                separators=(",", ":"),
            ),
            flush=True,
        )


if __name__ == "__main__":
    _rpc_loop(_handle)
