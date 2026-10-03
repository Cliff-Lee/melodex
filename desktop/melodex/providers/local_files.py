from __future__ import annotations

import hashlib
import os
import queue
import threading
import time
from collections import deque
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path
from typing import Any, Callable

from ..provider import MusicProvider, ProviderInfo
from ..library_scan import ProgressThrottle, ScanCancelled, ScanControl
from ..scan_metrics import ScanProbe
from ..storage_concurrency import StorageConcurrencyController

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
        self._cached_loader: Callable[[], list[dict[str, Any]]] | None = None
        self._cached_loader_lock = threading.RLock()
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
        cached_directories: dict[str, dict[str, Any]] | None = None,
        collect_tracks: bool = True,
        checkpoint: Callable[[dict[str, Any]], None] | None = None,
    ) -> dict[str, Any]:
        """Scan roots through a bounded discovery/metadata pipeline.

        P10c separates filesystem discovery from metadata consumption with a
        fixed-size queue. Discovery may run ahead only to the queue capacity;
        once full, the producer waits for metadata/index work to catch up.

        The live catalog remains atomic. Final snapshot rows are accumulated
        until a successful scan completes, and incomplete roots roll back their
        rows before persistence.
        """
        scan_roots = [Path(x) for x in (self.roots if roots is None else roots)]
        cached = {
            self._override_key(key): dict(value)
            for key, value in dict(cached_entries or {}).items()
            if isinstance(value, dict)
        }
        cached_dirs = {
            self._override_key(key): dict(value)
            for key, value in dict(cached_directories or {}).items()
            if isinstance(value, dict)
        }
        control = control or ScanControl()
        throttle = ProgressThrottle()
        tracks: list[dict[str, Any]] = []
        index_records: list[dict[str, Any]] = []
        directory_manifests: list[dict[str, Any]] = []
        tracks_indexed = 0
        root_states: list[dict[str, Any]] = []
        probe = ScanProbe(len(scan_roots))
        seen_keys: set[str] = set()
        available_root_keys: set[str] = set()

        unchanged = 0
        added = 0
        changed = 0
        removed = 0
        stat_failures = 0

        queue_capacity = 256
        work_queue: queue.Queue[dict[str, Any]] = queue.Queue(
            maxsize=queue_capacity
        )
        producer_done = threading.Event()
        producer_error: list[BaseException] = []
        max_queue_depth = 0
        queue_backpressure_events = 0
        directory_manifest_hits = 0
        directory_manifest_misses = 0
        concurrency = StorageConcurrencyController(scan_roots)
        metadata_executor = ThreadPoolExecutor(
            max_workers=4,
            thread_name_prefix="melodex-metadata",
        )
        pending_metadata: deque[dict[str, Any]] = deque()
        max_metadata_in_flight = 0

        def emit(
            phase: str,
            *,
            force: bool = False,
            current: str = "",
            completed: int = 0,
            total: int = 0,
            root_unchanged: int = 0,
            root_added: int = 0,
            root_changed: int = 0,
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
                    "unchanged": unchanged + root_unchanged,
                    "added": added + root_added,
                    "changed": changed + root_changed,
                    "removed": removed,
                    "stat_failures": stat_failures,
                    "streaming": True,
                    "queue_depth": work_queue.qsize(),
                    "queue_capacity": queue_capacity,
                }
            )

        def put_work(item: dict[str, Any]) -> None:
            nonlocal max_queue_depth, queue_backpressure_events
            while True:
                control.checkpoint()
                try:
                    work_queue.put_nowait(item)
                    max_queue_depth = max(max_queue_depth, work_queue.qsize())
                    return
                except queue.Full:
                    queue_backpressure_events += 1
                    try:
                        work_queue.put(item, timeout=0.05)
                        max_queue_depth = max(max_queue_depth, work_queue.qsize())
                        return
                    except queue.Full:
                        continue

        def discover() -> None:
            nonlocal stat_failures
            try:
                for root in scan_roots:
                    control.checkpoint()
                    exists = root.exists()
                    probe.root_checked(exists=exists)
                    root_key = self._override_key(root)
                    put_work(
                        {
                            "type": "root_start",
                            "path": str(root),
                            "root_key": root_key,
                            "available": bool(exists),
                        }
                    )
                    if not exists:
                        put_work(
                            {
                                "type": "root_end",
                                "root_key": root_key,
                                "complete": False,
                                "walk_errors": 0,
                            }
                        )
                        continue

                    root_walk_errors = 0

                    def on_walk_error(_error: OSError) -> None:
                        nonlocal root_walk_errors
                        root_walk_errors += 1

                    try:
                        walker = os.walk(root, onerror=on_walk_error)
                    except TypeError:
                        walker = os.walk(root)

                    for base, _, files in walker:
                        control.checkpoint()
                        probe.directory_seen()
                        manifest = hashlib.sha256()
                        audio_count = 0
                        for name in sorted(files):
                            control.checkpoint()
                            p = Path(base) / name
                            is_audio = p.suffix.lower() in AUDIO_EXTS
                            probe.file_seen(audio=is_audio)
                            if not is_audio:
                                continue

                            key = self._override_key(p)
                            size: int | None = None
                            mtime_ns: int | None = None
                            stat_started = time.perf_counter()
                            try:
                                file_stat = p.stat()
                                size = int(file_stat.st_size)
                                mtime_ns = int(
                                    getattr(
                                        file_stat,
                                        "st_mtime_ns",
                                        int(
                                            float(file_stat.st_mtime)
                                            * 1_000_000_000
                                        ),
                                    )
                                )
                            except OSError:
                                stat_failures += 1
                            finally:
                                concurrency.observe_stat(
                                    time.perf_counter() - stat_started
                                )

                            audio_count += 1
                            manifest.update(
                                (
                                    name
                                    + "\0"
                                    + str(size if size is not None else "?")
                                    + "\0"
                                    + str(
                                        mtime_ns
                                        if mtime_ns is not None
                                        else "?"
                                    )
                                    + "\n"
                                ).encode("utf-8", errors="surrogatepass")
                            )

                            put_work(
                                {
                                    "type": "file",
                                    "path": p,
                                    "key": key,
                                    "size": size,
                                    "mtime_ns": mtime_ns,
                                    "root_key": root_key,
                                }
                            )

                        put_work(
                            {
                                "type": "directory_manifest",
                                "path": str(base),
                                "root_path": str(root),
                                "root_key": root_key,
                                "manifest": manifest.hexdigest(),
                                "file_count": audio_count,
                            }
                        )

                    put_work(
                        {
                            "type": "root_end",
                            "root_key": root_key,
                            "complete": root_walk_errors == 0,
                            "walk_errors": int(root_walk_errors),
                        }
                    )
            except BaseException as exc:
                producer_error.append(exc)
            finally:
                producer_done.set()

        cancelled = False
        emit("discovering", force=True)

        producer = threading.Thread(
            target=discover,
            name="melodex-library-discovery",
            daemon=True,
        )
        producer.start()

        current_root_key = ""
        current_root_state: dict[str, Any] | None = None
        current_tracks_start = 0
        current_index_records_start = 0
        current_directory_manifests_start = 0
        current_tracks_indexed_start = 0
        current_root_seen: set[str] = set()
        root_unchanged = 0
        root_added = 0
        root_changed = 0

        def read_metadata(path: Path) -> tuple[dict[str, Any], float]:
            started = time.perf_counter()
            value = self._metadata(path)
            return value, max(0.0, time.perf_counter() - started)

        def flush_one_metadata() -> None:
            nonlocal tracks_indexed, max_metadata_in_flight
            if not pending_metadata:
                return
            row = pending_metadata.popleft()
            raw_metadata = dict(row.get("raw_metadata") or {})
            future = row.get("future")
            p = Path(row["path"])
            if isinstance(future, Future):
                raw_metadata, elapsed = future.result()
                probe.record_metadata_result(elapsed)
                emit(
                    "metadata",
                    current=p.name,
                    completed=probe.metrics.metadata_attempts,
                    total=0,
                    root_unchanged=root_unchanged,
                    root_added=root_added,
                    root_changed=root_changed,
                )
            if raw_metadata:
                record = {
                    "track": dict(raw_metadata),
                    "size": row.get("size"),
                    "mtime_ns": row.get("mtime_ns"),
                }
                if bool(row.get("checkpoint")) and checkpoint is not None:
                    checkpoint(dict(record))
                index_records.append(record)
                tracks_indexed += 1
                if collect_tracks:
                    tracks.append(self._apply_override(raw_metadata))

        def drain_metadata() -> None:
            while pending_metadata:
                control.checkpoint()
                flush_one_metadata()

        try:
            while not producer_done.is_set() or not work_queue.empty():
                control.checkpoint()
                try:
                    item = work_queue.get(timeout=0.05)
                except queue.Empty:
                    if pending_metadata:
                        flush_one_metadata()
                        continue
                    if producer_error:
                        raise producer_error[0]
                    continue

                item_type = str(item.get("type") or "")
                if item_type == "root_start":
                    current_root_key = str(item.get("root_key") or "")
                    current_root_state = {
                        "path": str(item.get("path") or ""),
                        "available": bool(item.get("available")),
                        "complete": False,
                        "walk_errors": 0,
                    }
                    root_states.append(current_root_state)
                    current_tracks_start = len(tracks)
                    current_index_records_start = len(index_records)
                    current_directory_manifests_start = len(directory_manifests)
                    current_tracks_indexed_start = tracks_indexed
                    current_root_seen = set()
                    root_unchanged = 0
                    root_added = 0
                    root_changed = 0
                    continue

                if item_type == "file":
                    p = Path(item["path"])
                    key = str(item.get("key") or "")
                    current_root_seen.add(key)
                    size = item.get("size")
                    mtime_ns = item.get("mtime_ns")
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
                        and int(previous_size) == int(size)
                        and int(previous_mtime) == int(mtime_ns)
                    )

                    if reusable:
                        root_unchanged += 1
                        pending_metadata.append(
                            {
                                "path": p,
                                "size": size,
                                "mtime_ns": mtime_ns,
                                "raw_metadata": previous_track,
                            }
                        )
                    else:
                        if previous is None:
                            root_added += 1
                        else:
                            root_changed += 1
                        probe.metadata_submitted()
                        pending_metadata.append(
                            {
                                "path": p,
                                "size": size,
                                "mtime_ns": mtime_ns,
                                "future": metadata_executor.submit(
                                    read_metadata,
                                    p,
                                ),
                                "checkpoint": True,
                            }
                        )

                    decision = concurrency.decision()
                    max_metadata_in_flight = max(
                        max_metadata_in_flight,
                        sum(
                            1
                            for row in pending_metadata
                            if isinstance(row.get("future"), Future)
                        ),
                    )
                    while len(pending_metadata) >= decision.in_flight_limit:
                        control.checkpoint()
                        flush_one_metadata()

                    emit(
                        "discovering",
                        current=p.parent.name,
                        root_unchanged=root_unchanged,
                        root_added=root_added,
                        root_changed=root_changed,
                    )
                    continue

                if item_type == "directory_manifest":
                    directory_path = str(item.get("path") or "")
                    manifest_value = str(item.get("manifest") or "")
                    file_count = max(0, int(item.get("file_count") or 0))
                    previous_dir = cached_dirs.get(
                        self._override_key(directory_path)
                    )
                    if (
                        previous_dir
                        and str(previous_dir.get("manifest") or "")
                        == manifest_value
                        and int(previous_dir.get("file_count") or 0)
                        == file_count
                    ):
                        directory_manifest_hits += 1
                    else:
                        directory_manifest_misses += 1
                    directory_manifests.append(
                        {
                            "path": directory_path,
                            "root_path": str(item.get("root_path") or ""),
                            "manifest": manifest_value,
                            "file_count": file_count,
                        }
                    )
                    continue

                if item_type == "root_end":
                    drain_metadata()
                    if current_root_state is None:
                        continue
                    walk_errors = int(item.get("walk_errors") or 0)
                    complete = bool(item.get("complete"))
                    current_root_state["walk_errors"] = walk_errors
                    current_root_state["complete"] = complete
                    if complete and bool(current_root_state.get("available")):
                        unchanged += root_unchanged
                        added += root_added
                        changed += root_changed
                        available_root_keys.add(current_root_key)
                        seen_keys.update(current_root_seen)
                    else:
                        del tracks[current_tracks_start:]
                        del index_records[current_index_records_start:]
                        del directory_manifests[
                            current_directory_manifests_start:
                        ]
                        tracks_indexed = current_tracks_indexed_start
                    current_root_state = None
                    current_root_key = ""
                    current_root_seen = set()
                    root_unchanged = root_added = root_changed = 0

            if producer_error:
                raise producer_error[0]

            for key, previous in cached.items():
                if key in seen_keys:
                    continue
                root_path = str(previous.get("root_path") or "")
                if (
                    root_path
                    and self._override_key(root_path) in available_root_keys
                ):
                    removed += 1

            emit(
                "metadata",
                force=True,
                completed=probe.metrics.metadata_attempts,
                total=probe.metrics.metadata_attempts,
            )
        except ScanCancelled:
            cancelled = True
        finally:
            if cancelled:
                control.cancel()
            producer.join(timeout=1.0)
            metadata_executor.shutdown(
                wait=not cancelled,
                cancel_futures=cancelled,
            )
            final_concurrency = concurrency.decision()
            metrics = probe.finish(
                tracks_indexed=0 if cancelled else tracks_indexed
            )
            metrics.update(
                {
                    "unchanged_files": int(unchanged),
                    "added_files": int(added),
                    "changed_files": int(changed),
                    "removed_files": int(removed),
                    "stat_failures": int(stat_failures),
                    "metadata_reused": int(unchanged),
                    "streaming_discovery": True,
                    "discovery_buffer_rows": 0,
                    "bounded_pipeline": True,
                    "collect_tracks": bool(collect_tracks),
                    "snapshot_track_copies": 2 if collect_tracks else 1,
                    "directory_manifest_hits": int(directory_manifest_hits),
                    "directory_manifest_misses": int(directory_manifest_misses),
                    "directory_manifests": len(directory_manifests),
                    "storage_profile": final_concurrency.profile,
                    "storage_average_stat_ms": final_concurrency.average_stat_ms,
                    "storage_network_hint": final_concurrency.network_hint,
                    "metadata_worker_limit": final_concurrency.metadata_workers,
                    "metadata_in_flight_limit": final_concurrency.in_flight_limit,
                    "metadata_max_in_flight": int(max_metadata_in_flight),
                    "pipeline_queue_capacity": int(queue_capacity),
                    "pipeline_max_queue_depth": int(max_queue_depth),
                    "pipeline_backpressure_events": int(
                        queue_backpressure_events
                    ),
                    "incomplete_roots": sum(
                        1
                        for state in root_states
                        if bool(state.get("available"))
                        and not bool(state.get("complete", True))
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
                "index_records": [],
                "directory_manifests": [],
                "metrics": metrics,
                "root_states": root_states,
                "cancelled": True,
            }

        emit(
            "complete",
            force=True,
            completed=tracks_indexed,
            total=tracks_indexed,
        )
        return {
            "tracks": tracks,
            "index_records": index_records,
            "directory_manifests": directory_manifests,
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

    def set_cached_loader(
        self,
        loader: Callable[[], list[dict[str, Any]]] | None,
    ) -> None:
        """Install a one-shot metadata loader without touching audio paths.

        Used at process startup so a large cached library can stay on disk until
        a feature actually needs the full catalog.
        """
        with self._cached_loader_lock:
            self._cached_loader = loader

    def _ensure_cached_loaded(self) -> None:
        loader = self._cached_loader
        if loader is None:
            return
        with self._cached_loader_lock:
            loader = self._cached_loader
            if loader is None:
                return
            # Clear before invoking so failures cannot recursively re-enter.
            self._cached_loader = None
            tracks = loader()
            self._tracks = self.prepare_cached_tracks(tracks)
            self._catalog_revision += 1

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
        with self._cached_loader_lock:
            self._cached_loader = None
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
        with self._cached_loader_lock:
            self._cached_loader = None
        self._tracks = tracks
        self._catalog_revision += 1
        self._last_scan_metrics = metrics
        return len(tracks)

    def scan(self) -> int:
        snapshot = self.scan_snapshot()
        return self.apply_scan_snapshot(snapshot)

    @property
    def catalog_loaded(self) -> bool:
        return self._cached_loader is None

    @property
    def catalog_revision(self) -> int:
        self._ensure_cached_loaded()
        return int(self._catalog_revision)

    @property
    def last_scan_metrics(self) -> dict[str, object]:
        return dict(self._last_scan_metrics)

    def search(self, query: str, limit: int = 50) -> list[dict[str, Any]]:
        self._ensure_cached_loaded()
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
        self._ensure_cached_loaded()
        return [dict(x) for x in self._tracks[:limit]]

    def resolve(self, track: dict[str, Any]) -> dict[str, Any]:
        if track.get("local_path"):
            return dict(track)
        self._ensure_cached_loaded()
        tid = str(track.get("track_id") or "")
        for item in self._tracks:
            if str(item.get("track_id") or "") == tid:
                return dict(item)
        raise RuntimeError("Local track is no longer in the indexed folders")

    @property
    def tracks(self) -> list[dict[str, Any]]:
        self._ensure_cached_loaded()
        return [dict(x) for x in self._tracks]
