from __future__ import annotations

import json
import os
import random
import socket
import time
import urllib.parse
import urllib.request
from urllib.parse import urlparse

PROVIDER_ID = "org.melodex.nicheradio"
USER_AGENT = os.getenv(
    "MELODEX_USER_AGENT",
    "Melodex-NicheRadio/0.1 (https://github.com/Cliff-Lee/melodex)",
)
NETWORK_DOMAIN = "24-7nicheradio.com"
CACHE_TTL_SECONDS = 600
_STATION_CACHE: dict[str, dict] = {}
_NETWORK_CACHE: tuple[float, list[dict]] = (0.0, [])


def _server_candidates() -> list[str]:
    env = os.getenv("RADIO_BROWSER_BASE")
    if env:
        return [env.rstrip("/")]
    hosts: list[str] = []
    try:
        for row in socket.getaddrinfo("all.api.radio-browser.info", 443, type=socket.SOCK_STREAM):
            ip = row[4][0]
            try:
                host = socket.gethostbyaddr(ip)[0]
            except OSError:
                continue
            if host.endswith(".api.radio-browser.info") and host not in hosts:
                hosts.append(host)
    except OSError:
        pass
    random.shuffle(hosts)
    urls = [f"https://{host}" for host in hosts]
    if "https://de1.api.radio-browser.info" not in urls:
        urls.append("https://de1.api.radio-browser.info")
    return urls


def _get_json(path: str, params: dict | None = None):
    errors: list[str] = []
    for base in _server_candidates():
        try:
            url = base + path
            if params:
                url += "?" + urllib.parse.urlencode(params)
            request = urllib.request.Request(
                url,
                headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
            )
            with urllib.request.urlopen(request, timeout=12) as response:
                return json.load(response)
        except Exception as exc:
            errors.append(f"{base}: {exc}")
    raise RuntimeError("Radio Browser mirrors unavailable: " + "; ".join(errors[-3:]))


def _normalise_host(value: str | None) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if "://" not in text:
        text = "https://" + text
    return (urlparse(text).hostname or "").casefold().removeprefix("www.")


def _is_nicheradio(station: dict) -> bool:
    homepage_host = _normalise_host(station.get("homepage"))
    if homepage_host == NETWORK_DOMAIN or homepage_host.endswith("." + NETWORK_DOMAIN):
        return True

    # Some directory rows have incomplete homepage data. Keep the fallback
    # deliberately narrow so unrelated stations called "24-7" are excluded.
    name = str(station.get("name") or "").casefold()
    homepage = str(station.get("homepage") or "").casefold()
    return (
        "niche radio" in name
        and ("24-7" in name or "24/7" in name)
        and NETWORK_DOMAIN in homepage
    )


def _network_stations(force: bool = False) -> list[dict]:
    global _NETWORK_CACHE
    now = time.monotonic()
    cached_at, cached_rows = _NETWORK_CACHE
    if not force and cached_rows and now - cached_at < CACHE_TTL_SECONDS:
        return list(cached_rows)

    rows_by_id: dict[str, dict] = {}
    # Radio Browser does not expose a homepage-domain query. These brand/name
    # searches produce a small candidate set which is then strictly filtered
    # to the official Niche Radio domain.
    for candidate in ("24-7", "Niche Radio"):
        rows = _get_json(
            "/json/stations/search",
            {
                "name": candidate,
                "limit": 500,
                "hidebroken": "true",
                "order": "name",
            },
        )
        for row in rows if isinstance(rows, list) else []:
            if not isinstance(row, dict) or not _is_nicheradio(row):
                continue
            station_id = str(row.get("stationuuid") or "").strip()
            if station_id:
                rows_by_id[station_id] = row
                _STATION_CACHE[station_id] = row

    result = sorted(
        rows_by_id.values(),
        key=lambda row: str(row.get("name") or "").casefold(),
    )
    _NETWORK_CACHE = (now, result)
    return list(result)


