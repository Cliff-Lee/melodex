from __future__ import annotations

import json
import os
import time
import urllib.parse

import requests

PROVIDER_ID = "org.melodex.nichedb.radio"
API_BASE = os.getenv("NICHEDB_API_BASE", "https://nichedb.dev/api/v1").rstrip("/")
USER_AGENT = os.getenv(
    "MELODEX_USER_AGENT",
    "Melodex-NicheDB-Radio/0.1.2 (https://github.com/Cliff-Lee/melodex)",
)
CACHE_TTL_SECONDS = 300
_ITEM_CACHE: dict[str, dict] = {}
_SEARCH_CACHE: dict[str, tuple[float, dict]] = {}
_LAST_RATE_LIMIT_REMAINING: str | None = None
_API_KEY = ""
_SESSION = requests.Session()


def _headers() -> dict[str, str]:
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    if _API_KEY:
        headers["Authorization"] = f"Bearer {_API_KEY}"
    return headers


def _get_json(path: str, params: dict | None = None, *, use_cache: bool = False) -> dict:
    global _LAST_RATE_LIMIT_REMAINING
    url = API_BASE + path
    if params:
        url += "?" + urllib.parse.urlencode(params, doseq=True)
    cache_key = url
    now = time.monotonic()
    if use_cache:
        cached = _SEARCH_CACHE.get(cache_key)
        if cached and now - cached[0] < CACHE_TTL_SECONDS:
            return cached[1]

    try:
        response = _SESSION.get(url, headers=_headers(), timeout=15)
        _LAST_RATE_LIMIT_REMAINING = response.headers.get("x-ratelimit-remaining")
        if response.status_code == 429:
            retry = response.headers.get("retry-after") or "later"
            raise RuntimeError(f"NicheDB rate limit reached; retry {retry}")
        response.raise_for_status()
        payload = response.json()
    except requests.exceptions.SSLError as exc:
        raise RuntimeError(f"NicheDB TLS verification failed: {exc}") from exc
    except requests.exceptions.RequestException as exc:
        raise RuntimeError(f"NicheDB request failed: {exc}") from exc
    except ValueError as exc:
        raise RuntimeError("NicheDB returned invalid JSON") from exc

    if not isinstance(payload, dict):
        raise RuntimeError("NicheDB returned an invalid response")
    if use_cache:
        _SEARCH_CACHE[cache_key] = (now, payload)
    return payload


def _item_id(item: dict) -> str:
    return str(item.get("id") or "").strip()


def _data(item: dict) -> dict:
    value = item.get("data")
    return value if isinstance(value, dict) else {}


def _is_playable(item: dict) -> bool:
    data = _data(item)
    stream = str(data.get("stream") or data.get("streamUrl") or "").strip()
    return bool(stream) and data.get("online") is not False


def _item_to_track(item: dict):
    item_id = _item_id(item)
    if not item_id or str(item.get("kind") or "") != "station" or not _is_playable(item):
        return None

    data = _data(item)
    _ITEM_CACHE[item_id] = item
    genres = [str(x) for x in (data.get("genres") or []) if str(x).strip()]
    languages = [str(x) for x in (data.get("languages") or []) if str(x).strip()]
    country = str(data.get("country") or data.get("countryCode") or "").strip()
    metadata = {
        "station": True,
        "live": True,
        "source": "NicheDB",
        "external_id": item.get("external_id"),
        "homepage": data.get("homepage") or item.get("url"),
        "nichedb_page": item.get("page"),
        "radio_browser_page": data.get("page"),
        "country": data.get("country"),
        "country_code": data.get("countryCode"),
        "state": data.get("state"),
        "languages": languages,
        "language_codes": data.get("languageCodes") or [],
        "genres": genres,
        "codec": data.get("codec"),
        "bitrate": data.get("bitrate"),
        "hls": bool(data.get("hls")),
        "votes": data.get("votes"),
        "listens_24h": data.get("clicksLast24h"),
        "click_trend": data.get("clickTrend"),
        "online": data.get("online"),
        "tags": item.get("tags") or [],
    }
    if data.get("lat") is not None and data.get("long") is not None:
        metadata["latitude"] = data.get("lat")
        metadata["longitude"] = data.get("long")

    return {
        "type": "track",
        "provider_id": PROVIDER_ID,
        "provider_track_id": item_id,
        "title": item.get("title") or data.get("name") or "Internet radio station",
        "artist": country or "Internet Radio",
        "album": "NicheDB Radio",
        "duration_ms": None,
        "artwork_url": item.get("image_url") or None,
        "metadata": metadata,
    }


