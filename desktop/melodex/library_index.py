from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1


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
                INSERT INTO index_meta(key, value)
                VALUES('schema_version', ?)
                ON CONFLICT(key) DO UPDATE SET value=excluded.value
                """,
                (str(SCHEMA_VERSION),),
            )

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
        with self._connect() as db:
            rows = db.execute(
                f"""
                SELECT metadata_json
                FROM tracks
                WHERE root_id IN ({placeholders})
                ORDER BY root_id, relative_path
                """,
                tuple(ids),
            ).fetchall()
        tracks: list[dict[str, Any]] = []
        for row in rows:
            try:
                value = json.loads(str(row["metadata_json"]))
            except Exception:
                continue
            if isinstance(value, dict):
                tracks.append(value)
        return tracks

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
    ) -> dict[str, Any]:
        """Atomically persist completed scan results.

        Unavailable roots are deliberately preserved rather than interpreted as
        empty/deleted libraries. Only roots positively observed as available in
        the completed scan are replaced.
        """
        clean_roots = [Path(root) for root in roots]
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
                path = str(row.get("path") or "")
                if path:
                    available_ids.add(_root_id(path))
        else:
            # Compatibility with hand-built snapshots; real scans always
            # provide root_states.
            available_ids = {_root_id(root) for root in clean_roots}

        root_by_id = {_root_id(root): root for root in clean_roots}
        grouped: dict[str, list[tuple[str, dict[str, Any]]]] = {
            root_id: [] for root_id in available_ids if root_id in root_by_id
        }

        stored_tracks = (
            list((snapshot or {}).get("index_tracks") or [])
            or list((snapshot or {}).get("tracks") or [])
        )
        for raw in stored_tracks:
            if not isinstance(raw, dict):
                continue
            track = dict(raw)
            local_path = str(track.get("local_path") or track.get("track_id") or "")
            if not local_path:
                continue
            root = self._matching_root(local_path, clean_roots)
            if root is None:
                continue
            root_id = _root_id(root)
            if root_id not in available_ids:
                continue
            grouped.setdefault(root_id, []).append(
                (self._relative_path(local_path, root), track)
            )

        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                for root_id in available_ids:
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
                    db.execute("DELETE FROM tracks WHERE root_id = ?", (root_id,))
                    rows = grouped.get(root_id, [])
                    db.executemany(
                        """
                        INSERT INTO tracks(
                            root_id,
                            relative_path,
                            metadata_json,
                            size,
                            mtime_ns
                        )
                        VALUES(?, ?, ?, NULL, NULL)
                        """,
                        [
                            (
                                root_id,
                                relative_path,
                                json.dumps(
                                    track,
                                    ensure_ascii=False,
                                    separators=(",", ":"),
                                    default=str,
                                ),
                            )
                            for relative_path, track in rows
                        ],
                    )
                    db.execute(
                        """
                        UPDATE roots
                        SET last_scan_at = ?, last_track_count = ?
                        WHERE root_id = ?
                        """,
                        (now, len(rows), root_id),
                    )
                db.commit()
            except Exception:
                db.rollback()
                raise

        return {
            "roots_persisted": len(available_ids),
            "tracks_persisted": sum(
                len(rows) for root_id, rows in grouped.items()
                if root_id in available_ids
            ),
            "roots_unavailable": max(0, len(clean_roots) - len(available_ids)),
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
