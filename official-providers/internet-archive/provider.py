from __future__ import annotations

import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

PROVIDER_ID = "org.melodex.internetarchive"
PROVIDER_NAME = "Internet Archive"
VERSION = "0.1.0"
USER_AGENT = f"Melodex-InternetArchive-Provider/{VERSION} (https://github.com/Cliff-Lee/melodex)"

SEARCH_URL = "https://archive.org/advancedsearch.php"
METADATA_URL = "https://archive.org/metadata/{identifier}"
DETAIL_URL = "https://archive.org/details/{identifier}"
DOWNLOAD_URL = "https://archive.org/download/{identifier}/{filename}"
IMAGE_URL = "https://archive.org/services/img/{identifier}"

_AUDIO_EXTENSIONS = {
    ".mp3",
    ".m4a",
    ".aac",
    ".ogg",
    ".oga",
    ".opus",
    ".flac",
    ".wav",
}
_AUDIO_FORMAT_WORDS = (
    "mp3",
    "mpeg audio",
    "ogg",
    "vorbis",
    "opus",
    "flac",
    "wave",
    "wav",
    "aac",
    "m4a",
    "apple lossless",
)
_FORMAT_PRIORITY = {
    ".mp3": 0,
    ".m4a": 1,
    ".aac": 2,
    ".ogg": 3,
    ".oga": 3,
    ".opus": 4,
    ".flac": 5,
    ".wav": 6,
}

_CACHE: dict[str, tuple[float, Any]] = {}
_CACHE_TTL_SECONDS = 300.0
_LAST_REQUEST_AT = 0.0
_MIN_REQUEST_INTERVAL = 0.22


def _text(value: Any) -> str:
    if isinstance(value, list):
        return ", ".join(_text(x) for x in value if _text(x))
    return str(value or "").strip()


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return _text(value).casefold() in {"1", "true", "yes", "y", "restricted"}


def _request_json(url: str, *, ttl: float = _CACHE_TTL_SECONDS) -> Any:
    global _LAST_REQUEST_AT
    cached = _CACHE.get(url)
    now = time.monotonic()
    if cached and now - cached[0] < ttl:
        return cached[1]

    delay = _MIN_REQUEST_INTERVAL - (now - _LAST_REQUEST_AT)
    if delay > 0:
        time.sleep(delay)

    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
        },
    )
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=20) as response:
                payload = json.load(response)
            _LAST_REQUEST_AT = time.monotonic()
            _CACHE[url] = (_LAST_REQUEST_AT, payload)
            return payload
        except urllib.error.HTTPError as exc:
            last_error = exc
            if exc.code == 429 and attempt < 2:
                retry_after = exc.headers.get("Retry-After")
                try:
                    wait = max(1.0, min(10.0, float(retry_after or 1.0)))
                except Exception:
                    wait = 1.0
                time.sleep(wait)
                continue
            if 500 <= exc.code < 600 and attempt < 2:
                time.sleep(0.5 * (attempt + 1))
                continue
            raise
        except (urllib.error.URLError, TimeoutError) as exc:
            last_error = exc
            if attempt < 2:
                time.sleep(0.5 * (attempt + 1))
                continue
            raise
    raise RuntimeError(str(last_error or "Internet Archive request failed"))


def _request_text(url: str) -> str:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT},
    )
    with urllib.request.urlopen(req, timeout=10) as response:
        return response.read().decode("utf-8", errors="replace")


def _vbr_playlist_url(identifier: str) -> str:
    quoted = urllib.parse.quote(identifier, safe="")
    playlist = (
        f"https://archive.org/download/{quoted}/"
        f"{quoted}_vbr.m3u"
    )
    try:
        text = _request_text(playlist)
    except Exception:
        return ""

    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith(("http://", "https://")):
            return line

    return ""


def _escape_term(value: str) -> str:
    # Lucene special characters.
    return re.sub(r'([+\-!(){}\[\]^"~*?:\\/]|&&|\|\|)', r"\\\1", value)


def _search_query(query: str) -> str:
    tokens = [_escape_term(token) for token in query.split() if token.strip()]
    if not tokens:
        return "mediatype:audio"
    terms = " AND ".join(tokens)
    return (
        "mediatype:audio AND "
        f"(title:({terms}) OR creator:({terms}) OR subject:({terms}))"
    )


def _duration_seconds(value: Any) -> float:
    raw = _text(value)
    if not raw:
        return 0.0
    try:
        return max(0.0, float(raw))
    except ValueError:
        pass
    parts = raw.split(":")
    if len(parts) in {2, 3}:
        try:
            nums = [float(x) for x in parts]
        except ValueError:
            return 0.0
        if len(nums) == 2:
            return max(0.0, nums[0] * 60 + nums[1])
        return max(0.0, nums[0] * 3600 + nums[1] * 60 + nums[2])
    return 0.0


def _is_audio_file(file: dict[str, Any]) -> bool:
    name = _text(file.get("name"))
    suffix = Path(name).suffix.casefold()
    fmt = _text(file.get("format")).casefold()
    if suffix not in _AUDIO_EXTENSIONS and not any(word in fmt for word in _AUDIO_FORMAT_WORDS):
        return False
    if _truthy(file.get("private")) or _truthy(file.get("encrypted")):
        return False
    return bool(name)