def _query_plan(query: str, limit: int) -> tuple[str, dict]:
    q = query.strip()
    requested = max(1, min(int(limit), 50))

    if not q:
        return "/items", {
            "collection": "radio",
            "kind": "station",
            "tags": "online,popular",
            "limit": requested,
        }

    lower = q.casefold()
    if lower == "popular":
        return "/items", {
            "collection": "radio",
            "kind": "station",
            "tags": "online,popular",
            "limit": requested,
        }

    prefixes = {
        "genre:": lambda value: value.casefold(),
        "country:": lambda value: f"country:{value.casefold()}",
        "lang:": lambda value: f"lang:{value.casefold()}",
        "codec:": lambda value: f"codec:{value.casefold()}",
    }
    for prefix, tagger in prefixes.items():
        if lower.startswith(prefix):
            value = q[len(prefix) :].strip()
            if value:
                return "/items", {
                    "collection": "radio",
                    "kind": "station",
                    "tags": f"online,{tagger(value)}",
                    "limit": requested,
                }

    # Search has no tag filter. Fetch extra candidates so filtering broken
    # streams does not leave an unnecessarily short Melodex result list.
    return "/search", {
        "q": q,
        "collection": "radio",
        "kind": "station",
        "limit": min(100, max(requested * 4, requested)),
    }


def _search(query: str, limit: int) -> list[dict]:
    path, params = _query_plan(query, limit)
    payload = _get_json(path, params, use_cache=True)
    rows = payload.get("items") or []
    if not isinstance(rows, list):
        return []
    result = []
    for item in rows:
        if not isinstance(item, dict):
            continue
        track = _item_to_track(item)
        if track is not None:
            result.append(track)
        if len(result) >= max(1, min(int(limit), 50)):
            break
    return result


def _item(track_id: str) -> dict:
    key = str(track_id or "").strip()
    if not key:
        raise RuntimeError("Missing NicheDB station id")
    cached = _ITEM_CACHE.get(key)
    if cached is not None:
        return cached
    payload = _get_json("/items/" + urllib.parse.quote(key, safe=""))
    item = payload.get("item")
    if not isinstance(item, dict):
        raise RuntimeError("NicheDB station not found")
    if str(item.get("kind") or "") != "station":
        raise RuntimeError("NicheDB item is not a radio station")
    _ITEM_CACHE[key] = item
    return item


def respond(request: dict):
    global _API_KEY
    method = request.get("method")
    params = request.get("params") or {}
    config = params.get("_melodex_config") or {}
    _API_KEY = str(config.get("api_key") or "").strip() if isinstance(config, dict) else ""

    if method == "provider.info":
        return {
            "id": PROVIDER_ID,
            "name": "NicheDB Radio",
            "version": "0.1.2",
            "protocol_version": "1.0",
            "capabilities": ["search", "track", "playback"],
        }

    if method == "provider.health":
        try:
            rows = _search("popular", 1)
            suffix = (
                f"; {_LAST_RATE_LIMIT_REMAINING} API requests remain this hour"
                if _LAST_RATE_LIMIT_REMAINING is not None
                else ""
            )
            return {
                "status": "ready" if rows else "degraded",
                "message": (
                    "NicheDB Radio is reachable" + suffix
                    if rows
                    else "NicheDB is reachable but returned no playable radio stations"
                ),
            }
        except Exception as exc:
            return {"status": "unavailable", "message": f"NicheDB Radio unavailable: {exc}"}

    if method == "catalog.search":
        raw_limit = params.get("limit")
        limit = 25 if raw_limit is None else max(1, min(int(raw_limit), 50))
        return {
            "items": _search(str(params.get("query") or ""), limit),
            "next_cursor": None,
        }

    if method == "catalog.get_track":
        track_id = str(params.get("provider_track_id") or params.get("track_id") or "")
        track = _item_to_track(_item(track_id))
        if track is None:
            raise RuntimeError("NicheDB station is not currently playable")
        return track

    if method in {"playback.resolve", "playback.refresh"}:
        track_id = str(params.get("provider_track_id") or params.get("track_id") or "")
        item = _item(track_id)
        data = _data(item)
        stream = str(data.get("stream") or data.get("streamUrl") or "").strip()
        if not stream:
            raise RuntimeError("NicheDB station has no stream URL")
        if data.get("online") is False:
            raise RuntimeError("NicheDB currently marks this station stream offline")
        return {
            "kind": "hls" if data.get("hls") else "http",
            "url": stream,
            "headers": {"User-Agent": USER_AGENT},
            "cookies": {},
            "mime_type": None,
            "expires_at": None,
            "seekable": False,
            "cache_policy": "none",
            "refresh_token": track_id,
            "request_timeout_seconds": 20,
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
