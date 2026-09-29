from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

EXTENSION_ID = "org.melodex.example.listenbrainz-community-pulse"
API = "https://api.listenbrainz.org"
USER_AGENT = os.getenv(
    "MELODEX_USER_AGENT",
    "Melodex-ListenBrainz-Community-Pulse/0.1.0 (https://github.com/Cliff-Lee/melodex)",
)


def _now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _fixture():
    return json.loads(
        (Path(__file__).parent / "fixtures" / "popularity.json").read_text(
            encoding="utf-8"
        )
    )


def _get_json(url):
    request = urllib.request.Request(
        url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"}
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        return json.load(response)


def _post_json(url, payload):
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        return json.load(response)


def _recording_popularity(recording_mbid):
    if os.getenv("MELODEX_EXAMPLE_FIXTURES") == "1":
        return _fixture()["recording"]
    return _post_json(
        API + "/1/popularity/recording",
        {"recording_mbids": [recording_mbid]},
    )


def _top_recordings(artist_mbid):
    if not artist_mbid:
        return []
    if os.getenv("MELODEX_EXAMPLE_FIXTURES") == "1":
        return _fixture()["top_recordings"]
    return _get_json(
        API
        + "/1/popularity/top-recordings-for-artist/"
        + urllib.parse.quote(artist_mbid)
    )


def _compact(value):
    try:
        number = int(value)
    except (TypeError, ValueError):
        return ""
    if number >= 1_000_000:
        return f"{number / 1_000_000:.1f}M"
    if number >= 1_000:
        return f"{number / 1_000:.1f}K"
    return str(number)


def _provenance(recording_mbid):
    return {
        "source_extension_id": EXTENSION_ID,
        "source_item_id": recording_mbid,
        "source_url": "https://listenbrainz.org/",
        "retrieved_at": _now(),
        "license": "Aggregate ListenBrainz/MetaBrainz service output; see source terms",
        "attribution": "ListenBrainz / MetaBrainz",
        "confidence": 0.9,
        "evidence": ["ListenBrainz aggregate popularity API"],
    }


def extension_health(params):
    if os.getenv("MELODEX_EXAMPLE_FIXTURES") == "1":
        return {
            "schema_version": "0.1",
            "status": "ready",
            "upstream_checked": True,
            "message": "ListenBrainz fixture service is available",
            "latency_ms": 0,
        }
    started = time.monotonic()
    request = urllib.request.Request(
        API + "/1/status/service-status",
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            payload = json.load(response)
        if not isinstance(payload, dict):
            raise ValueError("unexpected status response")
    except urllib.error.HTTPError as exc:
        return {
            "schema_version": "0.1",
            "status": "auth_required" if exc.code in {401, 403} else "unavailable",
            "upstream_checked": True,
            "message": f"ListenBrainz status endpoint returned HTTP {exc.code}",
            "latency_ms": int((time.monotonic() - started) * 1000),
        }
    except (urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError):
        return {
            "schema_version": "0.1",
            "status": "unavailable",
            "upstream_checked": True,
            "message": "ListenBrainz status endpoint is unavailable",
            "latency_ms": int((time.monotonic() - started) * 1000),
        }
    return {
        "schema_version": "0.1",
        "status": "ready",
        "upstream_checked": True,
        "message": "ListenBrainz status endpoint is reachable",
        "latency_ms": int((time.monotonic() - started) * 1000),
    }


def context_lookup(params):
    subject = params["subject"]
    canonical = subject.get("canonical_ids") or {}
    recording_mbid = str(canonical.get("musicbrainz_recording_id") or "").strip()
    artist_mbid = str(canonical.get("musicbrainz_artist_id") or "").strip()
    if not recording_mbid:
        return {
            "schema_version": "0.1",
            "capability": "context",
            "subject": subject,
            "cards": [],
            "cache": {"policy": "session", "ttl_seconds": None},
        }

    popularity = _recording_popularity(recording_mbid)
    row = popularity[0] if isinstance(popularity, list) and popularity else {}
    provenance = _provenance(recording_mbid)
    cards = []
    facts = []
    if isinstance(row, dict):
        if row.get("total_listen_count") is not None:
            facts.append({"label": "Listens", "value": int(row["total_listen_count"])})
        if row.get("total_user_count") is not None:
            facts.append({"label": "Listeners", "value": int(row["total_user_count"])})
    if facts:
        cards.append({
            "id": "community-pulse",
            "title": "Community Pulse",
            "kind": "facts",
            "priority": 70,
            "facts": facts,
            "provenance": provenance,
        })

    top = _top_recordings(artist_mbid)
    items = []
    for item in list(top or [])[:8]:
        if not isinstance(item, dict):
            continue
        title = str(item.get("recording_name") or "").strip()
        mbid = str(item.get("recording_mbid") or "").strip()
        if not title:
            continue
        listens = _compact(item.get("total_listen_count"))
        listeners = _compact(item.get("total_user_count"))
        subtitle_bits = []
        if listens:
            subtitle_bits.append(f"{listens} listens")
        if listeners:
            subtitle_bits.append(f"{listeners} listeners")
        rendered = {"title": title, "badge": "popular"}
        if subtitle_bits:
            rendered["subtitle"] = " · ".join(subtitle_bits)
        if mbid:
            rendered["url"] = f"https://musicbrainz.org/recording/{mbid}"
            rendered["canonical_ids"] = {"musicbrainz_recording_id": mbid}
        items.append(rendered)
    if items:
        cards.append({
            "id": "artist-popular-recordings",
            "title": "Popular With Listeners",
            "kind": "list",
            "priority": 45,
            "items": items,
            "provenance": provenance,
        })

    return {
        "schema_version": "0.1",
        "capability": "context",
        "subject": subject,
        "cards": cards,
        "cache": {"policy": "ttl", "ttl_seconds": 21600},
    }


def respond(request):
    method = request.get("method")
    params = request.get("params") or {}
    if method == "extension.health":
        return extension_health(params)
    if method == "context.lookup":
        return context_lookup(params)
    raise RuntimeError(f"Unsupported method: {method}")


def run_jsonrpc():
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


if __name__ == "__main__":
    run_jsonrpc()
