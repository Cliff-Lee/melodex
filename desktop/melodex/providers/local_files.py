from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from ..provider import MusicProvider, ProviderInfo

AUDIO_EXTS = {".mp3", ".flac", ".m4a", ".aac", ".ogg", ".opus", ".wav", ".aiff", ".wma"}


class LocalFilesProvider(MusicProvider):
    def __init__(self, roots: list[Path] | None = None):
        self.roots = [Path(p) for p in (roots or [])]
        self._tracks: list[dict[str, Any]] = []
        if self.roots:
            self.scan()

    @property
    def info(self) -> ProviderInfo:
        return ProviderInfo(
            id="local", name="This computer", description="Music files you choose on this device",
            capabilities=["search", "browse", "track", "playback", "library", "offline"],
            permissions={"network_hosts": [], "offline_downloads": False, "local_files": True},
        )

    def set_roots(self, roots: list[Path]) -> None:
        self.roots = [Path(x) for x in roots]
        self.scan()

    @staticmethod
    def _metadata(path: Path) -> dict[str, Any]:
        title, artist, album = path.stem, "", ""
        duration = 0.0
        musicbrainz_recording_id = ""
        musicbrainz_artist_id = ""
        musicbrainz_release_id = ""
        musicbrainz_release_group_id = ""
        try:
            from mutagen import File
            audio = File(path, easy=True)
            if audio:
                def first(key: str) -> str:
                    val = audio.tags.get(key, []) if audio.tags else []
                    return str(val[0]) if val else ""
                title = first("title") or title
                artist = first("artist")
                album = first("album")
                duration = float(getattr(getattr(audio, "info", None), "length", 0.0) or 0.0)
                musicbrainz_recording_id = (
                    first("musicbrainz_recordingid")
                    or first("musicbrainz_trackid")
                )
                musicbrainz_artist_id = (
                    first("musicbrainz_artistid")
                    or first("musicbrainz_albumartistid")
                )
                musicbrainz_release_id = first("musicbrainz_albumid")
                musicbrainz_release_group_id = first("musicbrainz_releasegroupid")
        except Exception:
            pass
        out = {
            "provider_id": "local", "track_id": str(path.resolve()), "rel": f"local:{path.resolve()}",
            "title": title, "artist": artist or "Unknown artist", "album": album,
            "duration": duration, "local_path": str(path.resolve()), "source": "local",
        }
        for key, value in (
            ("musicbrainz_recording_id", musicbrainz_recording_id),
            ("musicbrainz_artist_id", musicbrainz_artist_id),
            ("musicbrainz_release_id", musicbrainz_release_id),
            ("musicbrainz_release_group_id", musicbrainz_release_group_id),
        ):
            if value:
                out[key] = value
        return out

    def scan(self) -> int:
        tracks: list[dict[str, Any]] = []
        for root in self.roots:
            if not root.exists():
                continue
            for base, _, files in os.walk(root):
                for name in files:
                    p = Path(base) / name
                    if p.suffix.lower() in AUDIO_EXTS:
                        tracks.append(self._metadata(p))
        self._tracks = tracks
        return len(tracks)

    def search(self, query: str, limit: int = 50) -> list[dict[str, Any]]:
        q = query.casefold().strip()
        if not q:
            return self._tracks[:limit]
        scored = []
        for t in self._tracks:
            hay = f"{t.get('artist','')} {t.get('title','')} {t.get('album','')}".casefold()
            if q in hay:
                score = 2 if str(t.get("title", "")).casefold().startswith(q) else 1
                scored.append((score, t))
        scored.sort(key=lambda x: (-x[0], str(x[1].get("artist", "")), str(x[1].get("title", ""))))
        return [dict(t) for _, t in scored[:limit]]

    def browse(self, kind: str = "featured", limit: int = 50) -> list[dict[str, Any]]:
        return [dict(x) for x in self._tracks[:limit]]

    def resolve(self, track: dict[str, Any]) -> dict[str, Any]:
        if track.get("local_path"):
            return dict(track)
        tid = str(track.get("track_id") or "")
        for item in self._tracks:
            if str(item.get("track_id") or "") == tid:
                return dict(item)
        raise RuntimeError("Local track is no longer in the indexed folders")

    @property
    def tracks(self) -> list[dict[str, Any]]:
        return [dict(x) for x in self._tracks]
