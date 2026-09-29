from __future__ import annotations

import html
import json
import os
import re
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

EXTENSION_ID = "org.melodex.example.wikimedia-commons"
API = "https://commons.wikimedia.org/w/api.php"
USER_AGENT = os.getenv(
    "MELODEX_USER_AGENT",
    "Melodex-Wikimedia-Example/0.1 (https://github.com/Cliff-Lee/melodex)",
)


def _now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _plain(value):
    text = re.sub(r"<[^>]+>", "", str(value or ""))
    return html.unescape(text).strip()


def _fixture():
    return json.loads((Path(__file__).parent / "fixtures" / "search.json").read_text(encoding="utf-8"))


def _get_json(params):
    if os.getenv("MELODEX_EXAMPLE_FIXTURES") == "1":
        return _fixture()
    url = API + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as response:
        return json.load(response)


def _meta(ext, key):
    value = (ext.get(key) or {}).get("value")
    return _plain(value) if value else None


def artwork_lookup(params):
    subject = params["subject"]
    hints = subject.get("hints") or {}
    entity_type = subject["entity_type"]

    if entity_type == "artist":
        query = hints.get("name") or hints.get("artist")
        role = "portrait"
    elif entity_type == "album":
        query = " ".join(x for x in [hints.get("artist"), hints.get("title") or hints.get("album")] if x)
        role = "cover"
    else:
        query = " ".join(x for x in [hints.get("artist"), hints.get("title")] if x)
        role = "other"

    if not query:
        return {"schema_version":"0.1","capability":"artwork","subject":subject,"assets":[],
                "cache":{"policy":"session","ttl_seconds":None}}

    limit = max(1, min(int(params.get("max_results") or 5), 20))
    data = _get_json({
        "action":"query","format":"json","formatversion":"2",
        "generator":"search","gsrsearch":query,"gsrnamespace":"6","gsrlimit":str(limit),
        "prop":"imageinfo","iiprop":"url|size|mime|extmetadata",
    })

    assets = []
    for page in (data.get("query") or {}).get("pages") or []:
        info_rows = page.get("imageinfo") or []
        if not info_rows:
            continue
        info = info_rows[0]
        url = str(info.get("url") or "").strip()
        if not url:
            continue
        ext = info.get("extmetadata") or {}
        license_name = _meta(ext, "LicenseShortName")
        license_url = _meta(ext, "LicenseUrl")
        author = _meta(ext, "Artist")
        credit = _meta(ext, "Credit")
        attribution = "; ".join(x for x in [author, credit] if x)
        if license_url:
            license_name = f"{license_name or 'Licence'} — {license_url}"
        assets.append({
            "url": url,
            "role": role,
            "width": info.get("width"),
            "height": info.get("height"),
            "mime_type": info.get("mime"),
            "variant": _meta(ext, "ObjectName") or page.get("title"),
            "score": 0.75,
            "provenance": {
                "source_extension_id": EXTENSION_ID,
                "source_item_id": str(page.get("pageid") or ""),
                "source_url": info.get("descriptionurl") or info.get("descriptionshorturl"),
                "retrieved_at": _now(),
                "license": license_name,
                "attribution": attribution or None,
                "confidence": 0.75,
                "evidence": ["Wikimedia Commons file search result"],
            },
        })

    return {
        "schema_version":"0.1","capability":"artwork","subject":subject,"assets":assets,
        "cache":{"policy":"ttl","ttl_seconds":604800},
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
            result = respond(request)
            payload = {"jsonrpc":"2.0","id":request.get("id"),"result":result}
        except Exception as exc:
            payload = {"jsonrpc":"2.0","id":request.get("id") if isinstance(request,dict) else None,
                       "error":{"code":-32000,"message":str(exc)}}
        print(json.dumps(payload, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    run_jsonrpc(respond)