def _file_group_key(file: dict[str, Any]) -> str:
    basis = _text(file.get("original")) or _text(file.get("name"))
    stem = Path(basis).stem.casefold()
    stem = re.sub(r"(?:_vbr|_64kb|_128kb|_256kb|\.vbr)$", "", stem)
    return stem


def _file_preference(file: dict[str, Any]) -> tuple[int, int, str]:
    name = _text(file.get("name"))
    suffix = Path(name).suffix.casefold()
    fmt = _text(file.get("format")).casefold()
    score = _FORMAT_PRIORITY.get(suffix, 99)
    if "vbr mp3" in fmt:
        score = -1
    try:
        size = -int(file.get("size") or 0)
    except Exception:
        size = 0
    return score, size, name.casefold()


def _preferred_audio_files(files: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for file in files:
        if not isinstance(file, dict) or not _is_audio_file(file):
            continue
        groups.setdefault(_file_group_key(file), []).append(file)

    chosen = [min(group, key=_file_preference) for group in groups.values()]
    chosen.sort(
        key=lambda f: (
            _track_number(f),
            _text(f.get("title")).casefold(),
            _text(f.get("name")).casefold(),
        )
    )
    return chosen


def _track_number(file: dict[str, Any]) -> int:
    raw = _text(file.get("track"))
    match = re.match(r"\s*(\d+)", raw)
    return int(match.group(1)) if match else 999999


def _metadata(identifier: str) -> dict[str, Any]:
    ident = urllib.parse.quote(identifier, safe="")
    data = _request_json(METADATA_URL.format(identifier=ident))
    if not isinstance(data, dict):
        raise RuntimeError(f"Internet Archive item not found: {identifier}")
    return data


def _track_id(identifier: str, filename: str) -> str:
    return f"{identifier}::{filename}"


def _split_track_id(track_id: str) -> tuple[str, str]:
    identifier, _, filename = track_id.partition("::")
    if not identifier:
        raise RuntimeError("Invalid Internet Archive track id")
    return identifier, filename

def _item_restricted(metadata: dict[str, Any]) -> bool:
    return _truthy(metadata.get("access-restricted-item")) or _truthy(metadata.get("restricted"))


def _track_from_file(
    identifier: str,
    item_metadata: dict[str, Any],
    file: dict[str, Any],
    *,
    multi_file: bool,
) -> dict[str, Any]:
    filename = _text(file.get("name"))
    item_title = _text(item_metadata.get("title")) or identifier
    file_title = _text(file.get("title"))
    if file_title:
        title = file_title
    elif multi_file:
        title = Path(filename).stem
    else:
        title = item_title

    artist = (
        _text(file.get("artist"))
        or _text(item_metadata.get("creator"))
        or "Internet Archive"
    )
    album = _text(file.get("album")) or (item_title if multi_file else "")
    year_match = re.search(r"\b(18|19|20)\d{2}\b", _text(item_metadata.get("date")))
    year = int(year_match.group(0)) if year_match else None
    license_url = _text(item_metadata.get("licenseurl") or item_metadata.get("license"))
    details = DETAIL_URL.format(identifier=urllib.parse.quote(identifier, safe=""))

    out = {
        "type": "track",
        "provider_id": PROVIDER_ID,
        "provider_track_id": _track_id(identifier, filename),
        "title": title,
        "artist": artist,
        "album": album,
        "duration": _duration_seconds(file.get("length") or file.get("duration")),
        "source_page": details,
        "attribution": f"{artist} — Internet Archive",
        "artwork": IMAGE_URL.format(identifier=urllib.parse.quote(identifier, safe="")),
    }
    if year is not None:
        out["year"] = year
    if license_url:
        out["license_url"] = license_url
    rights = _text(item_metadata.get("rights"))
    if rights:
        out["rights"] = rights
    return out


def _tracks_for_identifier(identifier: str, remaining: int) -> list[dict[str, Any]]:
    data = _metadata(identifier)
    item_metadata = data.get("metadata") or {}
    if not isinstance(item_metadata, dict) or _item_restricted(item_metadata):
        return []
    files = [f for f in data.get("files", []) if isinstance(f, dict)]
    audio_files = _preferred_audio_files(files)
    if not audio_files:
        return []
    multi = len(audio_files) > 1
    return [
        _track_from_file(identifier, item_metadata, file, multi_file=multi)
        for file in audio_files[:remaining]
    ]


def _search_track_from_doc(doc: dict[str, Any]) -> dict[str, Any] | None:
    identifier = _text(doc.get("identifier"))
    if not identifier:
        return None

    title = _text(doc.get("title")) or identifier
    artist = _text(doc.get("creator")) or "Internet Archive"
    date = _text(doc.get("date"))
    year_match = re.search(r"\b(18|19|20)\d{2}\b", date)

    out = {
        "type": "track",
        "provider_id": PROVIDER_ID,
        "provider_track_id": identifier,
        "title": title,
        "artist": artist,
        "album": "",
        "duration": 0.0,
        "source_page": DETAIL_URL.format(
            identifier=urllib.parse.quote(identifier, safe="")
        ),
        "attribution": f"{artist} — Internet Archive",
        "artwork": IMAGE_URL.format(
            identifier=urllib.parse.quote(identifier, safe="")
        ),
    }

    if year_match:
        out["year"] = int(year_match.group(0))

    return out


def search_catalog(query: str, limit: int) -> list[dict[str, Any]]:
    limit = max(1, min(int(limit or 25), 25))

    params = {
        "q": _search_query(query),
        "fl[]": ["identifier", "title", "creator", "date"],
        "rows": limit,
        "page": 1,
        "output": "json",
        "sort[]": "downloads desc",
    }

    url = SEARCH_URL + "?" + urllib.parse.urlencode(params, doseq=True)
    data = _request_json(url, ttl=120.0)
    docs = list(((data or {}).get("response") or {}).get("docs") or [])

    tracks = []
    for doc in docs:
        if not isinstance(doc, dict):
            continue
        track = _search_track_from_doc(doc)
        if track:
            tracks.append(track)

    return tracks[:limit]

def get_track(track_id: str) -> dict[str, Any]:
    identifier, filename = _split_track_id(track_id)

    data = _metadata(identifier)
    item_metadata = data.get("metadata") or {}

    if not isinstance(item_metadata, dict) or _item_restricted(item_metadata):
        raise RuntimeError("Internet Archive item is restricted or unavailable")

    files = [f for f in data.get("files", []) if isinstance(f, dict)]
    preferred = _preferred_audio_files(files)

    if filename:
        target = next(
            (f for f in files if _text(f.get("name")) == filename),
            None,
        )
    else:
        target = preferred[0] if preferred else None

    if target is None or not _is_audio_file(target):
        raise RuntimeError("Internet Archive item has no playable audio")

    return _track_from_file(
        identifier,
        item_metadata,
        target,
        multi_file=len(preferred) > 1,
    )

def resolve_playback(track_id: str) -> dict[str, Any]:
    identifier, filename = _split_track_id(track_id)

    if filename:
        url = DOWNLOAD_URL.format(
            identifier=urllib.parse.quote(identifier, safe=""),
            filename=urllib.parse.quote(filename, safe="/"),
        )
    else:
        url = _vbr_playlist_url(identifier)

        if url:
            filename = urllib.parse.unquote(
                urllib.parse.urlparse(url).path.rsplit("/", 1)[-1]
            )
        else:
            track = get_track(track_id)
            _, filename = _split_track_id(
                str(track.get("provider_track_id") or "")
            )

            if not filename:
                raise RuntimeError(
                    "Internet Archive item has no playable audio"
                )

            url = DOWNLOAD_URL.format(
                identifier=urllib.parse.quote(identifier, safe=""),
                filename=urllib.parse.quote(filename, safe="/"),
            )

    suffix = Path(filename).suffix.casefold()

    mime = {
        ".mp3": "audio/mpeg",
        ".m4a": "audio/mp4",
        ".aac": "audio/aac",
        ".ogg": "audio/ogg",
        ".oga": "audio/ogg",
        ".opus": "audio/ogg",
        ".flac": "audio/flac",
        ".wav": "audio/wav",
    }.get(suffix, "")

    return {
        "kind": "http",
        "url": url,
        "headers": {},
        "cookies": {},
        "gateway_required": True,
        "seekable": True,
        "mime_type": mime,
        "cache_policy": "session",
        "request_timeout_seconds": 30,
    }

def respond(request: dict[str, Any]) -> Any:
    method = _text(request.get("method"))
    params = request.get("params") or {}

    if method == "provider.info":
        return {
            "id": PROVIDER_ID,
            "name": PROVIDER_NAME,
            "version": VERSION,
        }
    if method == "provider.health":
        return {
            "status": "ready",
            "authentication": "none",
            "note": "Public Internet Archive metadata and download endpoints",
        }
    if method == "catalog.search":
        return {
            "items": search_catalog(_text(params.get("query")), int(params.get("limit") or 25)),
            "next_cursor": None,
        }
    if method == "catalog.get_track":
        track_id = _text(params.get("provider_track_id") or params.get("track_id") or params.get("id"))
        return get_track(track_id)
    if method in {"playback.resolve", "playback.refresh"}:
        track_id = _text(params.get("provider_track_id") or params.get("track_id"))
        return resolve_playback(track_id)

    raise RuntimeError(f"Unsupported method: {method}")


def main() -> int:
    for line in sys.stdin:
        try:
            request = json.loads(line)
            result = respond(request)
            payload = {
                "jsonrpc": "2.0",
                "id": request.get("id"),
                "result": result,
            }
        except Exception as exc:
            payload = {
                "jsonrpc": "2.0",
                "id": request.get("id") if "request" in locals() else None,
                "error": {"code": -32000, "message": str(exc)},
            }
        print(json.dumps(payload, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
