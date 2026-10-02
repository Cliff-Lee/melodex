from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_provider():
    path = (
        Path(__file__).resolve().parents[1]
        / "bundled_provider_sources"
        / "nichedb_radio"
        / "provider.py"
    )
    spec = importlib.util.spec_from_file_location("melodex_test_nichedb_radio", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _station(*, item_id: int = 101, online: bool = True) -> dict:
    return {
        "id": item_id,
        "collection": "radio",
        "source": "radio-browser-stations",
        "adapter": "radiobrowser",
        "kind": "station",
        "external_id": f"station-uuid-{item_id}",
        "title": "Example Jazz FM" if online else "Broken Station",
        "summary": "London, United Kingdom · english · jazz · MP3 192 kbps",
        "url": "https://example.fm/",
        "image_url": "https://example.fm/icon.png",
        "tags": [
            "radio-browser",
            "online" if online else "offline",
            "popular",
            "country:gb",
            "codec:mp3",
            "lang:english",
            "jazz",
            "geo",
        ],
        "data": {
            "stationUuid": f"station-uuid-{item_id}",
            "name": "Example Jazz FM" if online else "Broken Station",
            "stream": "https://stream.example.fm/live.mp3",
            "streamUrl": "https://stream.example.fm/live.mp3",
            "homepage": "https://example.fm/",
            "country": "United Kingdom",
            "countryCode": "GB",
            "state": "England",
            "languages": ["english"],
            "languageCodes": ["eng"],
            "genres": ["jazz"],
            "codec": "MP3",
            "bitrate": 192,
            "hls": False,
            "online": online,
            "votes": 1200,
            "clicksLast24h": 250,
            "clickTrend": 3,
            "lat": 51.5,
            "long": -0.1,
            "page": f"https://www.radio-browser.info/history/station-uuid-{item_id}",
        },
        "page": f"https://nichedb.dev/i/{item_id}",
    }


def test_search_filters_offline_and_preserves_rich_metadata(monkeypatch):
    provider = _load_provider()
    online = _station()
    offline = _station(item_id=102, online=False)
    calls = []

    def fake_get(path, params=None, *, use_cache=False):
        calls.append((path, params, use_cache))
        return {"items": [offline, online]}

    monkeypatch.setattr(provider, "_get_json", fake_get)
    result = provider.respond(
        {"method": "catalog.search", "params": {"query": "jazz", "limit": 10}}
    )

    assert len(result["items"]) == 1
    track = result["items"][0]
    assert track["title"] == "Example Jazz FM"
    assert track["artist"] == "United Kingdom"
    assert track["metadata"]["genres"] == ["jazz"]
    assert track["metadata"]["codec"] == "MP3"
    assert track["metadata"]["bitrate"] == 192
    assert track["metadata"]["latitude"] == 51.5
    assert track["metadata"]["longitude"] == -0.1
    assert calls[-1][0] == "/search"
    assert calls[-1][1]["collection"] == "radio"
    assert calls[-1][1]["kind"] == "station"


def test_power_searches_use_nichedb_tags(monkeypatch):
    provider = _load_provider()
    calls = []

    def fake_get(path, params=None, *, use_cache=False):
        calls.append((path, params, use_cache))
        return {"items": [_station()]}

    monkeypatch.setattr(provider, "_get_json", fake_get)

    cases = {
        "popular": "online,popular",
        "genre:ambient": "online,ambient",
        "country:gb": "online,country:gb",
        "lang:english": "online,lang:english",
        "codec:mp3": "online,codec:mp3",
    }
    for query, tags in cases.items():
        provider._SEARCH_CACHE.clear()
        result = provider.respond(
            {"method": "catalog.search", "params": {"query": query, "limit": 5}}
        )
        assert result["items"]
        assert calls[-1][0] == "/items"
        assert calls[-1][1]["tags"] == tags


def test_playback_resolves_direct_station_stream(monkeypatch):
    provider = _load_provider()
    station = _station()
    provider._ITEM_CACHE.clear()

    def fake_get(path, params=None, *, use_cache=False):
        assert path == "/items/101"
        return {"item": station}

    monkeypatch.setattr(provider, "_get_json", fake_get)
    resource = provider.respond(
        {"method": "playback.resolve", "params": {"track_id": "101"}}
    )

    assert resource["kind"] == "http"
    assert resource["url"] == "https://stream.example.fm/live.mp3"
    assert resource["seekable"] is False
    assert resource["cache_policy"] == "none"
    assert resource["refresh_token"] == "101"


def test_offline_station_is_not_playable(monkeypatch):
    provider = _load_provider()
    provider._ITEM_CACHE.clear()

    def fake_get(path, params=None, *, use_cache=False):
        return {"item": _station(online=False)}

    monkeypatch.setattr(provider, "_get_json", fake_get)

    import pytest

    with pytest.raises(RuntimeError, match="offline"):
        provider.respond(
            {"method": "playback.resolve", "params": {"track_id": "101"}}
        )

def test_http_uses_requests_session_and_reports_tls_failure(monkeypatch):
    provider = _load_provider()
    provider._SEARCH_CACHE.clear()

    class FakeResponse:
        headers = {"x-ratelimit-remaining": "599"}
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {"items": [_station()]}

    calls = []

    def fake_get(url, timeout):
        calls.append((url, timeout))
        return FakeResponse()

    monkeypatch.setattr(provider._SESSION, "get", fake_get)
    payload = provider._get_json(
        "/search",
        {"q": "jazz", "collection": "radio", "kind": "station", "limit": 5},
    )
    assert payload["items"]
    assert calls and calls[0][0].startswith("https://nichedb.dev/api/v1/search?")
    assert calls[0][1] == 15

    def ssl_failure(url, timeout):
        raise provider.requests.exceptions.SSLError("certificate chain unavailable")

    provider._SEARCH_CACHE.clear()
    monkeypatch.setattr(provider._SESSION, "get", ssl_failure)

    import pytest

    with pytest.raises(RuntimeError, match="TLS verification failed"):
        provider._get_json("/search", {"q": "jazz"})

