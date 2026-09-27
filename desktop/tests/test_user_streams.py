from pathlib import Path

import pytest

from melodex.provider_manager import ProviderManager
from melodex.providers.user_streams import UserStreamsProvider


def test_add_search_and_resolve_stream():
    provider = UserStreamsProvider()
    item = provider.add_stream(
        "Deep Space Radio",
        "https://radio.example.test/live.mp3",
        genre="Ambient",
    )
    results = provider.search("ambient")
    assert len(results) == 1
    assert results[0]["track_id"] == item["id"]
    resolved = provider.resolve(results[0])
    assert resolved["stream_url"] == "https://radio.example.test/live.mp3"


def test_rejects_non_http_stream():
    provider = UserStreamsProvider()
    with pytest.raises(ValueError):
        provider.add_stream("Bad", "file:///tmp/music.mp3")


def test_import_m3u_and_m3u8(tmp_path: Path):
    provider = UserStreamsProvider()
    path = tmp_path / "radio.m3u8"
    path.write_text(
        "#EXTM3U\n"
        "#EXTINF:-1,Example Artist - Example Radio\n"
        "https://radio.example.test/live.aac\n",
        encoding="utf-8",
    )
    added = provider.import_playlist(path)
    assert len(added) == 1
    assert added[0]["name"] == "Example Artist — Example Radio"


def test_import_pls(tmp_path: Path):
    provider = UserStreamsProvider()
    path = tmp_path / "radio.pls"
    path.write_text(
        "[playlist]\n"
        "NumberOfEntries=1\n"
        "File1=https://radio.example.test/live.mp3\n"
        "Title1=Example Radio\n"
        "Length1=-1\n",
        encoding="utf-8",
    )
    added = provider.import_playlist(path)
    assert len(added) == 1
    assert added[0]["name"] == "Example Radio"


def test_provider_manager_persists_user_streams(tmp_path: Path):
    manager = ProviderManager(tmp_path)
    try:
        item = manager.add_user_stream(
            "Persistent Radio",
            "https://radio.example.test/persistent.mp3",
            "Electronic",
        )
        assert item["name"] == "Persistent Radio"
    finally:
        manager.close()

    restored = ProviderManager(tmp_path)
    try:
        entries = restored.user_streams()
        assert len(entries) == 1
        assert entries[0]["url"] == "https://radio.example.test/persistent.mp3"
    finally:
        restored.close()
