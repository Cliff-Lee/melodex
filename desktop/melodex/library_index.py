from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


SCHEMA_VERSION = 3


def _canonical_path(path: str | Path) -> str:
    """Normalise a root lexically without touching the filesystem."""
    return os.path.normcase(
        os.path.abspath(
            os.path.expanduser(str(path))
        )
    )


def _root_id(path: str | Path) -> str:
    value = _canonical_path(path).encode("utf-8", errors="surrogatepass")
    return hashlib.sha256(value).hexdigest()[:32]


class LocalLibraryIndex:
    """Persistent metadata cache for local/network music libraries.

    The database stores paths and metadata only. Audio bytes are never copied
    into the index. Each operation opens its own SQLite connection so a full
    index replacement can safely run on a worker thread.
    """

    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialise()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(str(self.path), timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 30000")
        return connection

    def _initialise(self) -> None:
        with self._connect() as db:
            current_version = int(db.execute("PRAGMA user_version").fetchone()[0])
            if current_version == SCHEMA_VERSION:
                return
            db.execute("PRAGMA journal_mode = WAL")
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS index_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
                """
            )
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS roots (
                    root_id TEXT PRIMARY KEY,
                    path TEXT NOT NULL UNIQUE,
                    last_scan_at TEXT,
                    last_track_count INTEGER NOT NULL DEFAULT 0
                )
                """
            )
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS tracks (
                    root_id TEXT NOT NULL,
                    relative_path TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    size INTEGER,
                    mtime_ns INTEGER,
                    PRIMARY KEY (root_id, relative_path),
                    FOREIGN KEY (root_id)
                        REFERENCES roots(root_id)
                        ON DELETE CASCADE
                )
                """
            )
            db.execute(
                "CREATE INDEX IF NOT EXISTS tracks_root_idx ON tracks(root_id)"
            )
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS directories (
                    root_id TEXT NOT NULL,
                    relative_dir TEXT NOT NULL,
                    manifest TEXT NOT NULL,
                    file_count INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY (root_id, relative_dir),
                    FOREIGN KEY (root_id)
                        REFERENCES roots(root_id)
                        ON DELETE CASCADE
                )
                """
            )
            db.execute(
                "CREATE INDEX IF NOT EXISTS directories_root_idx "
                "ON directories(root_id)"
            )
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS scan_generations (
                    generation_id TEXT PRIMARY KEY,
                    root_signature TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    completed_at TEXT,
                    status TEXT NOT NULL,
                    staged_count INTEGER NOT NULL DEFAULT 0
                )
                """
            )
            db.execute(
                "CREATE INDEX IF NOT EXISTS scan_generations_signature_idx "
                "ON scan_generations(root_signature, started_at)"
            )
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS scan_stage_tracks (
                    generation_id TEXT NOT NULL,
                    local_path TEXT NOT NULL,
                    root_id TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    size INTEGER,
                    mtime_ns INTEGER,
                    PRIMARY KEY (generation_id, local_path),
                    FOREIGN KEY (generation_id)
                        REFERENCES scan_generations(generation_id)
                        ON DELETE CASCADE
                )
                """
            )
            db.execute(
                "CREATE INDEX IF NOT EXISTS scan_stage_generation_idx "
                "ON scan_stage_tracks(generation_id)"
            )
            db.execute(
                """
                INSERT INTO index_meta(key, value)
                VALUES('schema_version', ?)
                ON CONFLICT(key) DO UPDATE SET value=excluded.value
                """,
                (str(SCHEMA_VERSION),),
            )
            db.execute(f"PRAGMA user_version = {int(SCHEMA_VERSION)}")

    @staticmethod
    def root_id(path: str | Path) -> str:
        return _root_id(path)

    def ensure_roots(self, roots: list[Path]) -> None:
        """Register roots without deleting any other cached roots."""
        clean = [Path(root) for root in roots]
        with self._connect() as db:
            for root in clean:
                db.execute(
                    """
                    INSERT INTO roots(root_id, path)
                    VALUES(?, ?)
                    ON CONFLICT(root_id) DO UPDATE SET path=excluded.path
                    """,
                    (_root_id(root), str(root)),
                )

    def sync_roots(self, roots: list[Path]) -> None:
        """Make the root table match configured roots without probing them."""
        clean = [Path(root) for root in roots]
        wanted = {_root_id(root): str(root) for root in clean}
        self.ensure_roots(clean)
        with self._connect() as db:
            if wanted:
                placeholders = ",".join("?" for _ in wanted)
                db.execute(
                    f"DELETE FROM roots WHERE root_id NOT IN ({placeholders})",
                    tuple(wanted),
                )
            else:
                db.execute("DELETE FROM roots")

    def sync_roots_if_needed(self, roots: list[Path]) -> bool:
        """Avoid startup writes when configured roots already match the index."""
        clean = [Path(root) for root in roots]
        wanted = {_root_id(root): str(root) for root in clean}
        with self._connect() as db:
            rows = db.execute("SELECT root_id, path FROM roots").fetchall()
        current = {
            str(row["root_id"]): str(row["path"])
            for row in rows
        }
        if current == wanted:
            return False
        self.sync_roots(clean)
        return True

    def roots_ready(self, roots: list[Path]) -> bool:
        """True when every configured root has at least one completed scan.

        A successfully indexed empty folder is ready because readiness is based
        on last_scan_at, not track count.
        """
        if not roots:
            return True
        ids = [_root_id(root) for root in roots]
        placeholders = ",".join("?" for _ in ids)
        with self._connect() as db:
            rows = db.execute(
                f"""
                SELECT root_id, last_scan_at
                FROM roots
                WHERE root_id IN ({placeholders})
                """,
                tuple(ids),
            ).fetchall()
        ready = {
            str(row["root_id"])
            for row in rows
            if str(row["last_scan_at"] or "").strip()
        }
        return all(root_id in ready for root_id in ids)

    def load_tracks(self, roots: list[Path]) -> list[dict[str, Any]]:
        if not roots:
            return []
        ids = [_root_id(root) for root in roots]
        placeholders = ",".join("?" for _ in ids)
        tracks: list[dict[str, Any]] = []
        with self._connect() as db:
            rows = db.execute(
                f"""
                SELECT metadata_json
                FROM tracks
                WHERE root_id IN ({placeholders})
                ORDER BY root_id, relative_path
                """,
                tuple(ids),
            )
            for row in rows:
                try:
                    value = json.loads(str(row["metadata_json"]))
                except Exception:
                    continue
                if isinstance(value, dict):
                    tracks.append(value)
        return tracks

    def load_scan_cache(
        self,
        roots: list[Path],
    ) -> dict[str, dict[str, Any]]:
        """Load cached raw metadata plus cheap file fingerprints.

        Keys are canonical absolute paths so the scanner can compare a newly
        enumerated file with the previous index without reopening its tags.
        """
        if not roots:
            return {}
        ids = [_root_id(root) for root in roots]
        placeholders = ",".join("?" for _ in ids)
        with self._connect() as db:
            rows = db.execute(
                f"""
                SELECT
                    t.root_id,
                    t.relative_path,
                    t.metadata_json,
                    t.size,
                    t.mtime_ns,
                    r.path AS root_path
                FROM tracks AS t
                JOIN roots AS r ON r.root_id = t.root_id
                WHERE t.root_id IN ({placeholders})
                """,
                tuple(ids),
            ).fetchall()

        cache: dict[str, dict[str, Any]] = {}
        for row in rows:
            try:
                metadata = json.loads(str(row["metadata_json"]))
            except Exception:
                continue
            if not isinstance(metadata, dict):
                continue
            root_path = str(row["root_path"] or "")
            relative = str(row["relative_path"] or "")
            local_path = str(
                metadata.get("local_path")
                or metadata.get("track_id")
                or (Path(root_path) / relative)
            )
            cache[_canonical_path(local_path)] = {
                "track": metadata,
                "size": (
                    int(row["size"])
                    if row["size"] is not None
                    else None
                ),
                "mtime_ns": (
                    int(row["mtime_ns"])
                    if row["mtime_ns"] is not None
                    else None
                ),
                "root_id": str(row["root_id"]),
                "root_path": root_path,
                "relative_path": relative,
            }
        return cache

    def load_directory_manifests(
        self,
        roots: list[Path],
    ) -> dict[str, dict[str, Any]]:
        """Load persisted direct-directory manifests for safe bulk reuse."""
        if not roots:
            return {}
        ids = [_root_id(root) for root in roots]
        placeholders = ",".join("?" for _ in ids)
        with self._connect() as db:
            rows = db.execute(
                f"""
                SELECT
                    d.root_id,
                    d.relative_dir,
                    d.manifest,
                    d.file_count,
                    r.path AS root_path
                FROM directories AS d
                JOIN roots AS r ON r.root_id = d.root_id
                WHERE d.root_id IN ({placeholders})
                """,
                tuple(ids),
            ).fetchall()

        out: dict[str, dict[str, Any]] = {}
        for row in rows:
            root_path = str(row["root_path"] or "")
            relative_dir = str(row["relative_dir"] or ".")
            directory = (
                Path(root_path)
                if relative_dir in {"", "."}
                else Path(root_path) / relative_dir
            )
            out[_canonical_path(directory)] = {
                "manifest": str(row["manifest"] or ""),
                "file_count": int(row["file_count"] or 0),
                "root_id": str(row["root_id"]),
                "root_path": root_path,
                "relative_dir": relative_dir,
            }
        return out

    @staticmethod
    def _roots_signature(roots: list[Path]) -> str:
        canonical = sorted(_canonical_path(root) for root in roots)
        payload = "\n".join(canonical).encode(
            "utf-8",
            errors="surrogatepass",
        )
        return hashlib.sha256(payload).hexdigest()

    def begin_scan_generation(self, roots: list[Path]) -> str:
        """Start a durable scan generation and retire abandoned workers."""
        clean = [Path(root) for root in roots]
        signature = self._roots_signature(clean)
        generation_id = uuid.uuid4().hex
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as db:
            db.execute(
                """
                UPDATE scan_generations
                SET status = 'interrupted', completed_at = ?
                WHERE root_signature = ? AND status = 'running'
                """,
                (now, signature),
            )
            db.execute(
                """
                INSERT INTO scan_generations(
                    generation_id,
                    root_signature,
                    started_at,
                    status,
                    staged_count
                )
                VALUES(?, ?, ?, 'running', 0)
                """,
                (generation_id, signature, now),
            )
        return generation_id

    def stage_scan_records(
        self,
        generation_id: str,
        roots: list[Path],
        records: list[dict[str, Any]],
    ) -> int:
        """Checkpoint successfully read changed metadata outside the live index."""
        clean = [Path(root) for root in roots]
        rows: list[tuple[str, str, str, str, int | None, int | None]] = []
        for record in records:
            if not isinstance(record, dict):
                continue
            track = dict(record.get("track") or {})
            local_path = str(
                track.get("local_path")
                or track.get("track_id")
                or record.get("local_path")
                or ""
            )
            if not local_path:
                continue
            root = self._matching_root(local_path, clean)
            if root is None:
                continue
            rows.append(
                (
                    str(generation_id),
                    _canonical_path(local_path),
                    _root_id(root),
                    json.dumps(
                        track,
                        ensure_ascii=False,
                        separators=(",", ":"),
                        default=str,
                    ),
                    int(record["size"])
                    if record.get("size") is not None
                    else None,
                    int(record["mtime_ns"])
                    if record.get("mtime_ns") is not None
                    else None,
                )
            )
        if not rows:
            return 0

        with self._connect() as db:
            state = db.execute(
                """
                SELECT status
                FROM scan_generations
                WHERE generation_id = ?
                """,
                (str(generation_id),),
            ).fetchone()
            if state is None or str(state["status"]) != "running":
                return 0
            db.executemany(
                """
                INSERT INTO scan_stage_tracks(
                    generation_id,
                    local_path,
                    root_id,
                    metadata_json,
                    size,
                    mtime_ns
                )
                VALUES(?, ?, ?, ?, ?, ?)
                ON CONFLICT(generation_id, local_path) DO UPDATE SET
                    root_id=excluded.root_id,
                    metadata_json=excluded.metadata_json,
                    size=excluded.size,
                    mtime_ns=excluded.mtime_ns
                """,
                rows,
            )
            staged_count = int(
                db.execute(
                    """
                    SELECT COUNT(*)
                    FROM scan_stage_tracks
                    WHERE generation_id = ?
                    """,
                    (str(generation_id),),
                ).fetchone()[0]
            )
            db.execute(
                """
                UPDATE scan_generations
                SET staged_count = ?
                WHERE generation_id = ?
                """,
                (staged_count, str(generation_id)),
            )
        return len(rows)

    def load_resume_cache(
        self,
        roots: list[Path],
    ) -> dict[str, dict[str, Any]]:
        """Load staged metadata from the newest interrupted compatible scan."""
        clean = [Path(root) for root in roots]
        if not clean:
            return {}
        signature = self._roots_signature(clean)
        with self._connect() as db:
            generation = db.execute(
                """
                SELECT generation_id
                FROM scan_generations
                WHERE root_signature = ?
                  AND status IN ('running', 'interrupted', 'cancelled', 'error')
                ORDER BY started_at DESC
                LIMIT 1
                """,
                (signature,),
            ).fetchone()
            if generation is None:
                return {}
            generation_id = str(generation["generation_id"])
            rows = db.execute(
                """
                SELECT
                    local_path,
                    root_id,
                    metadata_json,
                    size,
                    mtime_ns
                FROM scan_stage_tracks
                WHERE generation_id = ?
                """,
                (generation_id,),
            ).fetchall()

        root_by_id = {_root_id(root): root for root in clean}
        cache: dict[str, dict[str, Any]] = {}
        for row in rows:
            try:
                metadata = json.loads(str(row["metadata_json"]))
            except Exception:
                continue
            if not isinstance(metadata, dict):
                continue
            root = root_by_id.get(str(row["root_id"]))
            if root is None:
                continue
            local_path = str(row["local_path"] or "")
            if not local_path:
                continue
            cache[_canonical_path(local_path)] = {
                "track": metadata,
                "size": (
                    int(row["size"])
                    if row["size"] is not None
                    else None
                ),
                "mtime_ns": (
                    int(row["mtime_ns"])
                    if row["mtime_ns"] is not None
                    else None
                ),
                "root_id": str(row["root_id"]),
                "root_path": str(root),
                "resume_staged": True,
            }
        return cache

    def finish_scan_generation(
        self,
        generation_id: str,
        *,
        status: str,
    ) -> None:
        """Finish a generation; successful publication discards staging."""
        value = str(status or "error").strip().lower()
        if value not in {
            "completed",
            "cancelled",
            "error",
            "interrupted",
        }:
            value = "error"
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as db:
            row = db.execute(
                """
                SELECT root_signature
                FROM scan_generations
                WHERE generation_id = ?
                """,
                (str(generation_id),),
            ).fetchone()
            if row is None:
                return
            signature = str(row["root_signature"])
            db.execute(
                """
                UPDATE scan_generations
                SET status = ?, completed_at = ?
                WHERE generation_id = ?
                """,
                (value, now, str(generation_id)),
            )
            if value == "completed":
                # Once the new live index is committed, staged metadata is no
                # longer needed. Remove all compatible historical staging.
                old_rows = db.execute(
                    """
                    SELECT generation_id
                    FROM scan_generations
                    WHERE root_signature = ?
                    """,
                    (signature,),
                ).fetchall()
                ids = [str(item["generation_id"]) for item in old_rows]
                if ids:
                    placeholders = ",".join("?" for _ in ids)
                    db.execute(
                        f"""
                        DELETE FROM scan_stage_tracks
                        WHERE generation_id IN ({placeholders})
                        """,
                        tuple(ids),
                    )
                    db.execute(
                        f"""
                        UPDATE scan_generations
                        SET staged_count = 0
                        WHERE generation_id IN ({placeholders})
                        """,
                        tuple(ids),
                    )

    def scan_generation_summary(
        self,
        roots: list[Path],
    ) -> dict[str, Any]:
        """Return path-free generation diagnostics for support/testing."""
        clean = [Path(root) for root in roots]
        signature = self._roots_signature(clean)
        with self._connect() as db:
            row = db.execute(
                """
                SELECT generation_id, status, staged_count, started_at, completed_at
                FROM scan_generations
                WHERE root_signature = ?
                ORDER BY started_at DESC
                LIMIT 1
                """,
                (signature,),
            ).fetchone()
        if row is None:
            return {
                "status": "none",
                "staged_count": 0,
            }
        return {
            "generation_id": str(row["generation_id"]),
            "status": str(row["status"]),
            "staged_count": int(row["staged_count"] or 0),
            "started_at": str(row["started_at"] or ""),
            "completed_at": str(row["completed_at"] or ""),
        }

    @staticmethod
    def _matching_root(
        local_path: str | Path,
        roots: list[Path],
    ) -> Path | None:
        candidate = _canonical_path(local_path)
        ordered = sorted(
            roots,
            key=lambda root: len(_canonical_path(root)),
            reverse=True,
        )
        for root in ordered:
            root_value = _canonical_path(root)
            try:
                common = os.path.commonpath([candidate, root_value])
            except ValueError:
                continue
            if os.path.normcase(common) == os.path.normcase(root_value):
                return root
        return None

    @staticmethod
    def _relative_path(local_path: str | Path, root: Path) -> str:
        return os.path.relpath(
            _canonical_path(local_path),
            _canonical_path(root),
        )

    def replace_scan(
        self,
        roots: list[Path],
        snapshot: dict[str, Any],
        *,
        cancelled: Callable[[], bool] | None = None,
        batch_size: int = 250,
    ) -> dict[str, Any]:
        """Atomically persist completed scan results.

        Unavailable roots are deliberately preserved rather than interpreted as
        empty/deleted libraries. Only roots positively observed as available in
        the completed scan are replaced.
        """
        clean_roots = [Path(root) for root in roots]
        batch_size = max(1, int(batch_size))
        # A worker may finish after the user has changed configured roots.
        # Never let an older snapshot delete newer root registrations.
        self.ensure_roots(clean_roots)

        state_rows = [
            dict(row)
            for row in list((snapshot or {}).get("root_states") or [])
            if isinstance(row, dict)
        ]
        available_ids: set[str] = set()
        if state_rows:
            for row in state_rows:
                if not bool(row.get("available")):
                    continue
                # Older snapshots have no "complete" field and are treated as
                # complete for compatibility. New scans explicitly set it.
                if "complete" in row and not bool(row.get("complete")):
                    continue
                path = str(row.get("path") or "")
                if path:
                    available_ids.add(_root_id(path))
        else:
            # Compatibility with hand-built snapshots; real scans always
            # provide root_states.
            available_ids = {_root_id(root) for root in clean_roots}

        root_by_id = {_root_id(root): root for root in clean_roots}
        grouped: dict[
            str,
            list[tuple[str, dict[str, Any], int | None, int | None]],
        ] = {
            root_id: [] for root_id in available_ids if root_id in root_by_id
        }

        directory_rows: dict[str, list[tuple[str, str, int]]] = {
            root_id: [] for root_id in available_ids if root_id in root_by_id
        }
        preserve_dirs: dict[str, set[str]] = {
            root_id: set() for root_id in available_ids if root_id in root_by_id
        }
        preserve_counts: dict[str, int] = {
            root_id: 0 for root_id in available_ids if root_id in root_by_id
        }
        for row in list((snapshot or {}).get("preserve_directories") or []):
            if not isinstance(row, dict):
                continue
            root_path = str(row.get("root_path") or "")
            directory_path = str(row.get("path") or "")
            if not root_path or not directory_path:
                continue
            root_id = _root_id(root_path)
            root = root_by_id.get(root_id)
            if root is None or root_id not in available_ids:
                continue
            try:
                relative_dir = os.path.relpath(
                    _canonical_path(directory_path),
                    _canonical_path(root),
                )
            except ValueError:
                continue
            preserve_dirs.setdefault(root_id, set()).add(relative_dir)
            preserve_counts[root_id] = preserve_counts.get(root_id, 0) + max(
                0,
                int(row.get("file_count") or 0),
            )

        for row in list((snapshot or {}).get("directory_manifests") or []):
            if not isinstance(row, dict):
                continue
            root_path = str(row.get("root_path") or "")
            directory_path = str(row.get("path") or "")
            manifest = str(row.get("manifest") or "")
            if not root_path or not directory_path or not manifest:
                continue
            root_id = _root_id(root_path)
            root = root_by_id.get(root_id)
            if root is None or root_id not in available_ids:
                continue
            try:
                relative_dir = os.path.relpath(
                    _canonical_path(directory_path),
                    _canonical_path(root),
                )
            except ValueError:
                continue
            directory_rows.setdefault(root_id, []).append(
                (
                    relative_dir,
                    manifest,
                    max(0, int(row.get("file_count") or 0)),
                )
            )

        index_records = [
            dict(row)
            for row in list((snapshot or {}).get("index_records") or [])
            if isinstance(row, dict) and isinstance(row.get("track"), dict)
        ]
        if index_records:
            stored_records = index_records
        else:
            stored_tracks = (
                list((snapshot or {}).get("index_tracks") or [])
                or list((snapshot or {}).get("tracks") or [])
            )
            stored_records = [
                {"track": dict(raw), "size": None, "mtime_ns": None}
                for raw in stored_tracks
                if isinstance(raw, dict)
            ]

        for record in stored_records:
            track = dict(record.get("track") or {})
            local_path = str(track.get("local_path") or track.get("track_id") or "")
            if not local_path:
                continue
            root = self._matching_root(local_path, clean_roots)
            if root is None:
                continue
            root_id = _root_id(root)
            if root_id not in available_ids:
                continue
            size = record.get("size")
            mtime_ns = record.get("mtime_ns")
            grouped.setdefault(root_id, []).append(
                (
                    self._relative_path(local_path, root),
                    track,
                    int(size) if size is not None else None,
                    int(mtime_ns) if mtime_ns is not None else None,
                )
            )

        now = datetime.now(timezone.utc).isoformat()
        tracks_written = 0
        tracks_reused = 0
        tracks_deleted = 0
        write_batches = 0
        delete_batches = 0
        max_batch_rows = 0
        tracks_persisted_total = 0

        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                if cancelled is not None and cancelled():
                    db.rollback()
                    return {
                        "cancelled": True,
                        "roots_persisted": 0,
                        "tracks_persisted": 0,
                        "tracks_written": 0,
                        "tracks_reused": 0,
                        "tracks_deleted": 0,
                        "roots_unavailable": 0,
                        "roots_incomplete": 0,
                    }
                for root_id in available_ids:
                    if cancelled is not None and cancelled():
                        db.rollback()
                        return {
                            "cancelled": True,
                            "roots_persisted": 0,
                            "tracks_persisted": 0,
                            "tracks_written": 0,
                            "tracks_reused": 0,
                            "tracks_deleted": 0,
                            "roots_unavailable": 0,
                            "roots_incomplete": 0,
                        }
                    root = root_by_id.get(root_id)
                    if root is None:
                        continue
                    db.execute(
                        """
                        INSERT INTO roots(root_id, path)
                        VALUES(?, ?)
                        ON CONFLICT(root_id) DO UPDATE SET path=excluded.path
                        """,
                        (root_id, str(root)),
                    )

                    existing_rows = db.execute(
                        """
                        SELECT relative_path, size, mtime_ns
                        FROM tracks
                        WHERE root_id = ?
                        """,
                        (root_id,),
                    )
                    existing: dict[
                        str,
                        tuple[int | None, int | None],
                    ] = {}
                    for row in existing_rows:
                        existing[str(row["relative_path"])] = (
                            int(row["size"]) if row["size"] is not None else None,
                            int(row["mtime_ns"]) if row["mtime_ns"] is not None else None,
                        )

                    rows = grouped.get(root_id, [])
                    incoming_paths = {
                        relative_path for relative_path, _, _, _ in rows
                    }
                    preserved = preserve_dirs.get(root_id, set())
                    preserved_existing_paths = {
                        relative_path
                        for relative_path in existing
                        if os.path.dirname(relative_path) in preserved
                    }
                    tracks_reused += len(preserved_existing_paths)
                    removed_paths = (
                        existing.keys()
                        - incoming_paths
                        - preserved_existing_paths
                    )
                    if removed_paths:
                        delete_batch: list[tuple[str, str]] = []
                        for relative_path in removed_paths:
                            delete_batch.append((root_id, relative_path))
                            if len(delete_batch) >= batch_size:
                                db.executemany(
                                    """
                                    DELETE FROM tracks
                                    WHERE root_id = ? AND relative_path = ?
                                    """,
                                    delete_batch,
                                )
                                tracks_deleted += len(delete_batch)
                                delete_batches += 1
                                max_batch_rows = max(
                                    max_batch_rows,
                                    len(delete_batch),
                                )
                                delete_batch.clear()
                                if cancelled is not None and cancelled():
                                    db.rollback()
                                    return {
                                        "cancelled": True,
                                        "roots_persisted": 0,
                                        "tracks_persisted": 0,
                                        "tracks_written": 0,
                                        "tracks_reused": 0,
                                        "tracks_deleted": 0,
                                        "roots_unavailable": 0,
                                        "roots_incomplete": 0,
                                        "batch_size": batch_size,
                                        "write_batches": 0,
                                        "delete_batches": 0,
                                        "max_batch_rows": 0,
                                    }
                        if delete_batch:
                            db.executemany(
                                """
                                DELETE FROM tracks
                                WHERE root_id = ? AND relative_path = ?
                                """,
                                delete_batch,
                            )
                            tracks_deleted += len(delete_batch)
                            delete_batches += 1
                            max_batch_rows = max(
                                max_batch_rows,
                                len(delete_batch),
                            )

                    write_batch: list[
                        tuple[str, str, str, int | None, int | None]
                    ] = []
                    for relative_path, track, size, mtime_ns in rows:
                        previous = existing.get(relative_path)
                        reusable = bool(
                            previous is not None
                            and size is not None
                            and mtime_ns is not None
                            and previous[0] is not None
                            and previous[1] is not None
                            and int(previous[0]) == int(size)
                            and int(previous[1]) == int(mtime_ns)
                        )
                        if reusable:
                            tracks_reused += 1
                            continue

                        write_batch.append(
                            (
                                root_id,
                                relative_path,
                                json.dumps(
                                    track,
                                    ensure_ascii=False,
                                    separators=(",", ":"),
                                    default=str,
                                ),
                                size,
                                mtime_ns,
                            )
                        )
                        if len(write_batch) >= batch_size:
                            db.executemany(
                                """
                                INSERT INTO tracks(
                                    root_id,
                                    relative_path,
                                    metadata_json,
                                    size,
                                    mtime_ns
                                )
                                VALUES(?, ?, ?, ?, ?)
                                ON CONFLICT(root_id, relative_path) DO UPDATE SET
                                    metadata_json=excluded.metadata_json,
                                    size=excluded.size,
                                    mtime_ns=excluded.mtime_ns
                                """,
                                write_batch,
                            )
                            tracks_written += len(write_batch)
                            write_batches += 1
                            max_batch_rows = max(
                                max_batch_rows,
                                len(write_batch),
                            )
                            write_batch.clear()
                            if cancelled is not None and cancelled():
                                db.rollback()
                                return {
                                    "cancelled": True,
                                    "roots_persisted": 0,
                                    "tracks_persisted": 0,
                                    "tracks_written": 0,
                                    "tracks_reused": 0,
                                    "tracks_deleted": 0,
                                    "roots_unavailable": 0,
                                    "roots_incomplete": 0,
                                    "batch_size": batch_size,
                                    "write_batches": 0,
                                    "delete_batches": 0,
                                    "max_batch_rows": 0,
                                }

                    if write_batch:
                        db.executemany(
                            """
                            INSERT INTO tracks(
                                root_id,
                                relative_path,
                                metadata_json,
                                size,
                                mtime_ns
                            )
                            VALUES(?, ?, ?, ?, ?)
                            ON CONFLICT(root_id, relative_path) DO UPDATE SET
                                metadata_json=excluded.metadata_json,
                                size=excluded.size,
                                mtime_ns=excluded.mtime_ns
                            """,
                            write_batch,
                        )
                        tracks_written += len(write_batch)
                        write_batches += 1
                        max_batch_rows = max(
                            max_batch_rows,
                            len(write_batch),
                        )

                    db.execute(
                        "DELETE FROM directories WHERE root_id = ?",
                        (root_id,),
                    )
                    manifests = directory_rows.get(root_id, [])
                    if manifests:
                        db.executemany(
                            """
                            INSERT INTO directories(
                                root_id,
                                relative_dir,
                                manifest,
                                file_count
                            )
                            VALUES(?, ?, ?, ?)
                            """,
                            [
                                (root_id, relative_dir, manifest, file_count)
                                for relative_dir, manifest, file_count in manifests
                            ],
                        )

                    current_track_count = int(
                        db.execute(
                            """
                            SELECT COUNT(*)
                            FROM tracks
                            WHERE root_id = ?
                            """,
                            (root_id,),
                        ).fetchone()[0]
                    )
                    tracks_persisted_total += current_track_count
                    db.execute(
                        """
                        UPDATE roots
                        SET last_scan_at = ?, last_track_count = ?
                        WHERE root_id = ?
                        """,
                        (now, current_track_count, root_id),
                    )
                if cancelled is not None and cancelled():
                    db.rollback()
                    return {
                        "cancelled": True,
                        "roots_persisted": 0,
                        "tracks_persisted": 0,
                        "tracks_written": 0,
                        "tracks_reused": 0,
                        "tracks_deleted": 0,
                        "roots_unavailable": 0,
                        "roots_incomplete": 0,
                    }
                db.commit()
            except Exception:
                db.rollback()
                raise

        return {
            "roots_persisted": len(available_ids),
            "tracks_persisted": int(tracks_persisted_total),
            "tracks_written": tracks_written,
            "tracks_reused": tracks_reused,
            "tracks_deleted": tracks_deleted,
            "batch_size": batch_size,
            "write_batches": write_batches,
            "delete_batches": delete_batches,
            "max_batch_rows": max_batch_rows,
            "directory_manifests_persisted": sum(
                len(rows) for rows in directory_rows.values()
            ),
            "preserved_directories": sum(
                len(rows) for rows in preserve_dirs.values()
            ),
            "preserved_tracks": sum(preserve_counts.values()),
            "roots_unavailable": sum(
                1 for row in state_rows
                if not bool(row.get("available"))
            ) if state_rows else 0,
            "roots_incomplete": sum(
                1 for row in state_rows
                if bool(row.get("available"))
                and "complete" in row
                and not bool(row.get("complete"))
            ),
        }

    def summary(self, roots: list[Path]) -> dict[str, Any]:
        clean = [Path(root) for root in roots]
        if not clean:
            return {
                "root_count": 0,
                "ready_roots": 0,
                "track_count": 0,
                "all_ready": True,
            }
        ids = [_root_id(root) for root in clean]
        placeholders = ",".join("?" for _ in ids)
        with self._connect() as db:
            root_rows = db.execute(
                f"""
                SELECT root_id, last_scan_at
                FROM roots
                WHERE root_id IN ({placeholders})
                """,
                tuple(ids),
            ).fetchall()
            track_count = int(
                db.execute(
                    f"""
                    SELECT COUNT(*)
                    FROM tracks
                    WHERE root_id IN ({placeholders})
                    """,
                    tuple(ids),
                ).fetchone()[0]
            )
        ready = sum(
            1 for row in root_rows
            if str(row["last_scan_at"] or "").strip()
        )
        return {
            "root_count": len(clean),
            "ready_roots": ready,
            "track_count": track_count,
            "all_ready": ready == len(clean),
        }


__all__ = ["LocalLibraryIndex", "SCHEMA_VERSION"]
