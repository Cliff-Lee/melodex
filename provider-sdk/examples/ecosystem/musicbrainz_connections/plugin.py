from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

EXTENSION_ID = "org.melodex.example.musicbrainz-connections"
API = "https://musicbrainz.org/ws/2/recording/"
USER_AGENT = os.getenv(
    "MELODEX_USER_AGENT",
    "Melodex-MusicBrainz-Connections/0.1.0 (https://github.com/Cliff-Lee/melodex)",
)


def _now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _fixture():
    return json.loads(
        (Path(__file__).parent / "fixtures" / "recording.json").read_text(
            encoding="utf-8"
        )
    )


def _get_json(recording_mbid):
    if os.getenv("MELODEX_EXAMPLE_FIXTURES") == "1":
        return _fixture()
    inc = "recording-rels+release-rels+artist-rels+work-rels+place-rels"
    url = API + urllib.parse.quote(recording_mbid, safe="") + "?" + urllib.parse.urlencode(
        {"fmt": "json", "inc": inc}
    )
    request = urllib.request.Request(
        url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"}
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        return json.load(response)


def _artist_credit(entity):
    rows = entity.get("artist-credit") if isinstance(entity, dict) else None
    if not isinstance(rows, list):
        return ""
    names = []
    for row in rows:
        if isinstance(row, dict):
            name = str(row.get("name") or ((row.get("artist") or {}).get("name") if isinstance(row.get("artist"), dict) else "") or "").strip()
            if name:
                names.append(name)
    return ", ".join(names)


def _target(rel):
    for kind in ("recording", "release", "artist", "work", "place"):
        value = rel.get(kind)
        if isinstance(value, dict):
            return kind, value
    return "", {}


def _entity_url(kind, entity_id):
    if not kind or not entity_id:
        return None
    return f"https://musicbrainz.org/{kind}/{entity_id}"


def _canonical_ids(kind, entity_id):
    mapping = {
        "recording": "musicbrainz_recording_id",
        "release": "musicbrainz_release_id",
        "artist": "musicbrainz_artist_id",
    }
    key = mapping.get(kind)
    return {key: entity_id} if key and entity_id else None


def _relation_label(rel_type, direction):
    text = str(rel_type or "related").replace("_", " ").strip()
    lower = text.casefold()
    backward = str(direction or "").casefold() == "backward"
    if "sample" in lower:
        return "sampled by" if backward else "samples"
    if "remix" in lower:
        return "remixed as" if backward else "remix of"
    if "mash" in lower:
        return "mashed up as" if backward else "mash-up of"
    if "dj-mix" in lower or "dj mix" in lower:
        return "appears in DJ mix" if backward else "DJ-mix of"
    if "edit" in lower:
        return "edited as" if backward else "edit of"
    if "version" in lower or "a cappella" in lower or "instrumental" in lower or "karaoke" in lower:
        return "has version" if backward else "version of"
    if "compilation" in lower:
        return "compiled in" if backward else "compilation of"
    return text


def _badge(rel_type):
    lower = str(rel_type or "").casefold()
    for needle, label in (
        ("sample", "sample"),
        ("remix", "remix"),
        ("mash", "mash-up"),
        ("dj-mix", "DJ mix"),
        ("edit", "edit"),
        ("version", "version"),
        ("instrumental", "version"),
        ("a cappella", "version"),
        ("karaoke", "version"),
        ("compilation", "mix"),
    ):
        if needle in lower:
            return label
    return ""


def _provenance(recording_mbid):
    return {
        "source_extension_id": EXTENSION_ID,
        "source_item_id": recording_mbid,
        "source_url": f"https://musicbrainz.org/recording/{recording_mbid}",
        "retrieved_at": _now(),
        "license": "MusicBrainz core relationship data: CC0",
        "attribution": "MusicBrainz",
        "confidence": 0.95,
        "evidence": ["MusicBrainz recording relationship graph"],
    }


def context_lookup(params):
    subject = params["subject"]
    canonical = subject.get("canonical_ids") or {}
    recording_mbid = str(canonical.get("musicbrainz_recording_id") or "").strip()
    if not recording_mbid:
        return {
            "schema_version": "0.1",
            "capability": "context",
            "subject": subject,
            "cards": [],
            "cache": {"policy": "session", "ttl_seconds": None},
        }

    data = _get_json(recording_mbid)
    connections = []
    places = []
    works = []
    seen = set()
    for rel in list(data.get("relations") or []):
        if not isinstance(rel, dict):
            continue
        rel_type = str(rel.get("type") or "")
        kind, target = _target(rel)
        if not kind or not target:
            continue
        entity_id = str(target.get("id") or "")
        title = str(target.get("title") or target.get("name") or "").strip()
        if not title:
            continue
        key = (kind, entity_id, rel_type.casefold())
        if key in seen:
            continue
        seen.add(key)
        item = {
            "title": title,
            "relation": _relation_label(rel_type, rel.get("direction")),
        }
        subtitle = _artist_credit(target)
        if subtitle:
            item["subtitle"] = subtitle
        url = _entity_url(kind, entity_id)
        if url:
            item["url"] = url
        canonical_ids = _canonical_ids(kind, entity_id)
        if canonical_ids:
            item["canonical_ids"] = canonical_ids
        badge = _badge(rel_type)
        if badge:
            item["badge"] = badge

        lower = rel_type.casefold()
        if kind == "place":
            if "record" in lower:
                places.append(item)
        elif kind == "work":
            works.append(item)
        elif badge or kind in {"recording", "release"}:
            connections.append(item)

    provenance = _provenance(recording_mbid)
    cards = []
    if connections:
        cards.append({
            "id": "song-connections",
            "title": "Song Connections",
            "kind": "list",
            "priority": 90,
            "items": connections[:24],
            "provenance": provenance,
        })
    if works:
        cards.append({
            "id": "linked-works",
            "title": "Composition & Works",
            "kind": "list",
            "priority": 60,
            "items": works[:12],
            "provenance": provenance,
        })
    if places:
        cards.append({
            "id": "recording-places",
            "title": "Where It Was Recorded",
            "kind": "list",
            "priority": 55,
            "items": places[:12],
            "provenance": provenance,
        })
    return {
        "schema_version": "0.1",
        "capability": "context",
        "subject": subject,
        "cards": cards,
        "cache": {"policy": "ttl", "ttl_seconds": 2592000},
    }


def respond(request):
    if request.get("method") == "context.lookup":
        return context_lookup(request.get("params") or {})
    raise RuntimeError(f"Unsupported method: {request.get('method')}")


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
