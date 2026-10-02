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
        self._catalog_revision = 0
        self._last_scan_metrics: dict[str, object] = {}
        if self.roots and scan_on_init:
            self.scan()

    @staticmethod
    def _override_key(path: str | Path) -> str:
        # Keep override lookup purely lexical. Resolving thousands of cached
        # NAS paths at startup would touch the network and defeat instant load.
        return os.path.normcase(
            os.path.abspath(
                os.path.expanduser(str(path))
            )
        )

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
                self._catalog_revision += 1
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
        absolute_path = os.path.abspath(os.path.expanduser(str(path)))
        out = {
            "provider_id": "local",
            "track_id": absolute_path,
            "rel": f"local:{absolute_path}",
            "title": title,
            "artist": artist or "Unknown artist",
            "album": album,
            "duration": duration,
            "local_path": absolute_path,
            "source": "local",
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
        cached_entries: dict[str, dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Scan roots, reusing cached tags for files whose fingerprint is unchanged.

        The cheap fingerprint is file size + nanosecond modification time. A
        cache entry without a complete fingerprint is deliberately treated as
        changed, so the first rescan after upgrading populates trustworthy
        fingerprints for future incremental scans.
        """
        scan_roots = [Path(x) for x in (self.roots if roots is None else roots)]
        overrides = {
            str(key): dict(value)
            for key, value in self.overrides.items()
            if isinstance(value, dict)
        }
        cached = {
            self._override_key(key): dict(value)
            for key, value in dict(cached_entries or {}).items()
            if isinstance(value, dict)
        }
        control = control or ScanControl()
        throttle = ProgressThrottle()
        discovered: list[dict[str, Any]] = []
        tracks: list[dict[str, Any]] = []
        index_tracks: list[dict[str, Any]] = []
        index_records: list[dict[str, Any]] = []
        root_states: list[dict[str, Any]] = []
        probe = ScanProbe(len(scan_roots))
        seen_keys: set[str] = set()
        available_root_keys: set[str] = set()

        unchanged = 0
        added = 0
        changed = 0
        removed = 0
        stat_failures = 0

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
                    "current": Path(current).name if current else "",
                    "paused": control.paused,
                    "cancelled": control.cancelled,
                    "unchanged": unchanged,
                    "added": added,
                    "changed": changed,
                    "removed": removed,
                    "stat_failures": stat_failures,
                }
            )

        cancelled = False
        emit("discovering", force=True)
        try:
            for root in scan_roots:
                control.checkpoint()
                exists = root.exists()
                probe.root_checked(exists=exists)
                root_state = {
                    "path": str(root),
                    "available": bool(exists),
                    "complete": False,
                    "walk_errors": 0,
                }
                root_states.append(root_state)
                if not exists:
                    continue

                root_key = self._override_key(root)
                root_start = len(discovered)
                root_seen: set[str] = set()
                root_walk_errors = 0

                def on_walk_error(_error: OSError) -> None:
                    nonlocal root_walk_errors
                    root_walk_errors += 1

                try:
                    walker = os.walk(root, onerror=on_walk_error)
                except TypeError:
                    # Keeps simple monkeypatched walkers in unit tests working;
                    # the real os.walk supports onerror.
                    walker = os.walk(root)

                for base, _, files in walker:
                    control.checkpoint()
                    probe.directory_seen()
                    for name in files:
                        control.checkpoint()
                        p = Path(base) / name
                        is_audio = p.suffix.lower() in AUDIO_EXTS
                        probe.file_seen(audio=is_audio)
                        if not is_audio:
                            emit("discovering", current=Path(base).name)
                            continue

                        key = self._override_key(p)
                        root_seen.add(key)
                        size: int | None = None
                        mtime_ns: int | None = None
                        try:
                            file_stat = p.stat()
                            size = int(file_stat.st_size)
                            mtime_ns = int(
                                getattr(
                                    file_stat,
                                    "st_mtime_ns",
                                    int(float(file_stat.st_mtime) * 1_000_000_000),
                                )
                            )
                        except OSError:
                            stat_failures += 1

                        previous = cached.get(key)
                        previous_size = (
                            previous.get("size")
                            if isinstance(previous, dict)
                            else None
                        )
                        previous_mtime = (
                            previous.get("mtime_ns")
                            if isinstance(previous, dict)
                            else None
                        )
                        previous_track = (
                            dict(previous.get("track") or {})
                            if isinstance(previous, dict)
                            else {}
                        )
                        reusable = bool(
                            previous_track
                            and size is not None
                            and mtime_ns is not None
                            and previous_size is not None
                            and previous_mtime is not None
                            and int(previous_size) == size
                            and int(previous_mtime) == mtime_ns
                        )

                        if reusable:
                            kind = "unchanged"
                            unchanged += 1
                        elif previous is None:
                            kind = "added"
                            added += 1
                        else:
                            kind = "changed"
                            changed += 1

                        discovered.append(
                            {
                                "path": p,
                                "key": key,
                                "size": size,
                                "mtime_ns": mtime_ns,
                                "kind": kind,
                                "root_key": root_key,
                                "raw_track": previous_track if reusable else {},
                            }
                        )
                        emit("discovering", current=Path(base).name)

                root_state["walk_errors"] = int(root_walk_errors)
                root_state["complete"] = root_walk_errors == 0
                if root_walk_errors:
                    # Never apply a partial root. Undo its discovery/change
                    # counters and preserve the root's previous SQLite snapshot.
                    partial_rows = discovered[root_start:]
                    for row in partial_rows:
                        kind = str(row.get("kind") or "")
                        if kind == "unchanged":
                            unchanged = max(0, unchanged - 1)
                        elif kind == "added":
                            added = max(0, added - 1)
                        elif kind == "changed":
                            changed = max(0, changed - 1)
                    del discovered[root_start:]
                    continue

                available_root_keys.add(root_key)
                seen_keys.update(root_seen)

            # A cached file is considered removed only when its root was
            # positively available and fully enumerated in this scan.
            for key, previous in cached.items():
                if key in seen_keys:
                    continue
                root_path = str(previous.get("root_path") or "")
                if root_path and self._override_key(root_path) in available_root_keys:
                    removed += 1

            pending = [
                row for row in discovered
                if not dict(row.get("raw_track") or {})
            ]
            emit(
                "metadata",
                force=True,
                completed=0,
                total=len(pending),
            )
            for index, row in enumerate(pending, start=1):
                control.checkpoint()
                p = Path(row["path"])
                with probe.metadata_read():
                    row["raw_track"] = self._metadata(p)
                emit(
                    "metadata",
                    current=p.name,
                    completed=index,
                    total=len(pending),
                )

            # Build one complete snapshot in discovery order. Cached metadata is
            # raw file metadata; Melodex-only corrections are applied separately.
            for row in discovered:
                raw_metadata = dict(row.get("raw_track") or {})
                if not raw_metadata:
                    continue
                index_tracks.append(dict(raw_metadata))
                index_records.append(
                    {
                        "track": dict(raw_metadata),
                        "size": row.get("size"),
                        "mtime_ns": row.get("mtime_ns"),
                    }
                )
                tracks.append(self._apply_override(raw_metadata))
        except ScanCancelled:
            cancelled = True
        finally:
            metrics = probe.finish(tracks_indexed=len(tracks))
            metrics.update(
                {
                    "unchanged_files": int(unchanged),
                    "added_files": int(added),
                    "changed_files": int(changed),
                    "removed_files": int(removed),
                    "stat_failures": int(stat_failures),
                    "metadata_reused": int(unchanged),
                    "incomplete_roots": sum(
                        1
                        for state in root_states
                        if bool(state.get("available")) and not bool(state.get("complete", True))
                    ),
                }
            )

        if cancelled:
            emit(
                "cancelled",
                force=True,
                completed=probe.metrics.metadata_attempts,
                total=max(0, added + changed),
            )
            return {
                "tracks": [],
                "index_tracks": [],
                "index_records": [],
                "metrics": metrics,
                "root_states": root_states,
                "cancelled": True,
            }

        emit(
            "complete",
            force=True,
            completed=len(tracks),
            total=len(tracks),
        )
        return {
            "tracks": tracks,
            "index_tracks": index_tracks,
            "index_records": index_records,
            "metrics": metrics,
            "root_states": root_states,
            "changes": {
                "unchanged": int(unchanged),
                "added": int(added),
                "changed": int(changed),
                "removed": int(removed),
                "metadata_reads": int(probe.metrics.metadata_attempts),
                "stat_failures": int(stat_failures),
                "incomplete_roots": sum(
                    1
                    for state in root_states
                    if bool(state.get("available"))
                    and not bool(state.get("complete", True))
                ),
            },
            "cancelled": False,
        }

    def prepare_cached_tracks(
        self,
        tracks: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Apply Melodex-only corrections without probing any audio path."""
        return [
            self._apply_override(dict(item))
            for item in list(tracks or [])
            if isinstance(item, dict)
        ]

    def load_cached_tracks(self, tracks: list[dict[str, Any]]) -> int:
        """Load persisted metadata without probing the underlying audio files."""
        self._tracks = self.prepare_cached_tracks(tracks)
        self._catalog_revision += 1
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
        self._catalog_revision += 1
        self._last_scan_metrics = metrics
        return len(tracks)

    def scan(self) -> int:
        snapshot = self.scan_snapshot()
        return self.apply_scan_snapshot(snapshot)

    @property
    def catalog_revision(self) -> int:
        return int(self._catalog_revision)

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
