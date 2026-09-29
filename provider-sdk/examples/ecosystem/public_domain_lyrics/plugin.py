from __future__ import annotations

import json
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

EXTENSION_ID = "org.melodex.example.public-domain-lyrics"


def _now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _catalog():
    return json.loads(
        (Path(__file__).parent / "fixtures" / "catalog.json").read_text(encoding="utf-8")
    )


def _key(value):
    text = unicodedata.normalize("NFKD", str(value or "")).casefold()
    return re.sub(r"[^a-z0-9]+", "", text)


def _find(subject):
    hints = subject.get("hints") or {}
    title = _key(hints.get("title") or hints.get("name"))
    if not title:
        return None
    for row in _catalog().get("songs") or []:
        candidates = [row.get("title"), *(row.get("aliases") or [])]
        if title in {_key(value) for value in candidates if value}:
            return row
    return None


def lyrics_lookup(params):
    subject = params["subject"]
    row = _find(subject)
    requested_kinds = set(params.get("kinds") or [])
    requested_languages = {
        str(x).casefold() for x in (params.get("languages") or [])
    }

    entries = []
    if row:
        language = str(row.get("language") or "en")
        kind_allowed = not requested_kinds or "plain" in requested_kinds
        language_allowed = (
            not requested_languages or language.casefold() in requested_languages
        )
        if kind_allowed and language_allowed:
            entries.append(
                {
                    "kind": "plain",
                    "language": language,
                    "translation_of_language": None,
                    "text": str(row.get("text") or ""),
                    "copyright_notice": str(row.get("rights") or "") or None,
                    "provenance": {
                        "source_extension_id": EXTENSION_ID,
                        "source_item_id": str(row.get("id") or ""),
                        "source_url": row.get("source_url"),
                        "retrieved_at": _now(),
                        "license": "Public domain historical text; see per-entry rights note",
                        "attribution": row.get("attribution"),
                        "confidence": 1.0,
                        "evidence": [
                            "Exact normalized title match in bundled example corpus"
                        ],
                    },
                }
            )

    return {
        "schema_version": "0.1",
        "capability": "lyrics",
        "subject": subject,
        "entries": entries,
        "cache": {"policy": "persistent", "ttl_seconds": None},
    }


def respond(request):
    if request.get("method") == "lyrics.lookup":
        return lyrics_lookup(request.get("params") or {})
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
