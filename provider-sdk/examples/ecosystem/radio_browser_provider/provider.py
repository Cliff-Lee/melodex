from __future__ import annotations

import json
import os
import random
import socket
import urllib.parse
import urllib.request
from pathlib import Path

PROVIDER_ID = "org.melodex.example.radio-browser"
USER_AGENT = os.getenv(
    "MELODEX_USER_AGENT",
    "Melodex-RadioBrowser-Example/0.1 (https://github.com/Cliff-Lee/melodex)",
)
CACHE = {}


def _fixture():
    return json.loads((Path(__file__).parent / "fixtures" / "stations.json").read_text(encoding="utf-8"))


def _server_candidates():
    env = os.getenv("RADIO_BROWSER_BASE")
    if env:
        return [env.rstrip("/")]
    hosts = []
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


def _get_json(path, params=None):
    if os.getenv("MELODEX_EXAMPLE_FIXTURES") == "1":
        return _fixture()
    errors = []
    for base in _server_candidates():
        try:
            url = base + path
            if params:
                url += "?" + urllib.parse.urlencode(params)
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=12) as response:
                return json.load(response)
        except Exception as exc:
            errors.append(f"{base}: {exc}")
    raise RuntimeError("Radio Browser mirrors unavailable: " + "; ".join(errors[-3:]))


def _station_to_track(station):
    station_id = str(station.get("stationuuid") or "").strip()
    if not station_id:
        return None
    CACHE[station_id] = station
    tags = [x.strip() for x in str(station.get("tags") or "").split(",") if x.strip()]
    return {
        "type":"track",
        "provider_id":PROVIDER_ID,
        "provider_track_id":station_id,
        "title":station.get("name") or "Unnamed station",
        "artist":station.get("countrycode") or "Internet Radio",
        "album":"Internet Radio",
        "duration_ms":None,
        "artwork_url":station.get("favicon") or None,
        "metadata":{
            "station":True,
            "homepage":station.get("homepage"),
            "tags":tags,
            "language":station.get("language"),
            "languagecodes":station.get("languagecodes"),
            "codec":station.get("codec"),
            "bitrate":station.get("bitrate"),
            "hls":bool(station.get("hls")),
            "votes":station.get("votes"),
        },
    }


def _station(station_id):
    if station_id in CACHE:
        return CACHE[station_id]
    if os.getenv("MELODEX_EXAMPLE_FIXTURES") == "1":
        rows = _fixture()
    else:
        rows = _get_json("/json/stations/byuuid", {"uuids":station_id})
    if not rows:
        raise RuntimeError("Station not found")
    CACHE[station_id] = rows[0]
    return rows[0]


def respond(request):
    method = request.get("method")
    params = request.get("params") or {}

    if method == "provider.info":
        return {"id":PROVIDER_ID,"name":"Radio Browser Example","version":"0.1.0",
                "protocol_version":"1.0","capabilities":["search","track","playback"]}

    if method == "provider.health":
        if os.getenv("MELODEX_EXAMPLE_FIXTURES") == "1":
            return {"status":"ready","message":"Radio Browser fixture is available"}
        try:
            stats = _get_json("/json/stats")
            ready = isinstance(stats, dict) and str(stats.get("status") or "").upper() == "OK"
            return {
                "status":"ready" if ready else "degraded",
                "message":"Radio Browser service is reachable" if ready else "Radio Browser returned unexpected stats",
            }
        except Exception as exc:
            return {"status":"unavailable","message":f"Radio Browser unavailable: {exc}"}

    if method == "catalog.search":
        query = str(params.get("query") or "").strip()
        limit = max(1, min(int(params.get("limit") or 25), 50))
        rows = _get_json("/json/stations/search", {
            "name":query,"limit":limit,"hidebroken":"true","order":"votes","reverse":"true"
        })
        items = []
        for row in rows[:limit]:
            if not isinstance(row, dict):
                continue
            track = _station_to_track(row)
            if track is not None:
                items.append(track)
        return {"items":items,"next_cursor":None}

    if method == "catalog.get_track":
        track_id = str(params.get("provider_track_id") or params.get("track_id") or "")
        return _station_to_track(_station(track_id))

    if method in {"playback.resolve","playback.refresh"}:
        track_id = str(params.get("provider_track_id") or params.get("track_id") or "")
        station = _station(track_id)
        if os.getenv("MELODEX_EXAMPLE_FIXTURES") != "1":
            try:
                _get_json("/json/url/" + urllib.parse.quote(track_id, safe=""))
            except Exception:
                pass
        url = station.get("url_resolved") or station.get("url")
        if not url:
            raise RuntimeError("Station has no stream URL")
        return {
            "kind":"hls" if station.get("hls") else "http",
            "url":url,"headers":{"User-Agent":USER_AGENT},"cookies":{},
            "mime_type":None,"expires_at":None,"seekable":False,
            "cache_policy":"none","refresh_token":track_id,"request_timeout_seconds":20,
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
            payload = {"jsonrpc":"2.0","id":request.get("id"),"result":respond(request)}
        except Exception as exc:
            payload = {"jsonrpc":"2.0","id":request.get("id") if isinstance(request,dict) else None,
                       "error":{"code":-32000,"message":str(exc)}}
        print(json.dumps(payload, ensure_ascii=False), flush=True)
