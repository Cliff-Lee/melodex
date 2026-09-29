from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

EXTENSION_ID = "org.melodex.example.listenbrainz-tags"
API = "https://api.listenbrainz.org/1/metadata/recording/"
USER_AGENT = os.getenv(
    "MELODEX_USER_AGENT",
    "Melodex-ListenBrainz-Tags-Example/0.1 (https://github.com/Cliff-Lee/melodex)",
)


def _now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _fixture():
    return json.loads((Path(__file__).parent / "fixtures" / "recording.json").read_text(encoding="utf-8"))


def _get_json(recording_mbid):
    if os.getenv("MELODEX_EXAMPLE_FIXTURES") == "1":
        return _fixture()
    query = urllib.parse.urlencode({
        "recording_mbids": recording_mbid,
        "inc": "tag",
    })
    req = urllib.request.Request(
        API + "?" + query,
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=20) as response:
        return json.load(response)


def _provenance(recording_mbid, confidence=0.85):
    return {
        "source_extension_id": EXTENSION_ID,
        "source_item_id": recording_mbid,
        "source_url": f"https://listenbrainz.org/player/?recording_mbids={recording_mbid}",
        "retrieved_at": _now(),
        "license": "ListenBrainz user listen data/text is CC0; incorporated MusicBrainz data may have separate MetaBrainz licensing",
        "attribution": "ListenBrainz / MetaBrainz community",
        "confidence": confidence,
        "evidence": ["ListenBrainz recording metadata tag aggregate"],
    }


def _record(data, recording_mbid):
    if isinstance(data.get(recording_mbid), dict):
        return data[recording_mbid]
    rows = data.get("recordings")
    if isinstance(rows, list):
        return next(
            (
                row
                for row in rows
                if str(row.get("recording_mbid") or row.get("id") or "") == recording_mbid
            ),
            {},
        )
    return {}


def metadata_enrich(params):
    subject = params["subject"]
    canonical = subject.get("canonical_ids") or {}
    recording_mbid = str(canonical.get("musicbrainz_recording_id") or "").strip()
    if not recording_mbid:
        return {
            "schema_version": "0.1",
            "capability": "metadata",
            "subject": subject,
            "fields": {},
            "cache": {"policy": "session", "ttl_seconds": None},
        }

    data = _get_json(recording_mbid)
    row = _record(data, recording_mbid)
    tag_block = row.get("tag") if isinstance(row.get("tag"), dict) else {}
    recording_tags = [
        item for item in (tag_block.get("recording") or []) if isinstance(item, dict)
    ]
    recording_tags.sort(
        key=lambda item: (
            -int(item.get("count") or 0),
            str(item.get("tag") or "").casefold(),
        )
    )

    tags = []
    counts = []
    for item in recording_tags:
        name = str(item.get("tag") or "").strip()
        if not name:
            continue
        tags.append(name)
        counts.append({
            "tag": name,
            "count": int(item.get("count") or 0),
            "genre_mbid": item.get("genre_mbid"),
        })

    requested = set(params.get("requested_fields") or [])
    all_fields = not requested
    fields = {}
    provenance = _provenance(recording_mbid)

    if tags and (all_fields or "community_tags" in requested):
        fields["community_tags"] = {"value": tags[:20], "provenance": provenance}
    if counts and (all_fields or "community_tag_counts" in requested):
        fields["community_tag_counts"] = {
            "value": counts[:20],
            "provenance": provenance,
        }
    if tags and (all_fields or "genres" in requested):
        fields["genres"] = {
            "value": tags[:8],
            "provenance": _provenance(recording_mbid, 0.75),
        }

    return {
        "schema_version": "0.1",
        "capability": "metadata",
        "subject": subject,
        "fields": fields,
        "cache": {"policy": "ttl", "ttl_seconds": 86400},
    }


def respond(request):
    if request.get("method") == "metadata.enrich":
        return metadata_enrich(request.get("params") or {})
    raise RuntimeError(f"Unsupported method: {request.get('method')}")


def run_jsonrpc(respond):
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
    run_jsonrpc(respond)
