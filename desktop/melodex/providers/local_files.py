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
_ORIGINAL_OS_WALK = os.walk
_NAS_IO_RETRY_DELAYS = (0.05, 0.15)
FIRST_PLAYABLE_TARGET = 20
FIRST_MUSIC_BREADTH_DIRECTORY_LIMIT = 512
FIRST_MUSIC_BREADTH_FRONTIER_LIMIT = 512


def _retry_oserror(
    callback: Callable[[], Any],
    *,
    on_retry: Callable[[OSError], None] | None = None,
) -> Any:
    """Retry brief filesystem hiccups without hiding persistent failures.

    SMB/NFS mounts can transiently fail an otherwise healthy directory or stat
    operation. Two short retries are cheap on local storage, avoid hammering a
    struggling NAS, and still let the isolated scan worker fail fast enough for
    bounded cancellation if the share is genuinely unavailable.
    """
    for delay in (*_NAS_IO_RETRY_DELAYS, None):
        try:
            return callback()
        except OSError as exc:
            if delay is None:
                raise
            if on_retry is not None:
                on_retry(exc)
            time.sleep(delay)
    raise RuntimeError("unreachable NAS retry state")


def _scandir_walk(
    root: Path,
    *,
    onerror: Callable[[OSError | None, int], None] | None = None,
    control: ScanControl | None = None,
    first_playable_target: int = FIRST_PLAYABLE_TARGET,
    breadth_directory_limit: int = FIRST_MUSIC_BREADTH_DIRECTORY_LIMIT,
    breadth_frontier_limit: int = FIRST_MUSIC_BREADTH_FRONTIER_LIMIT,
):
    """Yield directory batches with a bounded breadth-first first-music pass.

    Production uses scandir to avoid constructing a Path and issuing a separate
    Path.stat call for every discovered file. If os.walk has been monkeypatched
    (tests/custom probes), callers deliberately fall back to that walker.

    The initial breadth-first pass ends after the first playable target, the
    directory budget, or the bounded frontier is exhausted. Remaining work is
    handed to the existing depth-first traversal so a large hierarchy does not
    leave an unbounded breadth-first queue behind.
    """
    frontier = deque([Path(root)])
    stack: list[Path] = []
    priority_frontier: deque[Path] = deque()
    visited_directories: set[str] = set()
    root_key = os.path.normcase(os.path.abspath(str(root)))
    breadth_directories = 0
    breadth_audio_files = 0
    first_playable_target = max(1, int(first_playable_target))
    breadth_directory_limit = max(1, int(breadth_directory_limit))
    breadth_frontier_limit = max(1, int(breadth_frontier_limit))
    breadth_complete = False
    while frontier or stack:
        if control is not None:
            requested = control.take_priority_path(root)
            if requested:
                candidate = os.path.normcase(os.path.abspath(requested))
                try:
                    inside_root = os.path.commonpath((root_key, candidate)) == root_key
                except ValueError:
                    inside_root = False
                if inside_root and candidate not in visited_directories:
                    priority_frontier.appendleft(Path(requested))
        if priority_frontier:
            base = priority_frontier.popleft()
            base_key = os.path.normcase(os.path.abspath(str(base)))
            if base_key in visited_directories:
                continue
            visited_directories.add(base_key)
            breadth_pass = False
            priority_pass = True
        elif (
            not breadth_complete
            and breadth_audio_files < first_playable_target
            and breadth_directories < breadth_directory_limit
            and frontier
        ):
            base = frontier.popleft()
            base_key = os.path.normcase(os.path.abspath(str(base)))
            if base_key in visited_directories:
                continue
            visited_directories.add(base_key)
            breadth_directories += 1
            breadth_pass = True
            priority_pass = False
        else:
            breadth_complete = True
            # Preserve queued breadth-first directories, then continue with the
            # scanner's ordinary depth-first work order.
            if frontier:
                stack.extend(reversed(frontier))
                frontier.clear()
            if not stack:
                break
            base = stack.pop()
            base_key = os.path.normcase(os.path.abspath(str(base)))
            if base_key in visited_directories:
                continue
            visited_directories.add(base_key)
            breadth_pass = False
            priority_pass = False
        retries = 0

        def retried(_error: OSError) -> None:
            nonlocal retries
            retries += 1

        try:
            def read_entries():
                with os.scandir(base) as iterator:
                    return sorted(iterator, key=lambda entry: entry.name)

            entries = _retry_oserror(read_entries, on_retry=retried)
            if retries and onerror is not None:
                onerror(None, retries)
        except OSError as exc:
            if onerror is not None:
                onerror(exc, retries)
            continue

        directories: list[Path] = []
        files: list[tuple[str, os.stat_result | None, float | None]] = []
        for entry in entries:
            entry_retries = 0

            def entry_retried(_error: OSError) -> None:
                nonlocal entry_retries
                entry_retries += 1

            try:
                is_directory = _retry_oserror(
                    lambda: entry.is_dir(follow_symlinks=False),
                    on_retry=entry_retried,
                )
                if is_directory:
                    directories.append(Path(entry.path))
                    if entry_retries and onerror is not None:
                        onerror(None, entry_retries)
                    continue
            except OSError as exc:
                if onerror is not None:
                    onerror(exc, entry_retries)
                continue

            if entry_retries and onerror is not None:
                onerror(None, entry_retries)

            # Avoid an unnecessary network round trip for every non-audio file.
            # Album folders often contain artwork, cue sheets and text files;
            # only audio fingerprints participate in the scan/index contract.
            if Path(entry.name).suffix.lower() not in AUDIO_EXTS:
                files.append((entry.name, None, None))
                continue

            stat_result = None
            stat_elapsed: float | None = None
            stat_retries = 0

            def stat_retried(_error: OSError) -> None:
                nonlocal stat_retries
                stat_retries += 1

            started = time.perf_counter()
            try:
                stat_result = _retry_oserror(
                    entry.stat,
                    on_retry=stat_retried,
                )
                if stat_retries and onerror is not None:
                    onerror(None, stat_retries)
            except OSError as exc:
                if onerror is not None:
                    onerror(exc, stat_retries)
            finally:
                stat_elapsed = max(0.0, time.perf_counter() - started)
            files.append((entry.name, stat_result, stat_elapsed))

        if priority_pass:
            # A user-requested subtree takes precedence over the background
            # queue. Keep its descendants in the same priority lane.
            breadth_audio_files += sum(
                1
                for name, _stat, _elapsed in files
                if Path(name).suffix.lower() in AUDIO_EXTS
            )
            for directory in reversed(directories):
                priority_frontier.appendleft(directory)
        elif breadth_pass:
            audio_in_directory = sum(
                1
                for name, _stat, _elapsed in files
                if Path(name).suffix.lower() in AUDIO_EXTS
            )
            breadth_audio_files += audio_in_directory
            room = max(0, breadth_frontier_limit - len(frontier))
            frontier.extend(directories[:room])
            overflow = directories[room:]
            # Keep the breadth-first frontier bounded. Overflow becomes the
            # tail of the normal depth-first continuation after this pass.
            stack.extend(reversed(overflow))
        else:
            # Reverse sorted children so popping visits them lexically.
            stack.extend(reversed(directories))
        yield str(base), files


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
        self._source_availability: dict[str, str] = {}
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
        new_roots = [Path(x) for x in roots]
        old_keys = tuple(self._root_key(root) for root in self.roots)
        new_keys = tuple(self._root_key(root) for root in new_roots)
        if old_keys != new_keys and self._tracks:
            retained = [
                track
                for track in self._tracks
                if self._path_is_under_roots(
                    str(track.get("local_path") or track.get("track_id") or ""),
                    new_roots,
                )
            ]
            if len(retained) != len(self._tracks):
                self._tracks = retained
                self._catalog_revision += 1
        self.roots = new_roots

    @staticmethod
    def _root_key(root: str | Path) -> str:
        return os.path.normcase(
            os.path.abspath(os.path.expanduser(str(root)))
        )

    @classmethod
    def _path_is_under_roots(cls, path: str, roots: list[Path]) -> bool:
        if not path:
            return False
        candidate = cls._root_key(path)
        return any(
            candidate == root or candidate.startswith(root.rstrip(os.sep) + os.sep)
            for root in (cls._root_key(item) for item in roots)
        )

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
        cache_keys_canonical: bool = False,
        collect_tracks: bool = True,
        checkpoint: Callable[[dict[str, Any]], None] | None = None,
        on_first_audio_file: Callable[[dict[str, Any]], None] | None = None,
        on_track_ready: Callable[[dict[str, Any]], None] | None = None,
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
        raw_cached = {
            str(key): dict(value)
            for key, value in dict(cached_entries or {}).items()
            if isinstance(value, dict)
        }
        raw_cached_dirs = {
            str(key): dict(value)
            for key, value in dict(cached_directories or {}).items()
            if isinstance(value, dict)
        }
        cache_key_normalizations = 0
        if cache_keys_canonical:
            # LocalLibraryIndex guarantees canonical absolute keys. Production
            # callers can therefore avoid normalising every indexed path again
            # before traversal begins.
            cached = raw_cached
            cached_dirs = raw_cached_dirs
        else:
            cached = {}
            for key, value in raw_cached.items():
                cached[self._override_key(key)] = value
                cache_key_normalizations += 1
            cached_dirs = {}
            for key, value in raw_cached_dirs.items():
                cached_dirs[self._override_key(key)] = value
                cache_key_normalizations += 1
        control = control or ScanControl()
        throttle = ProgressThrottle()
        tracks: list[dict[str, Any]] = []
        index_records: list[dict[str, Any]] = []
        directory_manifests: list[dict[str, Any]] = []
        preserve_directories: list[dict[str, Any]] = []
        tracks_indexed = 0
        root_states: list[dict[str, Any]] = []
        probe = ScanProbe(len(scan_roots))
        seen_keys: set[str] = set()
        preserved_directory_keys: set[str] = set()
        available_root_keys: set[str] = set()

        unchanged = 0
        resumed = 0
        added = 0
        changed = 0
        removed = 0
        stat_failures = 0
        cached_root_normalizations = 0
        cached_root_keys: dict[str, str] = {}

        queue_capacity = 256
        work_queue: queue.Queue[dict[str, Any]] = queue.Queue(
            maxsize=queue_capacity
        )
        producer_done = threading.Event()
        producer_error: list[BaseException] = []
        provisional_audio_files_emitted = 0
        max_queue_depth = 0
        queue_backpressure_events = 0
        directory_manifest_hits = 0
        directory_manifest_misses = 0
        directory_reuse_hits = 0
        directory_reuse_tracks = 0
        file_work_items_materialized = 0
        directory_reuse_materializations_avoided = 0
        scandir_directories = 0
        concurrency = StorageConcurrencyController(scan_roots)
        metadata_executor = ThreadPoolExecutor(
            # P14l lets fast local storage use the full existing eight-job
            # in-flight budget. The adaptive controller still starts at two
            # workers and keeps likely network storage conservative.
            max_workers=8,
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
            root_resumed: int = 0,
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
                    "resumed": resumed + root_resumed,
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
            nonlocal provisional_audio_files_emitted
            nonlocal stat_failures
            nonlocal file_work_items_materialized
            nonlocal directory_reuse_materializations_avoided
            try:
                for root in scan_roots:
                    control.checkpoint()
                    root_io_retries = 0

                    def root_retried(_error: OSError) -> None:
                        nonlocal root_io_retries
                        root_io_retries += 1

                    try:
                        _retry_oserror(root.stat, on_retry=root_retried)
                        exists = True
                    except OSError:
                        exists = False
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
                                "io_retries": int(root_io_retries),
                            }
                        )
                        continue

                    root_walk_errors = 0

                    def on_walk_error(
                        error: OSError | None,
                        retries: int = 0,
                    ) -> None:
                        nonlocal root_walk_errors, root_io_retries
                        root_io_retries += max(0, int(retries))
                        if error is not None:
                            root_walk_errors += 1

                    if os.walk is _ORIGINAL_OS_WALK:
                        walker = _scandir_walk(
                            root,
                            onerror=on_walk_error,
                            control=control,
                        )
                        fast_scandir = True
                    else:
                        try:
                            legacy = os.walk(root, onerror=on_walk_error)
                        except TypeError:
                            legacy = os.walk(root)
                        walker = (
                            (base, [(name, None, None) for name in files])
                            for base, _, files in legacy
                        )
                        fast_scandir = False

                    for base, files in walker:
                        control.checkpoint()
                        probe.directory_seen()
                        if probe.metrics.directories_seen == 1:
                            emit("discovering", force=True, current=Path(base).name)
                        manifest = hashlib.sha256()
                        audio_count = 0
                        directory_key = self._override_key(base)
                        previous_dir = cached_dirs.get(directory_key)
                        reuse_candidate = previous_dir is not None
                        file_work: list[
                            tuple[str, int | None, int | None]
                        ] = []

                        def materialize_file_work(
                            name: str,
                            size: int | None,
                            mtime_ns: int | None,
                        ) -> dict[str, Any]:
                            nonlocal file_work_items_materialized
                            path = Path(base) / name
                            file_work_items_materialized += 1
                            return {
                                "type": "file",
                                "path": path,
                                "key": self._override_key(path),
                                "size": size,
                                "mtime_ns": mtime_ns,
                                "root_key": root_key,
                            }

                        for name, direntry_stat, direntry_stat_elapsed in files:
                            control.checkpoint()
                            is_audio = Path(name).suffix.lower() in AUDIO_EXTS
                            probe.file_seen(audio=is_audio)
                            if is_audio and probe.metrics.audio_files_seen == 1:
                                emit("discovering", force=True, current=Path(base).name)
                            if (
                                is_audio
                                and on_first_audio_file is not None
                                and provisional_audio_files_emitted
                                < FIRST_PLAYABLE_TARGET
                            ):
                                provisional_audio_files_emitted += 1
                                provisional_path = Path(base) / name
                                absolute_path = os.path.abspath(
                                    os.path.expanduser(str(provisional_path))
                                )
                                try:
                                    on_first_audio_file(
                                        {
                                            "provider_id": "local",
                                            "track_id": absolute_path,
                                            "rel": f"local:{absolute_path}",
                                            "title": provisional_path.stem,
                                            "artist": "Unknown artist",
                                            "album": "",
                                            "duration": 0.0,
                                            "local_path": absolute_path,
                                            "source": "local",
                                            "provisional": True,
                                        }
                                    )
                                except Exception:
                                    # Early playback is opportunistic. A UI or
                                    # IPC callback failure must not fail indexing.
                                    pass
                            if not is_audio:
                                continue

                            path: Path | None = None
                            size: int | None = None
                            mtime_ns: int | None = None
                            stat_started = time.perf_counter()
                            try:
                                if fast_scandir and direntry_stat is None:
                                    # scandir already exhausted the bounded retry
                                    # budget and marked this root incomplete.
                                    stat_failures += 1
                                    continue
                                if direntry_stat is not None:
                                    file_stat = direntry_stat
                                else:
                                    legacy_retries = 0

                                    def legacy_stat_retried(_error: OSError) -> None:
                                        nonlocal legacy_retries
                                        legacy_retries += 1

                                    path = Path(base) / name
                                    file_stat = _retry_oserror(
                                        path.stat,
                                        on_retry=legacy_stat_retried,
                                    )
                                    if legacy_retries:
                                        on_walk_error(None, legacy_retries)
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
                                # Custom/monkeypatched os.walk probes historically
                                # allow virtual files with no real stat result.
                                # Production NAS traversal uses scandir, where an
                                # exhausted stat failure has already marked the
                                # root incomplete before this consumer sees it.
                                stat_failures += 1
                            finally:
                                measured_stat = (
                                    direntry_stat_elapsed
                                    if direntry_stat_elapsed is not None
                                    else time.perf_counter() - stat_started
                                )
                                concurrency.observe_stat(measured_stat)

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
                            if reuse_candidate:
                                file_work.append((name, size, mtime_ns))
                                if len(file_work) > 5000:
                                    for buffered_name, buffered_size, buffered_mtime in file_work:
                                        put_work(
                                            materialize_file_work(
                                                buffered_name,
                                                buffered_size,
                                                buffered_mtime,
                                            )
                                        )
                                    file_work.clear()
                                    reuse_candidate = False
                            else:
                                put_work(
                                    materialize_file_work(
                                        name,
                                        size,
                                        mtime_ns,
                                    )
                                )

                        manifest_value = manifest.hexdigest()
                        reusable_directory = bool(
                            reuse_candidate
                            and previous_dir
                            and str(previous_dir.get("manifest") or "")
                            == manifest_value
                            and int(previous_dir.get("file_count") or 0)
                            == audio_count
                        )

                        if reusable_directory:
                            directory_reuse_materializations_avoided += audio_count
                            put_work(
                                {
                                    "type": "directory_reuse",
                                    "path": str(base),
                                    "root_path": str(root),
                                    "root_key": root_key,
                                    "manifest": manifest_value,
                                    "file_count": audio_count,
                                    "fast_scandir": fast_scandir,
                                }
                            )
                        else:
                            if reuse_candidate:
                                for buffered_name, buffered_size, buffered_mtime in file_work:
                                    put_work(
                                        materialize_file_work(
                                            buffered_name,
                                            buffered_size,
                                            buffered_mtime,
                                        )
                                    )
                            put_work(
                                {
                                    "type": "directory_manifest",
                                    "path": str(base),
                                    "root_path": str(root),
                                    "root_key": root_key,
                                    "manifest": manifest_value,
                                    "file_count": audio_count,
                                    "fast_scandir": fast_scandir,
                                }
                            )

                    put_work(
                        {
                            "type": "root_end",
                            "root_key": root_key,
                            "complete": root_walk_errors == 0,
                            "walk_errors": int(root_walk_errors),
                            "io_retries": int(root_io_retries),
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
        current_preserve_directories_start = 0
        current_tracks_indexed_start = 0
        current_root_seen: set[str] = set()
        current_root_preserved_dirs: set[str] = set()
        root_unchanged = 0
        root_resumed = 0
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
                prepared_track = self._apply_override(raw_metadata)
                if collect_tracks:
                    tracks.append(prepared_track)
                if on_track_ready is not None:
                    try:
                        on_track_ready(dict(prepared_track))
                    except Exception:
                        # Progressive UI updates must not fail the durable scan.
                        pass

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
                        "io_retries": 0,
                    }
                    root_states.append(current_root_state)
                    current_tracks_start = len(tracks)
                    current_index_records_start = len(index_records)
                    current_directory_manifests_start = len(directory_manifests)
                    current_preserve_directories_start = len(preserve_directories)
                    current_tracks_indexed_start = tracks_indexed
                    current_root_seen = set()
                    current_root_preserved_dirs = set()
                    root_unchanged = 0
                    root_resumed = 0
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
                        if bool(previous.get("resume_staged")):
                            root_resumed += 1
                        else:
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
                        root_resumed=root_resumed,
                        root_added=root_added,
                        root_changed=root_changed,
                    )
                    continue

                if item_type == "directory_reuse":
                    directory_path = str(item.get("path") or "")
                    manifest_value = str(item.get("manifest") or "")
                    file_count = max(0, int(item.get("file_count") or 0))
                    if bool(item.get("fast_scandir")):
                        scandir_directories += 1
                    directory_manifest_hits += 1
                    directory_reuse_hits += 1
                    directory_reuse_tracks += file_count
                    root_unchanged += file_count
                    tracks_indexed += file_count
                    canonical_dir = self._override_key(directory_path)
                    current_root_preserved_dirs.add(canonical_dir)
                    preserve_directories.append(
                        {
                            "path": directory_path,
                            "root_path": str(item.get("root_path") or ""),
                            "file_count": file_count,
                        }
                    )
                    directory_manifests.append(
                        {
                            "path": directory_path,
                            "root_path": str(item.get("root_path") or ""),
                            "manifest": manifest_value,
                            "file_count": file_count,
                        }
                    )
                    continue

                if item_type == "directory_manifest":
                    if bool(item.get("fast_scandir")):
                        scandir_directories += 1
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
                    io_retries = int(item.get("io_retries") or 0)
                    complete = bool(item.get("complete"))
                    current_root_state["walk_errors"] = walk_errors
                    current_root_state["io_retries"] = io_retries
                    current_root_state["complete"] = complete
                    if complete and bool(current_root_state.get("available")):
                        unchanged += root_unchanged
                        resumed += root_resumed
                        added += root_added
                        changed += root_changed
                        available_root_keys.add(current_root_key)
                        seen_keys.update(current_root_seen)
                        preserved_directory_keys.update(
                            current_root_preserved_dirs
                        )
                    else:
                        del tracks[current_tracks_start:]
                        del index_records[current_index_records_start:]
                        del directory_manifests[
                            current_directory_manifests_start:
                        ]
                        del preserve_directories[
                            current_preserve_directories_start:
                        ]
                        tracks_indexed = current_tracks_indexed_start
                    current_root_state = None
                    current_root_key = ""
                    current_root_seen = set()
                    current_root_preserved_dirs = set()
                    root_unchanged = root_resumed = root_added = root_changed = 0

            if producer_error:
                raise producer_error[0]

            for key, previous in cached.items():
                if key in seen_keys:
                    continue
                parent_key = os.path.dirname(key)
                if not cache_keys_canonical:
                    parent_key = self._override_key(parent_key)
                if parent_key in preserved_directory_keys:
                    continue
                root_path = str(previous.get("root_path") or "")
                if root_path:
                    canonical_root = cached_root_keys.get(root_path)
                    if canonical_root is None:
                        canonical_root = self._override_key(root_path)
                        cached_root_keys[root_path] = canonical_root
                        cached_root_normalizations += 1
                    if canonical_root in available_root_keys:
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
                    "resumed_files": int(resumed),
                    "added_files": int(added),
                    "changed_files": int(changed),
                    "removed_files": int(removed),
                    "stat_failures": int(stat_failures),
                    "metadata_reused": int(unchanged + resumed),
                    "streaming_discovery": True,
                    "discovery_buffer_rows": 0,
                    "bounded_pipeline": True,
                    "collect_tracks": bool(collect_tracks),
                    "snapshot_track_copies": 2 if collect_tracks else 1,
                    "cache_keys_canonical": bool(cache_keys_canonical),
                    "cache_key_normalizations": int(cache_key_normalizations),
                    "cached_root_normalizations": int(
                        cached_root_normalizations
                    ),
                    "directory_manifest_hits": int(directory_manifest_hits),
                    "directory_manifest_misses": int(directory_manifest_misses),
                    "directory_reuse_hits": int(directory_reuse_hits),
                    "directory_reuse_tracks": int(directory_reuse_tracks),
                    "file_work_items_materialized": int(
                        file_work_items_materialized
                    ),
                    "directory_reuse_materializations_avoided": int(
                        directory_reuse_materializations_avoided
                    ),
                    "directory_manifests": len(directory_manifests),
                    "scandir_directories": int(scandir_directories),
                    "scandir_enabled": bool(scandir_directories),
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
                    "io_retries": sum(
                        int(state.get("io_retries") or 0)
                        for state in root_states
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
                "preserve_directories": [],
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
            "preserve_directories": preserve_directories,
            "metrics": metrics,
            "root_states": root_states,
            "changes": {
                "unchanged": int(unchanged),
                "resumed": int(resumed),
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
            self._apply_source_availability(
                self._tracks, self._source_availability
            )
            self._catalog_revision += 1

    def prepare_cached_tracks(
        self,
        tracks: list[dict[str, Any]],
        *,
        source_availability: dict[str, str] | None = None,
    ) -> list[dict[str, Any]]:
        """Apply Melodex-only corrections without probing any audio path."""
        prepared = [
            self._apply_override(dict(item))
            for item in list(tracks or [])
            if isinstance(item, dict)
        ]
        self._apply_source_availability(
            prepared,
            self._source_availability
            if source_availability is None
            else source_availability,
        )
        return prepared

    def load_cached_tracks(
        self, tracks: list[dict[str, Any]], *, prepared: bool = False
    ) -> int:
        """Load persisted metadata without probing the underlying audio files."""
        with self._cached_loader_lock:
            self._cached_loader = None
        self._tracks = (
            tracks
            if prepared
            else self.prepare_cached_tracks(tracks)
        )
        if not prepared:
            self._apply_source_availability(
                self._tracks, self._source_availability
            )
        self._catalog_revision += 1
        return len(self._tracks)

    def set_source_availability(
        self,
        root: str | Path,
        status: str,
        *,
        update_tracks: bool = True,
    ) -> None:
        """Annotate cached rows from one source without checking its files."""
        key = os.path.normcase(os.path.abspath(os.path.expanduser(str(root))))
        normalized = str(status or "cached").strip().lower()
        if normalized not in {"available", "unavailable", "degraded", "cached"}:
            normalized = "cached"
        self._source_availability[key] = normalized
        if update_tracks:
            self._apply_source_availability(
                self._tracks, self._source_availability
            )
        self._catalog_revision += 1

    @staticmethod
    def _apply_source_availability(
        tracks: list[dict[str, Any]],
        source_availability: dict[str, str],
    ) -> None:
        roots = [
            (
                os.path.normcase(os.path.abspath(os.path.expanduser(root))),
                status,
            )
            for root, status in source_availability.items()
        ]
        for track in tracks:
            path = str(track.get("local_path") or "").strip()
            if not path:
                continue
            canonical = os.path.normcase(os.path.abspath(os.path.expanduser(path)))
            matches = [
                (root, status)
                for root, status in roots
                if canonical == root or canonical.startswith(root.rstrip(os.sep) + os.sep)
            ]
            if matches:
                track["availability"] = max(matches, key=lambda item: len(item[0]))[1]

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
        self._apply_source_availability(tracks, self._source_availability)
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
    def track_count(self) -> int:
        """Return the in-memory row count without copying track dictionaries."""
        return len(self._tracks)

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
