from __future__ import annotations

import json
import os
import time
import urllib.parse
import urllib.request
from pathlib import Path

PROVIDER_ID = "org.melodex.example.librivox"
API = "https://librivox.org/api/feed/audiobooks"
USER_AGENT = os.getenv(
    "MELODEX_USER_AGENT",
    "Melodex-LibriVox-Example/0.1 (https://github.com/Cliff-Lee/melodex)",
)
BOOK_CACHE = {}
TRACK_CACHE = {}
_LAST_REQUEST = 0.0


def _fixture():
    return json.loads((Path(__file__).parent / "fixtures" / "books.json").read_text(encoding="utf-8"))


def _pace():
    global _LAST_REQUEST
    delay = 2.0 - (time.monotonic() - _LAST_REQUEST)
    if delay > 0:
        time.sleep(delay)
    _LAST_REQUEST = time.monotonic()


def _get_json(params):
    if os.getenv("MELODEX_EXAMPLE_FIXTURES") == "1":
        return _fixture()
    _pace()
    url = API + "/?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent":USER_AGENT,"Accept":"application/json"})
    with urllib.request.urlopen(req, timeout=20) as response:
        return json.load(response)


def _authors(book):
    names = []
    for author in book.get("authors") or []:
        name = " ".join(x for x in [author.get("first_name"), author.get("last_name")] if x).strip()
        if name:
            names.append(name)
    return ", ".join(names) or "Unknown author"


def _track(book, section):
    book_id = str(book["id"])
    section_id = str(section["id"])
    track_id = f"{book_id}:{section_id}"
    item = {
        "type":"track",
        "provider_id":PROVIDER_ID,
        "provider_track_id":track_id,
        "title":section.get("title") or f"Section {section.get('section_number') or ''}".strip(),
        "artist":_authors(book),
        "album":book.get("title") or "LibriVox",
        "duration_ms":int(section.get("playtime") or 0) * 1000,
        "artwork_url":book.get("coverart_jpg") or None,
        "metadata":{
            "public_domain_us":True,
            "book_id":book_id,
            "section_id":section_id,
            "section_number":section.get("section_number"),
            "language":section.get("language") or book.get("language"),
            "librivox_url":book.get("url_librivox"),
            "archive_url":book.get("url_iarchive"),
        }
    }
    TRACK_CACHE[track_id] = (book, section)
    return item


def _cache_book(book):
    BOOK_CACHE[str(book["id"])] = book
    for section in book.get("sections") or []:
        _track(book, section)


def _load_book(book_id):
    if book_id in BOOK_CACHE:
        return BOOK_CACHE[book_id]
    data = _get_json({"id":book_id,"extended":"1","format":"json","limit":"1"})
    books = data.get("books") or []
    if not books:
        raise RuntimeError("LibriVox book not found")
    _cache_book(books[0])
    return books[0]


def _find_track(track_id):
    if track_id in TRACK_CACHE:
        return TRACK_CACHE[track_id]
    try:
        book_id, section_id = track_id.split(":", 1)
    except ValueError:
        raise RuntimeError("Invalid LibriVox track id")
    book = _load_book(book_id)
    for section in book.get("sections") or []:
        if str(section.get("id")) == section_id:
            TRACK_CACHE[track_id] = (book, section)
            return book, section
    raise RuntimeError("LibriVox section not found")


def _search(query, limit):
    common = {"extended":"1","coverart":"1","format":"json","limit":str(min(limit, 20))}
    data = _get_json({**common, "title":query})
    books = data.get("books") or []
    if not books and os.getenv("MELODEX_EXAMPLE_FIXTURES") != "1":
        data = _get_json({**common, "author":query})
        books = data.get("books") or []
    return books


def respond(request):
    method = request.get("method")
    params = request.get("params") or {}

    if method == "provider.info":
        return {"id":PROVIDER_ID,"name":"LibriVox Example","version":"0.1.0",
                "protocol_version":"1.0","capabilities":["search","track","playback","offline"]}

    if method == "provider.health":
        return {"status":"ready"}

    if method == "catalog.search":
        query = str(params.get("query") or "").strip()
        limit = min(int(params.get("limit") or 25), 50)
        items = []
        for book in _search(query, limit):
            _cache_book(book)
            for section in book.get("sections") or []:
                items.append(_track(book, section))
                if len(items) >= limit:
                    break
            if len(items) >= limit:
                break
        return {"items":items,"next_cursor":None}

    if method == "catalog.get_track":
        track_id = str(params.get("provider_track_id") or params.get("track_id") or "")
        book, section = _find_track(track_id)
        return _track(book, section)

    if method in {"playback.resolve","playback.refresh"}:
        track_id = str(params.get("provider_track_id") or params.get("track_id") or "")
        book, section = _find_track(track_id)
        url = section.get("listen_url")
        if not url:
            raise RuntimeError("LibriVox section has no listen_url")
        purpose = params.get("purpose") or "stream"
        return {
            "kind":"http","url":url,"headers":{"User-Agent":USER_AGENT},"cookies":{},
            "mime_type":"audio/mpeg","expires_at":None,"seekable":True,
            "cache_policy":"offline_allowed" if purpose in {"offline","stream"} else "session",
            "refresh_token":None,"request_timeout_seconds":30,
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
