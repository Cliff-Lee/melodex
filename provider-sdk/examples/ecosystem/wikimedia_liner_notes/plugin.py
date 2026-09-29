from __future__ import annotations

import json
import os
import re
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

EXTENSION_ID = "org.melodex.example.wikimedia-liner-notes"
USER_AGENT = os.getenv(
    "MELODEX_USER_AGENT",
    "Melodex-Wikimedia-Liner-Notes/0.1.0 (https://github.com/Cliff-Lee/melodex)",
)


def _now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _fixture():
    return json.loads(
        (Path(__file__).parent / "fixtures" / "context.json").read_text(
            encoding="utf-8"
        )
    )


def _get_json(url):
    request = urllib.request.Request(
        url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"}
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        return json.load(response)


def _wikidata(qid):
    if os.getenv("MELODEX_EXAMPLE_FIXTURES") == "1":
        return _fixture()["wikidata"]
    return _get_json(
        "https://www.wikidata.org/wiki/Special:EntityData/"
        + urllib.parse.quote(qid, safe="")
        + ".json"
    )


def _summary(title):
    if os.getenv("MELODEX_EXAMPLE_FIXTURES") == "1":
        return _fixture()["summary"]
    return _get_json(
        "https://en.wikipedia.org/api/rest_v1/page/summary/"
        + urllib.parse.quote(title.replace(" ", "_"), safe="")
    )


def context_lookup(params):
    subject = params["subject"]
    canonical = subject.get("canonical_ids") or {}
    qid = str(canonical.get("wikidata_id") or "").strip()
    if not qid or not re.fullmatch(r"Q[1-9]\d*", qid):
        return {
            "schema_version": "0.1",
            "capability": "context",
            "subject": subject,
            "cards": [],
            "cache": {"policy": "session", "ttl_seconds": None},
        }

    wikidata = _wikidata(qid)
    entity = (
        (wikidata.get("entities") or {}).get(qid)
        if isinstance(wikidata.get("entities"), dict)
        else {}
    ) or {}
    sitelinks = entity.get("sitelinks") if isinstance(entity, dict) else {}
    enwiki = sitelinks.get("enwiki") if isinstance(sitelinks, dict) else {}
    title = str((enwiki or {}).get("title") or "").strip()
    if not title:
        return {
            "schema_version": "0.1",
            "capability": "context",
            "subject": subject,
            "cards": [],
            "cache": {"policy": "ttl", "ttl_seconds": 604800},
        }

    summary = _summary(title)
    extract = str(summary.get("extract") or "").strip()
    if not extract:
        return {
            "schema_version": "0.1",
            "capability": "context",
            "subject": subject,
            "cards": [],
            "cache": {"policy": "ttl", "ttl_seconds": 604800},
        }
    content_urls = summary.get("content_urls") if isinstance(summary.get("content_urls"), dict) else {}
    desktop = content_urls.get("desktop") if isinstance(content_urls, dict) else {}
    source_url = str((desktop or {}).get("page") or "")
    if not source_url:
        source_url = "https://en.wikipedia.org/wiki/" + urllib.parse.quote(
            title.replace(" ", "_"), safe=""
        )

    provenance = {
        "source_extension_id": EXTENSION_ID,
        "source_item_id": qid,
        "source_url": source_url,
        "retrieved_at": _now(),
        "license": "Wikipedia text: CC BY-SA; Wikidata structured data: CC0",
        "attribution": "Wikipedia contributors / Wikidata",
        "confidence": 0.9,
        "evidence": ["Wikidata English Wikipedia sitelink", "Wikipedia page summary"],
    }
    return {
        "schema_version": "0.1",
        "capability": "context",
        "subject": subject,
        "cards": [
            {
                "id": "liner-note",
                "title": "Liner Notes",
                "kind": "text",
                "priority": 80,
                "text": extract,
                "provenance": provenance,
            }
        ],
        "cache": {"policy": "ttl", "ttl_seconds": 604800},
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