def _station_to_track(station: dict):
    station_id = str(station.get("stationuuid") or "").strip()
    if not station_id or not _is_nicheradio(station):
        return None
    _STATION_CACHE[station_id] = station
    tags = [x.strip() for x in str(station.get("tags") or "").split(",") if x.strip()]
    country = str(station.get("country") or station.get("countrycode") or "").strip()
    return {
        "type": "track",
        "provider_id": PROVIDER_ID,
        "provider_track_id": station_id,
        "title": station.get("name") or "24-7 Niche Radio",
        "artist": "24-7 Niche Radio",
        "album": "Live Radio",
        "duration_ms": None,
        "artwork_url": station.get("favicon") or None,
        "metadata": {
            "station": True,
            "live": True,
            "network": "24-7 Niche Radio",
            "homepage": station.get("homepage") or f"https://{NETWORK_DOMAIN}/",
            "country": country or None,
            "tags": tags,
            "language": station.get("language"),
            "languagecodes": station.get("languagecodes"),
            "codec": station.get("codec"),
            "bitrate": station.get("bitrate"),
            "hls": bool(station.get("hls")),
            "votes": station.get("votes"),
        },
    }


def _station(station_id: str) -> dict:
    if station_id in _STATION_CACHE:
        return _STATION_CACHE[station_id]
    rows = _get_json("/json/stations/byuuid", {"uuids": station_id})
    if not rows or not isinstance(rows, list) or not isinstance(rows[0], dict):
        raise RuntimeError("Station not found")
    station = rows[0]
    if not _is_nicheradio(station):
        raise RuntimeError("Station is not part of 24-7 Niche Radio")
    _STATION_CACHE[station_id] = station
    return station


def _matches_query(station: dict, query: str) -> bool:
    needle = query.casefold().strip()
    if not needle:
        return True
    fields = [
        station.get("name"),
        station.get("tags"),
        station.get("country"),
        station.get("language"),
    ]
    haystack = " ".join(str(value or "") for value in fields).casefold()
    return needle in haystack


def respond(request: dict):
    method = request.get("method")
    params = request.get("params") or {}

    if method == "provider.info":
        return {
            "id": PROVIDER_ID,
            "name": "24-7 Niche Radio",
            "version": "0.1.0",
            "protocol_version": "1.0",
            "capabilities": ["search", "track", "playback"],
        }

    if method == "provider.health":
        try:
            rows = _network_stations(force=True)
            return {
                "status": "ready" if rows else "degraded",
                "message": (
                    f"24-7 Niche Radio discovery is available ({len(rows)} stations found)"
                    if rows
                    else "Radio Browser is reachable but no current 24-7 Niche Radio stations were found"
                ),
            }
        except Exception as exc:
            return {"status": "unavailable", "message": f"NicheRadio unavailable: {exc}"}

    if method == "catalog.search":
        query = str(params.get("query") or "").strip()
        raw_limit = params.get("limit")
        limit = 25 if raw_limit is None else max(1, min(int(raw_limit), 100))
        items = []
        for station in _network_stations():
            if not _matches_query(station, query):
                continue
            track = _station_to_track(station)
            if track is not None:
                items.append(track)
            if len(items) >= limit:
                break
        return {"items": items, "next_cursor": None}

    if method == "catalog.get_track":
        track_id = str(params.get("provider_track_id") or params.get("track_id") or "")
        return _station_to_track(_station(track_id))

    if method in {"playback.resolve", "playback.refresh"}:
        track_id = str(params.get("provider_track_id") or params.get("track_id") or "")
        station = _station(track_id)
        try:
            _get_json("/json/url/" + urllib.parse.quote(track_id, safe=""))
        except Exception:
            pass
        url = station.get("url_resolved") or station.get("url")
        if not url:
            raise RuntimeError("Station has no stream URL")
        return {
            "kind": "hls" if station.get("hls") else "http",
            "url": url,
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
