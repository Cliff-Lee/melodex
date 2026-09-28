from __future__ import annotations

import json
import os
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

EXTENSION_ID = "org.melodex.example.musicbrainz"
BASE = "https://musicbrainz.org/ws/2"
USER_AGENT = os.getenv(
    "MELODEX_USER_AGENT",
    "Melodex-MusicBrainz-Example/0.1 (https://github.com/Cliff-Lee/melodex)",
)
_LAST_REQUEST = 0.0


def _now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _fixture(name):
    return json.loads((Path(__file__).parent / "fixtures" / name).read_text(encoding="utf-8"))


def _rate_limit():
    global _LAST_REQUEST
    delay = 1.05 - (time.monotonic() - _LAST_REQUEST)
    if delay > 0:
        time.sleep(delay)
    _LAST_REQUEST = time.monotonic()


def _get_json(path, params=None):
    if os.getenv("MELODEX_EXAMPLE_FIXTURES") == "1":
        return _fixture("search.json" if path == "/recording/" else "lookup.json")
    _rate_limit()
    url = BASE + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as response:
        return json.load(response)


def _artist_credit(row):
    parts = []
    for credit in row.get("artist-credit") or []:
        name = credit.get("name") or (credit.get("artist") or {}).get("name") or ""
        if name:
            parts.append(name + str(credit.get("joinphrase") or ""))
    return "".join(parts).strip()


def _provenance(item_id, score=None, evidence=None):
    return {
        "source_extension_id": EXTENSION_ID,
        "source_item_id": item_id,
        "source_url": f"https://musicbrainz.org/recording/{item_id}",
        "retrieved_at": _now(),
        "license": "See MusicBrainz data license (core data CC0; supplementary data differs)",
        "attribution": "MusicBrainz",
        "confidence": score,
        "evidence": evidence or [],
    }


def _candidate(recording):
    ids = {"musicbrainz_recording_id": recording["id"]}
    credits = recording.get("artist-credit") or []
    if credits and (credits[0].get("artist") or {}).get("id"):
        ids["musicbrainz_artist_id"] = credits[0]["artist"]["id"]
    isrcs = recording.get("isrcs") or []
    if isrcs:
        ids["isrc"] = isrcs[0]
    releases = recording.get("releases") or []
    if releases:
        ids["musicbrainz_release_id"] = releases[0].get("id")
        group = releases[0].get("release-group") or {}
        if group.get("id"):
            ids["musicbrainz_release_group_id"] = group["id"]
    ids = {k: v for k, v in ids.items() if v}
    score = max(0.0, min(1.0, float(recording.get("score") or 0) / 100.0))
    return {
        "canonical_ids": ids,
        "display": {
            "title": recording.get("title"),
            "artist": _artist_credit(recording),
            "duration_ms": recording.get("length"),
        },
        "score": score,
        "provenance": _provenance(
            recording["id"], score, ["MusicBrainz recording search score"]
        ),
    }


def identity_resolve(params):
    subject = params["subject"]
    canonical = subject.get("canonical_ids") or {}
    existing = canonical.get("musicbrainz_recording_id")
    if existing:
        return {
            "schema_version": "0.1",
            "capability": "identity",
            "status": "matched",
            "subject": subject,
            "candidates": [{
                "canonical_ids": {"musicbrainz_recording_id": existing},
                "display": subject.get("hints") or {},
                "score": 1.0,
                "provenance": _provenance(existing, 1.0, ["MBID supplied by caller"]),
            }],
            "cache": {"policy": "persistent", "ttl_seconds": None},
        }

    hints = subject.get("hints") or {}
    title = str(hints.get("title") or "").strip()
    artist = str(hints.get("artist") or "").strip()
    isrc = canonical.get("isrc")

    if isrc:
        query = f"isrc:{isrc}"
    elif title and artist:
        query = f'recording:"{title.replace(chr(34), "")}" AND artist:"{artist.replace(chr(34), "")}"'
    elif title:
        query = f'recording:"{title.replace(chr(34), "")}"'
    else:
        return {
            "schema_version": "0.1", "capability": "identity", "status": "not_found",
            "subject": subject, "candidates": [], "cache": {"policy": "session", "ttl_seconds": None},
        }

    data = _get_json("/recording/", {
        "query": query, "fmt": "json", "limit": min(int(params.get("max_candidates") or 5), 20)
    })
    candidates = [_candidate(row) for row in data.get("recordings") or []]
    if not candidates:
        status = "not_found"
    elif len(candidates) == 1 or (candidates[0]["score"] - candidates[1]["score"] >= 0.08):
        status = "matched"
    else:
        status = "ambiguous"
    return {
        "schema_version": "0.1", "capability": "identity", "status": status,
        "subject": subject, "candidates": candidates,
        "cache": {"policy": "ttl", "ttl_seconds": 604800},
    }


def _sourced(value, recording_id, confidence=1.0):
    return {"value": value, "provenance": _provenance(recording_id, confidence)}


def metadata_enrich(params):
    subject = params["subject"]
    canonical = subject.get("canonical_ids") or {}
    recording_id = canonical.get("musicbrainz_recording_id")
    if not recording_id:
        raise RuntimeError("metadata.enrich requires musicbrainz_recording_id in v0.1 example")

    row = _get_json(
        f"/recording/{recording_id}",
        {"fmt": "json", "inc": "artist-credits+isrcs+releases+release-groups+genres"},
    )
    requested = set(params.get("requested_fields") or [])
    all_fields = not requested
    fields = {}

    def add(name, value, confidence=1.0):
        if value not in (None, "", []) and (all_fields or name in requested):
            fields[name] = _sourced(value, recording_id, confidence)

    add("title", row.get("title"))
    add("artist", _artist_credit(row))
    add("duration_ms", row.get("length"))

    isrcs = row.get("isrcs") or []
    add("isrc", isrcs[0] if isrcs else None)

    releases = row.get("releases") or []
    if releases:
        add("album", releases[0].get("title"), 0.95)
        date = releases[0].get("date") or row.get("first-release-date")
        if date:
            add("year", int(str(date)[:4]), 0.95)

    genres = [g.get("name") for g in (row.get("genres") or []) if g.get("name")]
    add("genres", genres, 0.8)

    return {
        "schema_version": "0.1", "capability": "metadata", "subject": subject,
        "fields": fields, "cache": {"policy": "ttl", "ttl_seconds": 86400},
    }


def respond(request):
    method = request.get("method")
    params = request.get("params") or {}
    if method == "identity.resolve":
        return identity_resolve(params)
    if method == "metadata.enrich":
        return metadata_enrich(params)
    raise RuntimeError(f"Unsupported method: {method}")


def run_jsonrpc(respond):
    import sys
    for line in sys.stdin:
        if not line.strip():
            continue
        request = None
        try:
            request = json.loads(line)
            result = respond(request)
            payload = {"jsonrpc": "2.0", "id": request.get("id"), "result": result}
        except Exception as exc:
            payload = {"jsonrpc": "2.0", "id": request.get("id") if isinstance(request, dict) else None,
                       "error": {"code": -32000, "message": str(exc)}}
        print(json.dumps(payload, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    run_jsonrpc(respond)
