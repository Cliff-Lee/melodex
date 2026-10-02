from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Callable

from ..provider import MusicProvider, ProviderInfo
from ..library_scan import ProgressThrottle, ScanCancelled, ScanControl
from ..scan_metrics import ScanProbe

AUDIO_EXTS = {".mp3", ".flac", ".m4a", ".aac", ".ogg", ".opus", ".wav", ".aiff", ".wma"}


class LocalFilesProvider(MusicProvider):
    EDITABLE_METADATA_FIELDS = {
        "title", "artist", "album", "album_artist", "year", "genre",
        "track_number", "disc_number",
    }

    def __init__(
        self,
        roots: list[Path] | None = None,
        overrides: dict[str, dict[str, Any]] | None = None,
        *,
        scan_on_init: bool = True,
    ):
        self.roots = [Path(p) for p in (roots or [])]
        self.overrides = {
            str(key): dict(value)
            for key, value in dict(overrides or {}).items()
            if isinstance(value, dict)
        }
        self._tracks: list[dict[str, Any]] = []
        self._last_scan_metrics: dict[str, object] = {}
        if self.roots and scan_on_init:
            self.scan()

    @staticmethod
    def _override_key(path: str | Path) -> str:
        value = Path(path).expanduser()
        try:
            value = value.resolve()
        except Exception:
            pass
        return str(value)

    def _apply_override(self, track: dict[str, Any]) -> dict[str, Any]:
        out = dict(track)
        local_path = str(out.get("local_path") or out.get("track_id") or "")
        if not local_path:
            return out
        override = self.overrides.get(self._override_key(local_path), {})
        for key, value in dict(override).items():
            if key in self.EDITABLE_METADATA_FIELDS:
                out[key] = value
        return out

    def set_metadata_override(
        self,
        local_path: str | Path,
        changes: dict[str, Any],
    ) -> dict[str, Any]:
        key = self._override_key(local_path)
        clean = {
            field: value
            for field, value in dict(changes or {}).items()
            if field in self.EDITABLE_METADATA_FIELDS
        }
        existing = dict(self.overrides.get(key) or {})
        existing.update(clean)
        self.overrides[key] = existing
        for index, track in enumerate(self._tracks):
            if self._override_key(str(track.get("local_path") or "")) == key:
                self._tracks[index] = self._apply_override(track)
                return dict(self._tracks[index])
        return {}

    def clear_metadata_override(
        self,
        local_path: str | Path,
        *,
        rescan: bool = True,
    ) -> bool:
        key = self._override_key(local_path)
        changed = key in self.overrides
        self.overrides.pop(key, None)
        if changed and rescan:
            # Compatibility for non-GUI callers. The desktop manager passes
            # rescan=False and schedules the filesystem work asynchronously.
            self.scan()
        return changed

    @property
    def info(self) -> ProviderInfo:
        return ProviderInfo(
            id="local", name="This computer", description="Music files you choose on this device",
            capabilities=["search", "browse", "track", "playback", "library", "offline"],
            permissions={"network_hosts": [], "offline_downloads": False, "local_files": True},
        )

    def configure_roots(self, roots: list[Path]) -> None:
        """Update configured roots without touching the filesystem."""
        self.roots = [Path(x) for x in roots]

    def set_roots(self, roots: list[Path]) -> None:
        """Compatibility API for callers that explicitly want a synchronous scan."""
        self.configure_roots(roots)
        self.scan()

    @staticmethod
    def _metadata(path: Path) -> dict[str, Any]:
        title, artist, album = path.stem, "", ""
        duration = 0.0
        album_artist = ""
        date = ""
        genre = ""
        track_number = 0
        disc_number = 0
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
                album_artist = first("albumartist")
                date = first("date") or first("originaldate")
                genre = first("genre")
                def number(key: str) -> int:
                    raw = first(key).split("/", 1)[0].strip()
                    return int(raw) if raw.isdigit() else 0
                track_number = number("tracknumber")
                disc_number = number("discnumber")
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
            ("album_artist", album_artist),
            ("date", date),
            ("genre", genre),
            ("track_number", track_number),
            ("disc_number", disc_number),
            ("musicbrainz_recording_id", musicbrainz_recording_id),
            ("musicbrainz_artist_id", musicbrainz_artist_id),
            ("musicbrainz_release_id", musicbrainz_release_id),
            ("musicbrainz_release_group_id", musicbrainz_release_group_id),
        ):
            if value:
                out[key] = value
        if date[:4].isdigit():
            out["year"] = int(date[:4])
        return out

    def scan_snapshot(
        self,
        roots: list[Path] | None = None,
        *,
        progress: Callable[[dict[str, Any]], None] | None = None,
        control: ScanControl | None = None,
    ) -> dict[str, Any]:
        """Scan roots without mutating the live provider catalog.

        Filesystem traversal and metadata reads may run on a worker thread. A
        cooperative control object provides pause/cancel checkpoints between
        filesystem operations; Campaign 6 will harden cancellation of an OS call
        that is already blocked inside a network filesystem.
        """
        scan_roots = [Path(x) for x in (self.roots if roots is None else roots)]
        overrides = {
            str(key): dict(value)
            for key, value in self.overrides.items()
            if isinstance(value, dict)
        }
        control = control or ScanControl()
        throttle = ProgressThrottle()
        audio_paths: list[Path] = []
        tracks: list[dict[str, Any]] = []
        index_tracks: list[dict[str, Any]] = []
        root_states: list[dict[str, Any]] = []
        probe = ScanProbe(len(scan_roots))

        def emit(
            phase: str,
            *,
            force: bool = False,
            current: str = "",
            completed: int = 0,
            total: int = 0,
        ) -> None:
            if progress is None or not throttle.ready(force=force):
                return
            progress(
                {
                    "phase": phase,
                    "files_seen": probe.metrics.files_seen,
                    "audio_files_seen": probe.metrics.audio_files_seen,
                    "directories_seen": probe.metrics.directories_seen,
                    "completed": max(0, int(completed)),
                    "total": max(0, int(total)),
                    # Only a basename is exposed to the UI; never a private path.
                    "current": Path(current).name if current else "",
                    "paused": control.paused,
                    "cancelled": control.cancelled,
                }
            )

        cancelled = False
        emit("discovering", force=True)
        try:
            for root in scan_roots:
                control.checkpoint()
                exists = root.exists()
                probe.root_checked(exists=exists)
                root_states.append({
                    "path": str(root),
                    "available": bool(exists),
                })
                if not exists:
                    continue
                for base, _, files in os.walk(root):
                    control.checkpoint()
                    probe.directory_seen()
                    for name in files:
                        control.checkpoint()
                        p = Path(base) / name
                        is_audio = p.suffix.lower() in AUDIO_EXTS
                        probe.file_seen(audio=is_audio)
                        if is_audio:
                            audio_paths.append(p)
                        emit(
                            "discovering",
                            current=Path(base).name,
                        )

            emit(
                "metadata",
                force=True,
                completed=0,
                total=len(audio_paths),
            )
            for index, p in enumerate(audio_paths, start=1):
                control.checkpoint()
                with probe.metadata_read():
                    raw_metadata = self._metadata(p)
                index_tracks.append(dict(raw_metadata))
                metadata = dict(raw_metadata)
                local_path = str(
                    metadata.get("local_path")
                    or metadata.get("track_id")
                    or ""
                )
                override = overrides.get(
                    self._override_key(local_path),
                    {},
                )
                if override:
                    for key, value in override.items():
                        if key in self.EDITABLE_METADATA_FIELDS:
                            metadata[key] = value
                tracks.append(metadata)
                emit(
                    "metadata",
                    current=p.name,
                    completed=index,
                    total=len(audio_paths),
                )
        except ScanCancelled:
            cancelled = True
        finally:
            metrics = probe.finish(tracks_indexed=len(tracks))

        if cancelled:
            emit(
                "cancelled",
                force=True,
                completed=len(tracks),
                total=len(audio_paths),
            )
            return {
                "tracks": [],
                "index_tracks": [],
                "metrics": metrics,
                "root_states": root_states,
                "cancelled": True,
            }

        emit(
            "complete",
            force=True,
            completed=len(tracks),
            total=len(audio_paths),
        )
        return {
            "tracks": tracks,
            "index_tracks": index_tracks,
            "metrics": metrics,
            "root_states": root_states,
            "cancelled": False,
        }

    def load_cached_tracks(self, tracks: list[dict[str, Any]]) -> int:
        """Load persisted metadata without probing the underlying audio files."""
        self._tracks = [
            self._apply_override(dict(item))
            for item in list(tracks or [])
            if isinstance(item, dict)
        ]
        return len(self._tracks)

    def apply_scan_snapshot(self, snapshot: dict[str, Any]) -> int:
        """Atomically replace the live catalog with a completed scan snapshot."""
        tracks = [
            dict(item)
            for item in list((snapshot or {}).get("tracks") or [])
            if isinstance(item, dict)
        ]
        metrics = dict((snapshot or {}).get("metrics") or {})
        self._tracks = tracks
        self._last_scan_metrics = metrics
        return len(tracks)

    def scan(self) -> int:
        snapshot = self.scan_snapshot()
        return self.apply_scan_snapshot(snapshot)

    @property
    def last_scan_metrics(self) -> dict[str, object]:
        return dict(self._last_scan_metrics)

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
