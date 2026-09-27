from __future__ import annotations

import configparser
import re
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from ..provider import MusicProvider, ProviderInfo
from ..playlist_io import load_playlist


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _valid_stream_url(value: str) -> bool:
    parsed = urlparse(_clean(value))
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _entry(raw: dict[str, Any]) -> dict[str, Any]:
    stream_id = _clean(raw.get("id")) or uuid.uuid4().hex
    name = _clean(raw.get("name")) or _clean(raw.get("title")) or "Untitled stream"
    url = _clean(raw.get("url") or raw.get("stream_url"))
    genre = _clean(raw.get("genre"))
    description = _clean(raw.get("description"))
    return {
        "id": stream_id,
        "name": name,
        "url": url,
        "genre": genre,
        "description": description,
    }


class UserStreamsProvider(MusicProvider):
    """User-managed direct HTTP(S) audio streams and radio endpoints."""

    def __init__(self, entries: list[dict[str, Any]] | None = None):
        self._entries: list[dict[str, Any]] = []
        self.set_entries(entries or [])

    @property
    def info(self) -> ProviderInfo:
        return ProviderInfo(
            id="streams",
            name="User Streams",
            description="Radio, direct audio URLs and personal stream playlists",
            capabilities=["search", "browse", "track", "playback", "library"],
            permissions={
                "network_hosts": ["*"],
                "offline_downloads": False,
                "local_files": False,
            },
        )

    def set_entries(self, entries: list[dict[str, Any]]) -> None:
        cleaned: list[dict[str, Any]] = []
        seen: set[str] = set()
        for raw in entries:
            if not isinstance(raw, dict):
                continue
            item = _entry(raw)
            if not _valid_stream_url(item["url"]):
                continue
            if item["id"] in seen:
                item["id"] = uuid.uuid4().hex
            seen.add(item["id"])
            cleaned.append(item)
        self._entries = cleaned

    def add_stream(
        self,
        name: str,
        url: str,
        genre: str = "",
        description: str = "",
    ) -> dict[str, Any]:
        url = _clean(url)
        if not _valid_stream_url(url):
            raise ValueError("Stream URL must start with http:// or https://")
        item = _entry(
            {
                "name": name,
                "url": url,
                "genre": genre,
                "description": description,
            }
        )
        self._entries.append(item)
        return dict(item)

    def update_stream(
        self,
        stream_id: str,
        name: str,
        url: str,
        genre: str = "",
        description: str = "",
    ) -> dict[str, Any]:
        url = _clean(url)
        if not _valid_stream_url(url):
            raise ValueError("Stream URL must start with http:// or https://")
        for index, item in enumerate(self._entries):
            if item["id"] == stream_id:
                updated = _entry(
                    {
                        "id": stream_id,
                        "name": name,
                        "url": url,
                        "genre": genre,
                        "description": description,
                    }
                )
                self._entries[index] = updated
                return dict(updated)
        raise KeyError(f"Unknown stream: {stream_id}")

    def remove_stream(self, stream_id: str) -> bool:
        before = len(self._entries)
        self._entries = [item for item in self._entries if item["id"] != stream_id]
        return len(self._entries) != before

    def import_playlist(self, path: Path) -> list[dict[str, Any]]:
        path = Path(path)
        suffix = path.suffix.lower()
        if suffix == ".pls":
            imported = self._load_pls(path)
        elif suffix in {".m3u", ".m3u8"}:
            playlist = load_playlist(path)
            imported = []
            for raw in playlist.get("tracks", []):
                if not isinstance(raw, dict):
                    continue
                url = _clean(raw.get("stream_url") or raw.get("url"))
                if not _valid_stream_url(url):
                    continue
                title = _clean(raw.get("title"))
                artist = _clean(raw.get("artist"))
                display = f"{artist} — {title}" if artist and title else title or artist
                imported.append(
                    {
                        "name": display or Path(urlparse(url).path).name or "Imported stream",
                        "url": url,
                        "genre": "",
                        "description": f"Imported from {path.name}",
                    }
                )
        else:
            raise ValueError("Supported stream playlists are .m3u, .m3u8 and .pls")

        added: list[dict[str, Any]] = []
        existing_urls = {item["url"] for item in self._entries}
        for raw in imported:
            url = _clean(raw.get("url"))
            if not _valid_stream_url(url) or url in existing_urls:
                continue
            item = self.add_stream(
                _clean(raw.get("name")) or "Imported stream",
                url,
                _clean(raw.get("genre")),
                _clean(raw.get("description")),
            )
            existing_urls.add(url)
            added.append(item)
        return added

    @staticmethod
    def _load_pls(path: Path) -> list[dict[str, Any]]:
        parser = configparser.ConfigParser(interpolation=None)
        parser.optionxform = str.lower
        parser.read(path, encoding="utf-8-sig")
        if not parser.has_section("playlist"):
            raise ValueError("PLS file has no [playlist] section")
        section = parser["playlist"]
        indices = sorted(
            {
                int(match.group(1))
                for key in section
                if (match := re.fullmatch(r"file(\d+)", key, flags=re.I))
            }
        )
        items: list[dict[str, Any]] = []
        for index in indices:
            url = _clean(section.get(f"file{index}", ""))
            if not _valid_stream_url(url):
                continue
            title = _clean(section.get(f"title{index}", "")) or "Imported stream"
            items.append(
                {
                    "name": title,
                    "url": url,
                    "genre": "",
                    "description": f"Imported from {path.name}",
                }
            )
        return items

    def _track(self, item: dict[str, Any]) -> dict[str, Any]:
        stream_id = item["id"]
        genre = item.get("genre", "")
        return {
            "provider_id": "streams",
            "track_id": stream_id,
            "rel": f"streams:{stream_id}",
            "title": item["name"],
            "artist": "User stream",
            "album": genre,
            "genre": genre,
            "description": item.get("description", ""),
            "stream_url": item["url"],
            "url": item["url"],
            "source": "user-streams",
        }

    def search(self, query: str, limit: int = 50) -> list[dict[str, Any]]:
        q = _clean(query).casefold()
        items = self._entries
        if q:
            items = [
                item
                for item in items
                if q
                in " ".join(
                    [
                        item["name"],
                        item["url"],
                        item.get("genre", ""),
                        item.get("description", ""),
                    ]
                ).casefold()
            ]
        return [self._track(item) for item in items[:limit]]

    def browse(self, kind: str = "featured", limit: int = 50) -> list[dict[str, Any]]:
        return [self._track(item) for item in self._entries[:limit]]

    def resolve(self, track: dict[str, Any]) -> dict[str, Any]:
        stream_id = _clean(track.get("track_id") or track.get("provider_track_id"))
        for item in self._entries:
            if item["id"] == stream_id:
                return self._track(item)
        url = _clean(track.get("stream_url") or track.get("url"))
        if _valid_stream_url(url):
            out = dict(track)
            out["provider_id"] = "streams"
            out["stream_url"] = url
            out["url"] = url
            return out
        raise RuntimeError("User stream is no longer configured")

    @property
    def entries(self) -> list[dict[str, Any]]:
        return [dict(item) for item in self._entries]
