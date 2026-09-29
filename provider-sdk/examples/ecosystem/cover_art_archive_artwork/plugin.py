from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

EXTENSION_ID = "org.melodex.example.cover-art-archive"
BASE = "https://coverartarchive.org"
USER_AGENT = os.getenv(
    "MELODEX_USER_AGENT",
    "Melodex-CoverArtArchive-Example/0.1 (https://github.com/Cliff-Lee/melodex)",
)


def _now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _fixture():
    return json.loads((Path(__file__).parent / "fixtures" / "release.json").read_text(encoding="utf-8"))


def _get_json(path):
    if os.getenv("MELODEX_EXAMPLE_FIXTURES") == "1":
        return _fixture()
    req = urllib.request.Request(
        BASE + path,
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return {}
        raise


def _pick_url(image):
    thumbs = image.get("thumbnails") if isinstance(image.get("thumbnails"), dict) else {}
    return (
        thumbs.get("1200")
        or thumbs.get("500")
        or thumbs.get("large")
        or thumbs.get("250")
        or image.get("image")
    )


def artwork_lookup(params):
    subject = params["subject"]
    canonical = subject.get("canonical_ids") or {}
    release_id = str(canonical.get("musicbrainz_release_id") or "").strip()
    release_group_id = str(canonical.get("musicbrainz_release_group_id") or "").strip()

    if release_id:
        path = f"/release/{urllib.parse.quote(release_id, safe="")}/"
        source_id = release_id
        evidence = ["MusicBrainz release ID supplied by caller"]
    elif release_group_id:
        path = f"/release-group/{urllib.parse.quote(release_group_id, safe="")}/"
        source_id = release_group_id
        evidence = ["MusicBrainz release-group ID supplied by caller"]
    else:
        return {
            "schema_version": "0.1",
            "capability": "artwork",
            "subject": subject,
            "assets": [],
            "cache": {"policy": "session", "ttl_seconds": None},
        }

    data = _get_json(path)
    max_results = max(1, min(int(params.get("max_results") or 5), 20))
    assets = []
    images = [row for row in (data.get("images") or []) if isinstance(row, dict)]
    images.sort(key=lambda row: (not bool(row.get("front")), bool(row.get("back"))))
    for image in images[:max_results]:
        url = _pick_url(image)
        if not url:
            continue
        types = [str(x) for x in image.get("types") or []]
        role = "cover" if image.get("front") or "Front" in types else "other"
        image_id = str(image.get("id") or "")
        assets.append({
            "url": url,
            "role": role,
            "width": None,
            "height": None,
            "mime_type": None,
            "variant": str(image.get("comment") or ", ".join(types) or "Cover Art Archive image"),
            "score": 1.0 if role == "cover" else 0.75,
            "provenance": {
                "source_extension_id": EXTENSION_ID,
                "source_item_id": image_id or source_id,
                "source_url": f"{BASE}{path}",
                "retrieved_at": _now(),
                "license": "Artwork rights vary by image; inspect the linked Cover Art Archive/Internet Archive source",
                "attribution": "Cover Art Archive / MusicBrainz community",
                "confidence": 1.0,
                "evidence": evidence + (["Front cover selected by Cover Art Archive"] if role == "cover" else []),
            },
        })

    return {
        "schema_version": "0.1",
        "capability": "artwork",
        "subject": subject,
        "assets": assets,
        "cache": {"policy": "ttl", "ttl_seconds": 604800},
    }


def respond(request):
    if request.get("method") == "artwork.lookup":
        return artwork_lookup(request.get("params") or {})
    raise RuntimeError(f"Unsupported method: {request.get('method')}")


def run_jsonrpc(respond):
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


if __name__ == "__main__":
    run_jsonrpc(respond)
