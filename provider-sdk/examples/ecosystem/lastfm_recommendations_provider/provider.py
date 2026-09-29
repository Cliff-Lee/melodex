from __future__ import annotations

import hashlib
import json
import os
import urllib.parse
import urllib.request
from pathlib import Path

PROVIDER_ID = "org.melodex.example.lastfm-recommendations"
API = "https://ws.audioscrobbler.com/2.0/"
USER_AGENT = os.getenv(
    "MELODEX_USER_AGENT",
    "Melodex-LastFM-Recommendations-Example/0.1 (https://github.com/Cliff-Lee/melodex)",
)


def _fixture():
    return json.loads(
        (Path(__file__).parent / "fixtures" / "similar.json").read_text(
            encoding="utf-8"
        )
    )


def _api_key(params):
    config = params.get("_melodex_config") or {}
    return str(config.get("api_key") or "").strip()


def _get_json(artist, title, limit, api_key):
    if os.getenv("MELODEX_EXAMPLE_FIXTURES") == "1":
        return _fixture()
    if not api_key:
        raise RuntimeError("Add your Last.fm API key in this plugin's settings")
    query = urllib.parse.urlencode(
        {
            "method": "track.getsimilar",
            "artist": artist,
            "track": title,
            "api_key": api_key,
            "format": "json",
            "autocorrect": "1",
            "limit": str(limit),
        }
    )
    req = urllib.request.Request(
        API + "?" + query,
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=20) as response:
        data = json.load(response)
    if isinstance(data, dict) and data.get("error"):
        raise RuntimeError(
            str(data.get("message") or f"Last.fm API error {data.get('error')}")
        )
    return data


def _image(row):
    images = [x for x in (row.get("image") or []) if isinstance(x, dict)]
    for preferred in ("extralarge", "large", "medium", "small"):
        value = next(
            (
                str(x.get("#text") or "")
                for x in images
                if x.get("size") == preferred and x.get("#text")
            ),
            "",
        )
        if value:
            return value
    return ""


def _safe_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _health(api_key):
    if os.getenv("MELODEX_EXAMPLE_FIXTURES") == "1":
        return {"status":"ready","message":"Last.fm fixture is available"}
    if not api_key:
        return {"status":"auth_required","message":"Configure a Last.fm API key"}
    query = urllib.parse.urlencode(
        {
            "method":"chart.gettoptracks",
            "api_key":api_key,
            "format":"json",
            "limit":"1",
        }
    )
    req = urllib.request.Request(
        API + "?" + query,
        headers={"User-Agent": USER_AGENT, "Accept":"application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=12) as response:
            data = json.load(response)
        if isinstance(data, dict) and data.get("error"):
            code = int(data.get("error") or 0)
            return {
                "status":"auth_required" if code in {4, 9, 10, 26} else "unavailable",
                "message":str(data.get("message") or f"Last.fm API error {code}"),
            }
        ready = isinstance(data, dict) and isinstance(data.get("tracks"), dict)
        return {
            "status":"ready" if ready else "degraded",
            "message":"Last.fm API is reachable" if ready else "Last.fm returned an unexpected response",
        }
    except Exception as exc:
        return {"status":"unavailable","message":f"Last.fm unavailable: {exc}"}


def _track(row):
    artist_obj = row.get("artist") if isinstance(row.get("artist"), dict) else {}
    artist = str(artist_obj.get("name") or row.get("artist") or "Unknown artist")
    title = str(row.get("name") or "Unknown track")
    lastfm_url = str(row.get("url") or "")
    raw_id = "|".join([artist.casefold(), title.casefold(), lastfm_url])
    track_id = hashlib.sha256(raw_id.encode("utf-8")).hexdigest()[:24]
    mbid = str(row.get("mbid") or "").strip() or None
    duration = row.get("duration")
    try:
        duration_ms = int(duration) if duration not in (None, "") else None
    except (TypeError, ValueError):
        duration_ms = None
    return {
        "type": "track",
        "provider_id": PROVIDER_ID,
        "provider_track_id": track_id,
        "title": title,
        "artist": artist,
        "album": "",
        "duration_ms": duration_ms,
        "artwork_url": _image(row) or None,
        "musicbrainz_recording_id": mbid,
        "metadata": {
            "recommendation_only": True,
            "playable": False,
            "match_score": _safe_float(row.get("match"), 0.0),
            "lastfm_url": lastfm_url,
            "lastfm_playcount": row.get("playcount"),
            "artist_mbid": artist_obj.get("mbid") or None,
            "artist_url": artist_obj.get("url") or None,
        },
    }


def recommendations_get(params):
    seed = params.get("seed") if isinstance(params.get("seed"), dict) else {}
    artist = str(seed.get("artist") or "").strip()
    title = str(seed.get("title") or "").strip()
    if not artist or not title:
        raise RuntimeError("recommendations.get requires seed.artist and seed.title")
    limit = max(1, min(int(params.get("limit") or 25), 100))
    data = _get_json(artist, title, limit, _api_key(params))
    block = data.get("similartracks") if isinstance(data, dict) else {}
    rows = block.get("track") if isinstance(block, dict) else []
    return {
        "items": [
            _track(row)
            for row in (rows or [])[:limit]
            if isinstance(row, dict)
        ],
        "next_cursor": None,
        "seed": {
            "artist": artist,
            "title": title,
            "album": str(seed.get("album") or ""),
        },
    }


def respond(request):
    method = request.get("method")
    params = request.get("params") or {}

    if method == "provider.info":
        return {
            "id": PROVIDER_ID,
            "name": "Last.fm Recommendations Example",
            "version": "0.1.0",
            "protocol_version": "1.0",
            "capabilities": ["recommendations"],
        }

    if method == "provider.health":
        return _health(_api_key(params))

    if method == "recommendations.get":
        return recommendations_get(params)

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
                "id": request.get("id") if isinstance(request, dict) else None,
                "error": {"code": -32000, "message": str(exc)},
            }
        print(json.dumps(payload, ensure_ascii=False), flush=True)
