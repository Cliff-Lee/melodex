from __future__ import annotations

import hashlib
import json
import math
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any


class UserState:
    """Private local listening state used only by Melodex.

    Nothing is uploaded: history and preferences live in the application's
    support directory and are intentionally simple enough to survive upgrades.
    """

    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock, self._conn:
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS listening_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    rel TEXT NOT NULL DEFAULT '',
                    track_json TEXT NOT NULL,
                    played_at REAL NOT NULL,
                    completed INTEGER NOT NULL DEFAULT 0
                );
                CREATE INDEX IF NOT EXISTS idx_history_played_at
                    ON listening_history(played_at DESC);
                CREATE TABLE IF NOT EXISTS preferences (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS playback_checkpoint (
                    id INTEGER PRIMARY KEY CHECK(id=1),
                    track_json TEXT NOT NULL,
                    position_ms INTEGER NOT NULL DEFAULT 0,
                    updated_at REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS playback_queue (
                    id INTEGER PRIMARY KEY CHECK(id=1),
                    tracks_json TEXT NOT NULL,
                    queue_index INTEGER NOT NULL DEFAULT 0,
                    updated_at REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS recent_directories (
                    path TEXT PRIMARY KEY,
                    accessed_at REAL NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_recent_directories_accessed
                    ON recent_directories(accessed_at DESC);
                CREATE TABLE IF NOT EXISTS source_status (
                    source_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    checked_at REAL NOT NULL,
                    detail TEXT NOT NULL DEFAULT ''
                );
                CREATE TABLE IF NOT EXISTS pins (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    kind TEXT NOT NULL,
                    pin_key TEXT NOT NULL UNIQUE,
                    payload_json TEXT NOT NULL,
                    pinned_at REAL NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_pins_pinned_at
                    ON pins(pinned_at DESC);
                CREATE TABLE IF NOT EXISTS playlists (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT NOT NULL DEFAULT '',
                    source TEXT NOT NULL DEFAULT '',
                    payload_json TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_playlists_updated_at
                    ON playlists(updated_at DESC);
                CREATE TABLE IF NOT EXISTS track_signals (
                    track_key TEXT PRIMARY KEY,
                    track_json TEXT NOT NULL,
                    artist TEXT NOT NULL DEFAULT '',
                    plays INTEGER NOT NULL DEFAULT 0,
                    completes INTEGER NOT NULL DEFAULT 0,
                    skips INTEGER NOT NULL DEFAULT 0,
                    loves INTEGER NOT NULL DEFAULT 0,
                    dislikes INTEGER NOT NULL DEFAULT 0,
                    keeps INTEGER NOT NULL DEFAULT 0,
                    last_played REAL NOT NULL DEFAULT 0,
                    last_completed REAL NOT NULL DEFAULT 0,
                    last_feedback REAL NOT NULL DEFAULT 0
                );
                CREATE INDEX IF NOT EXISTS idx_track_signals_last_played
                    ON track_signals(last_played DESC);
                CREATE TABLE IF NOT EXISTS transition_signals (
                    style TEXT PRIMARY KEY,
                    likes INTEGER NOT NULL DEFAULT 0,
                    dislikes INTEGER NOT NULL DEFAULT 0,
                    updated_at REAL NOT NULL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS moments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    track_key TEXT NOT NULL,
                    track_json TEXT NOT NULL,
                    position_ms INTEGER NOT NULL DEFAULT 0,
                    label TEXT NOT NULL DEFAULT '',
                    created_at REAL NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_moments_created_at
                    ON moments(created_at DESC);
                CREATE TABLE IF NOT EXISTS vibes (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    mode TEXT NOT NULL DEFAULT 'balanced',
                    minutes INTEGER NOT NULL DEFAULT 60,
                    adventure REAL NOT NULL DEFAULT 0.34,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_vibes_updated_at
                    ON vibes(updated_at DESC);
                CREATE TABLE IF NOT EXISTS journey_recipes (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT NOT NULL DEFAULT '',
                    payload_json TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_journey_recipes_updated_at
                    ON journey_recipes(updated_at DESC);
                CREATE TABLE IF NOT EXISTS journey_runs (
                    id TEXT PRIMARY KEY,
                    recipe_id TEXT NOT NULL DEFAULT '',
                    recipe_json TEXT NOT NULL,
                    original_route_json TEXT NOT NULL,
                    final_route_json TEXT NOT NULL DEFAULT '{}',
                    status TEXT NOT NULL DEFAULT 'active',
                    started_at REAL NOT NULL,
                    ended_at REAL NOT NULL DEFAULT 0
                );
                CREATE INDEX IF NOT EXISTS idx_journey_runs_started_at
                    ON journey_runs(started_at DESC);
                CREATE TABLE IF NOT EXISTS journey_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at REAL NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_journey_events_run
                    ON journey_events(run_id, created_at ASC);
                """
            )

    def save_journey_recipe(
        self,
        recipe_id: str,
        name: str,
        description: str,
        payload: dict[str, Any],
    ) -> None:
        recipe_id = str(recipe_id or "").strip()
        if not recipe_id:
            raise ValueError("recipe_id is required")
        now = time.time()
        data = json.dumps(dict(payload or {}), ensure_ascii=False)
        with self._lock, self._conn:
            self._conn.execute(
                """
                INSERT INTO journey_recipes(id,name,description,payload_json,created_at,updated_at)
                VALUES(?,?,?,?,?,?)
                ON CONFLICT(id) DO UPDATE SET
                    name=excluded.name,
                    description=excluded.description,
                    payload_json=excluded.payload_json,
                    updated_at=excluded.updated_at
                """,
                (
                    recipe_id,
                    str(name or "Journey recipe"),
                    str(description or ""),
                    data,
                    now,
                    now,
                ),
            )

    def journey_recipes(self, limit: int = 200) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT id,name,description,payload_json,created_at,updated_at
                FROM journey_recipes
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (max(1, int(limit)),),
            ).fetchall()
        out: list[dict[str, Any]] = []
        for row in rows:
            try:
                payload = json.loads(row["payload_json"])
                if not isinstance(payload, dict):
                    payload = {}
            except Exception:
                payload = {}
            out.append(
                {
                    "id": str(row["id"]),
                    "name": str(row["name"]),
                    "description": str(row["description"] or ""),
                    "payload": payload,
                    "created_at": float(row["created_at"] or 0),
                    "updated_at": float(row["updated_at"] or 0),
                }
            )
        return out

    def get_journey_recipe(self, recipe_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute(
                """
                SELECT id,name,description,payload_json,created_at,updated_at
                FROM journey_recipes
                WHERE id=?
                """,
                (str(recipe_id or ""),),
            ).fetchone()
        if row is None:
            return None
        try:
            payload = json.loads(row["payload_json"])
            if not isinstance(payload, dict):
                payload = {}
        except Exception:
            payload = {}
        return {
            "id": str(row["id"]),
            "name": str(row["name"]),
            "description": str(row["description"] or ""),
            "payload": payload,
            "created_at": float(row["created_at"] or 0),
            "updated_at": float(row["updated_at"] or 0),
        }

    def delete_journey_recipe(self, recipe_id: str) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "DELETE FROM journey_recipes WHERE id=?",
                (str(recipe_id or ""),),
            )

    def start_journey_run(
        self,
        run_id: str,
        *,
        recipe_id: str = "",
        recipe: dict[str, Any] | None = None,
        original_route: dict[str, Any] | None = None,
    ) -> None:
        run_id = str(run_id or "").strip()
        if not run_id:
            raise ValueError("run_id is required")
        now = time.time()
        with self._lock, self._conn:
            self._conn.execute(
                """
                INSERT INTO journey_runs(
                    id,recipe_id,recipe_json,original_route_json,final_route_json,
                    status,started_at,ended_at
                ) VALUES(?,?,?,?,?,'active',?,0)
                """,
                (
                    run_id,
                    str(recipe_id or ""),
                    json.dumps(dict(recipe or {}), ensure_ascii=False),
                    json.dumps(dict(original_route or {}), ensure_ascii=False),
                    "{}",
                    now,
                ),
            )

    def record_journey_event(
        self,
        run_id: str,
        event_type: str,
        payload: dict[str, Any] | None = None,
    ) -> int:
        run_id = str(run_id or "").strip()
        event_type = str(event_type or "").strip()
        if not run_id or not event_type:
            return 0
        with self._lock, self._conn:
            cur = self._conn.execute(
                """
                INSERT INTO journey_events(run_id,event_type,payload_json,created_at)
                VALUES(?,?,?,?)
                """,
                (
                    run_id,
                    event_type,
                    json.dumps(dict(payload or {}), ensure_ascii=False),
                    time.time(),
                ),
            )
            return int(cur.lastrowid or 0)

    def finish_journey_run(
        self,
        run_id: str,
        *,
        status: str,
        final_route: dict[str, Any] | None = None,
    ) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                """
                UPDATE journey_runs
                SET status=?,final_route_json=?,ended_at=?
                WHERE id=?
                """,
                (
                    str(status or "stopped"),
                    json.dumps(dict(final_route or {}), ensure_ascii=False),
                    time.time(),
                    str(run_id or ""),
                ),
            )

    def journey_runs(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT id,recipe_id,recipe_json,original_route_json,final_route_json,
                       status,started_at,ended_at
                FROM journey_runs
                ORDER BY started_at DESC
                LIMIT ?
                """,
                (max(1, int(limit)),),
            ).fetchall()
        out: list[dict[str, Any]] = []
        for row in rows:
            def parsed(key: str) -> dict[str, Any]:
                try:
                    value = json.loads(row[key])
                    return value if isinstance(value, dict) else {}
                except Exception:
                    return {}
            out.append(
                {
                    "id": str(row["id"]),
                    "recipe_id": str(row["recipe_id"] or ""),
                    "recipe": parsed("recipe_json"),
                    "original_route": parsed("original_route_json"),
                    "final_route": parsed("final_route_json"),
                    "status": str(row["status"] or ""),
                    "started_at": float(row["started_at"] or 0),
                    "ended_at": float(row["ended_at"] or 0),
                }
            )
        return out

    def journey_events(self, run_id: str) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT id,event_type,payload_json,created_at
                FROM journey_events
                WHERE run_id=?
                ORDER BY created_at ASC,id ASC
                """,
                (str(run_id or ""),),
            ).fetchall()
        out: list[dict[str, Any]] = []
        for row in rows:
            try:
                payload = json.loads(row["payload_json"])
                if not isinstance(payload, dict):
                    payload = {}
            except Exception:
                payload = {}
            out.append(
                {
                    "id": int(row["id"]),
                    "event_type": str(row["event_type"] or ""),
                    "payload": payload,
                    "created_at": float(row["created_at"] or 0),
                }
            )
        return out

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    @staticmethod
    def track_key(track: dict[str, Any]) -> str:
        rel = str(track.get("rel", "") or "").strip()
        if rel:
            return "rel:" + rel
        local = str(track.get("local_path", "") or "").strip()
        if local:
            return "file:" + local
        artist = str(track.get("artist", "") or "").strip().casefold()
        album = str(track.get("album", "") or "").strip().casefold()
        title = str(track.get("title", "") or "").strip().casefold()
        return "meta:" + "|".join((artist, album, title))

    @staticmethod
    def playback_track_snapshot(track: dict[str, Any] | None) -> dict[str, Any]:
        """Keep stable identity and display metadata, never transient sources or credentials."""
        source = dict(track or {})
        allowed = (
            "provider_id", "track_id", "id", "rel", "local_path", "title",
            "artist", "album", "name", "duration", "duration_seconds", "track_no",
            "disc_no", "year", "genre", "provisional", "progressive_local",
        )
        snapshot: dict[str, Any] = {}
        for key in allowed:
            value = source.get(key)
            if value is None or value == "":
                continue
            if key == "local_path" and isinstance(value, Path):
                value = str(value)
            if key in {"local_path", "rel"} and isinstance(value, str):
                if value.strip().casefold().startswith(("http://", "https://")):
                    continue
            if key == "provider_id" and isinstance(value, str):
                value = value.strip()
            if not isinstance(value, (str, int, float, bool)):
                continue
            if isinstance(value, float) and not math.isfinite(value):
                continue
            if key in {"track_id", "id"} and isinstance(value, str):
                identity = value.strip()
                if not identity or identity.casefold().startswith(("http://", "https://")):
                    continue
                if "?" in identity or "#" in identity:
                    continue
                value = identity
            snapshot[key] = value
        return snapshot

    @staticmethod
    def playback_identity(track: dict[str, Any] | None) -> str:
        row = UserState.playback_track_snapshot(track)
        local_path = str(row.get("local_path") or "").strip()
        if local_path:
            return "file:" + local_path
        rel = str(row.get("rel") or "").strip()
        if rel:
            return "rel:" + rel
        provider = str(row.get("provider_id") or "").strip()
        track_id = row.get("track_id")
        if track_id in (None, ""):
            track_id = row.get("id")
        if provider and track_id not in (None, ""):
            return "provider:" + json.dumps(
                [provider, str(track_id)], ensure_ascii=False, separators=(",", ":")
            )
        return ""

    @staticmethod
    def same_playback_track(
        left: dict[str, Any] | None, right: dict[str, Any] | None
    ) -> bool:
        left_identity = UserState.playback_identity(left)
        right_identity = UserState.playback_identity(right)
        if left_identity or right_identity:
            return bool(left_identity and right_identity and left_identity == right_identity)
        left_row = dict(left or {})
        right_row = dict(right or {})
        if not any(str(left_row.get(key) or "").strip() for key in ("artist", "album", "title")):
            return False
        return UserState.track_key(left_row) == UserState.track_key(right_row)

    def _signal_event(self, track: dict[str, Any], event: str) -> None:
        key = self.track_key(track)
        if not key:
            return
        payload = json.dumps(self.playback_track_snapshot(track), ensure_ascii=False)
        artist = str(track.get("artist", "") or "")
        now = time.time()
        column = {
            "play": "plays", "complete": "completes", "skip": "skips",
            "love": "loves", "dislike": "dislikes", "keep": "keeps",
        }.get(str(event or "").lower())
        if not column:
            return
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO track_signals(track_key,track_json,artist) VALUES(?,?,?) "
                "ON CONFLICT(track_key) DO UPDATE SET track_json=excluded.track_json,artist=excluded.artist",
                (key, payload, artist),
            )
            params: list[Any] = [now, key]
            if event == "play":
                self._conn.execute(
                    f"UPDATE track_signals SET {column}={column}+1,last_played=? WHERE track_key=?",
                    params,
                )
            elif event == "complete":
                self._conn.execute(
                    f"UPDATE track_signals SET {column}={column}+1,last_completed=? WHERE track_key=?",
                    params,
                )
            else:
                self._conn.execute(
                    f"UPDATE track_signals SET {column}={column}+1,last_feedback=? WHERE track_key=?",
                    params,
                )

    def record_play(self, track: dict[str, Any]) -> int:
        snapshot = self.playback_track_snapshot(track)
        payload = json.dumps(snapshot, ensure_ascii=False)
        with self._lock, self._conn:
            cur = self._conn.execute(
                "INSERT INTO listening_history(rel,track_json,played_at,completed) VALUES(?,?,?,0)",
                (str(snapshot.get("rel", "") or ""), payload, time.time()),
            )
            history_id = int(cur.lastrowid or 0)
        self._signal_event(track, "play")
        path = str(snapshot.get("local_path") or "").strip()
        if path:
            self.record_recent_directory(str(Path(path).parent))
        return history_id

    def save_playback_checkpoint(
        self, track: dict[str, Any] | None, position_ms: int
    ) -> None:
        """Persist a stable track identity and position, never a short-lived source."""
        if not track:
            return
        row = self.playback_track_snapshot(track)
        if not self.playback_identity(row):
            with self._lock, self._conn:
                self._conn.execute("DELETE FROM playback_checkpoint WHERE id=1")
            return
        payload = json.dumps(row, ensure_ascii=False)
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO playback_checkpoint(id,track_json,position_ms,updated_at) "
                "VALUES(1,?,?,?) ON CONFLICT(id) DO UPDATE SET "
                "track_json=excluded.track_json,position_ms=excluded.position_ms,"
                "updated_at=excluded.updated_at",
                (payload, max(0, int(position_ms)), time.time()),
            )

    def playback_checkpoint(self) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT track_json,position_ms,updated_at FROM playback_checkpoint WHERE id=1"
            ).fetchone()
        if row is None:
            return None
        try:
            raw_track = json.loads(row["track_json"])
        except Exception:
            return None
        if not isinstance(raw_track, dict):
            return None
        track = self.playback_track_snapshot(raw_track)
        if not self.playback_identity(track):
            with self._lock, self._conn:
                self._conn.execute("DELETE FROM playback_checkpoint WHERE id=1")
            return None
        payload = json.dumps(track, ensure_ascii=False)
        if payload != row["track_json"]:
            with self._lock, self._conn:
                self._conn.execute(
                    "UPDATE playback_checkpoint SET track_json=? WHERE id=1",
                    (payload,),
                )
        return {
            "track": track,
            "position_ms": max(0, int(row["position_ms"] or 0)),
            "updated_at": float(row["updated_at"] or 0),
        }

    def save_playback_queue(
        self,
        tracks: list[dict[str, Any]],
        queue_index: int,
        *,
        max_tracks: int = 5000,
    ) -> None:
        """Persist a bounded queue of resolvable identities without temporary URLs."""
        source = [dict(row) for row in list(tracks or []) if isinstance(row, dict)]
        try:
            requested_index = int(queue_index)
        except (TypeError, ValueError):
            requested_index = -1
        entries = []
        for source_index, row in enumerate(source):
            snapshot = self.playback_track_snapshot(row)
            if self.playback_identity(snapshot):
                entries.append((source_index, snapshot))
        if not entries:
            with self._lock, self._conn:
                self._conn.execute("DELETE FROM playback_queue WHERE id=1")
            return
        target_position = next(
            (i for i, (source_index, _) in enumerate(entries) if source_index == requested_index),
            None,
        )
        if target_position is None and requested_index >= 0:
            target_position = min(
                range(len(entries)),
                key=lambda i: (abs(entries[i][0] - requested_index), entries[i][0] > requested_index),
            )
        if target_position is None:
            target_position = 0
        limit = max(1, int(max_tracks))
        if len(entries) > limit:
            start = max(0, min(target_position - limit // 2, len(entries) - limit))
            entries = entries[start:start + limit]
            target_position -= start
        payload = json.dumps([row for _, row in entries], ensure_ascii=False)
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO playback_queue(id,tracks_json,queue_index,updated_at) "
                "VALUES(1,?,?,?) ON CONFLICT(id) DO UPDATE SET "
                "tracks_json=excluded.tracks_json,queue_index=excluded.queue_index,"
                "updated_at=excluded.updated_at",
                (payload, target_position, time.time()),
            )

    def playback_queue(self, *, max_tracks: int = 5000) -> dict[str, Any] | None:
        with self._lock:
            saved = self._conn.execute(
                "SELECT tracks_json,queue_index,updated_at FROM playback_queue WHERE id=1"
            ).fetchone()
        if saved is None:
            return None
        try:
            raw_tracks = json.loads(saved["tracks_json"])
        except Exception:
            return None
        if not isinstance(raw_tracks, list):
            return None
        entries = []
        for source_index, raw_track in enumerate(raw_tracks):
            if not isinstance(raw_track, dict):
                continue
            snapshot = self.playback_track_snapshot(raw_track)
            if self.playback_identity(snapshot):
                entries.append((source_index, snapshot))
        if not entries:
            with self._lock, self._conn:
                self._conn.execute("DELETE FROM playback_queue WHERE id=1")
            return None
        old_index = max(0, min(len(raw_tracks) - 1, int(saved["queue_index"] or 0)))
        target_position = next(
            (i for i, (source_index, _) in enumerate(entries) if source_index == old_index),
            None,
        )
        if target_position is None:
            target_position = min(
                range(len(entries)),
                key=lambda i: (abs(entries[i][0] - old_index), entries[i][0] > old_index),
            )
        limit = max(1, int(max_tracks))
        if len(entries) > limit:
            start = max(0, min(target_position - limit // 2, len(entries) - limit))
            entries = entries[start:start + limit]
            target_position -= start
        tracks = [row for _, row in entries]
        with self._lock, self._conn:
            self._conn.execute(
                "UPDATE playback_queue SET tracks_json=?,queue_index=? WHERE id=1",
                (json.dumps(tracks, ensure_ascii=False), target_position),
            )
        return {
            "tracks": tracks,
            "queue_index": target_position,
            "updated_at": float(saved["updated_at"] or 0),
        }

    def record_recent_directory(self, path: str | Path) -> None:
        value = str(Path(path).expanduser().absolute())
        if not value:
            return
        now = time.time()
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO recent_directories(path,accessed_at) VALUES(?,?) "
                "ON CONFLICT(path) DO UPDATE SET accessed_at=excluded.accessed_at",
                (value, now),
            )
            self._conn.execute(
                "DELETE FROM recent_directories WHERE path NOT IN "
                "(SELECT path FROM recent_directories ORDER BY accessed_at DESC LIMIT 100)"
            )

    def recent_directories(self, limit: int = 20) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT path,accessed_at FROM recent_directories "
                "ORDER BY accessed_at DESC LIMIT ?",
                (max(1, int(limit)),),
            ).fetchall()
        return [
            {"path": str(row["path"]), "accessed_at": float(row["accessed_at"] or 0)}
            for row in rows
        ]

    def set_source_status(
        self, source_id: str, status: str, detail: str = ""
    ) -> None:
        key = str(source_id or "").strip()
        if not key:
            return
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO source_status(source_id,status,checked_at,detail) "
                "VALUES(?,?,?,?) ON CONFLICT(source_id) DO UPDATE SET "
                "status=excluded.status,checked_at=excluded.checked_at,detail=excluded.detail",
                (key, str(status or "unknown"), time.time(), str(detail or "")[:300]),
            )

    def source_statuses(self) -> dict[str, dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT source_id,status,checked_at,detail FROM source_status"
            ).fetchall()
        return {
            str(row["source_id"]): {
                "status": str(row["status"]),
                "checked_at": float(row["checked_at"] or 0),
                "detail": str(row["detail"] or ""),
            }
            for row in rows
        }

    def mark_completed(self, history_id: int) -> None:
        if not history_id:
            return
        track: dict[str, Any] | None = None
        with self._lock, self._conn:
            row = self._conn.execute("SELECT track_json,completed FROM listening_history WHERE id=?", (int(history_id),)).fetchone()
            if row and not bool(row["completed"]):
                try:
                    obj = json.loads(row["track_json"])
                    if isinstance(obj, dict):
                        track = obj
                except Exception:
                    track = None
            self._conn.execute("UPDATE listening_history SET completed=1 WHERE id=?", (int(history_id),))
        if track:
            self._signal_event(track, "complete")

    def record_skip(self, track: dict[str, Any]) -> None:
        self._signal_event(track, "skip")

    def record_feedback(self, track: dict[str, Any], positive: bool) -> None:
        key = self.track_key(track)
        if not key:
            return
        payload = json.dumps(dict(track), ensure_ascii=False)
        artist = str(track.get("artist", "") or "")
        now = time.time()
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO track_signals(track_key,track_json,artist) VALUES(?,?,?) "
                "ON CONFLICT(track_key) DO UPDATE SET track_json=excluded.track_json,artist=excluded.artist",
                (key, payload, artist),
            )
            if positive:
                self._conn.execute("UPDATE track_signals SET loves=1,dislikes=0,last_feedback=? WHERE track_key=?", (now, key))
            else:
                self._conn.execute("UPDATE track_signals SET dislikes=1,loves=0,last_feedback=? WHERE track_key=?", (now, key))

    @classmethod
    def _taste_correction_key(cls, track: dict[str, Any]) -> str:
        track = dict(track or {})
        if not any(
            str(track.get(field) or "").strip()
            for field in ("rel", "local_path", "track_id", "artist", "title", "album")
        ):
            return ""
        identity = cls.track_key(track)
        if not str(track.get("rel") or "").strip() and not str(
            track.get("local_path") or ""
        ).strip() and str(track.get("track_id") or "").strip():
            identity = "provider:" + "|".join(
                (
                    str(track.get("provider_id") or "").strip().casefold(),
                    str(track.get("track_id") or "").strip(),
                )
            )
        if not identity:
            return ""
        digest = hashlib.sha256(identity.encode("utf-8", errors="replace")).hexdigest()
        return "taste_correction:" + digest

    def record_taste_correction(self, track: dict[str, Any], direction: str) -> bool:
        """Remember one reversible, path-free correction for a track's traits."""
        direction = str(direction or "").strip().lower()
        if direction not in {"more", "less"}:
            raise ValueError("direction must be 'more' or 'less'")
        key = self._taste_correction_key(track)
        if not key:
            return False
        artist = str(
            track.get("artist") or track.get("album_artist") or ""
        ).strip()[:200]
        raw_genres = track.get("genres") or track.get("genre")
        if isinstance(raw_genres, (list, tuple, set)):
            values = sorted(raw_genres, key=str) if isinstance(raw_genres, set) else raw_genres
            genres: Any = [
                str(value).strip()[:80]
                for value in values
                if str(value or "").strip()
            ][:8]
        else:
            genres = str(raw_genres or "").strip()[:300]
        if not artist and not genres:
            return False
        payload = json.dumps(
            {
                "direction": direction,
                "artist": artist,
                "genres": genres,
            },
            ensure_ascii=False,
        )
        with self._lock, self._conn:
            self._conn.execute("DELETE FROM preferences WHERE key=?", (key,))
            self._conn.execute(
                "INSERT INTO preferences(key,value) VALUES(?,?)",
                (key, payload),
            )
        return True

    def taste_correction(self, track: dict[str, Any]) -> str:
        key = self._taste_correction_key(track)
        if not key:
            return ""
        with self._lock:
            row = self._conn.execute(
                "SELECT value FROM preferences WHERE key=?", (key,)
            ).fetchone()
        if row is None:
            return ""
        try:
            payload = json.loads(row["value"])
        except (TypeError, ValueError):
            return ""
        direction = str(payload.get("direction") or "") if isinstance(payload, dict) else ""
        return direction if direction in {"more", "less"} else ""

    def clear_taste_correction(self, track: dict[str, Any]) -> bool:
        key = self._taste_correction_key(track)
        if not key:
            return False
        with self._lock, self._conn:
            cur = self._conn.execute("DELETE FROM preferences WHERE key=?", (key,))
            return cur.rowcount > 0

    def taste_corrections(self, limit: int = 5000) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT value FROM preferences WHERE key GLOB 'taste_correction:*' "
                "ORDER BY rowid DESC LIMIT ?",
                (max(1, int(limit)),),
            ).fetchall()
        corrections: list[dict[str, Any]] = []
        for row in rows:
            try:
                payload = json.loads(row["value"])
            except (TypeError, ValueError):
                continue
            if not isinstance(payload, dict) or payload.get("direction") not in {"more", "less"}:
                continue
            corrections.append(
                {
                    "direction": str(payload["direction"]),
                    "artist": str(payload.get("artist") or ""),
                    "genres": payload.get("genres") or "",
                }
            )
        return corrections

    def record_keep(self, track: dict[str, Any]) -> None:
        self._signal_event(track, "keep")

    def track_signal(self, track: dict[str, Any]) -> dict[str, Any]:
        key = self.track_key(track)
        with self._lock:
            row = self._conn.execute("SELECT * FROM track_signals WHERE track_key=?", (key,)).fetchone()
        return dict(row) if row else {}

    def track_signals(self, limit: int = 5000) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM track_signals ORDER BY last_played DESC, last_feedback DESC LIMIT ?",
                (max(1, int(limit)),),
            ).fetchall()
        return [dict(row) for row in rows]

    def record_transition_feedback(self, style: str, positive: bool) -> None:
        style = str(style or "smooth").strip().lower() or "smooth"
        column = "likes" if positive else "dislikes"
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO transition_signals(style,updated_at) VALUES(?,?) "
                "ON CONFLICT(style) DO UPDATE SET updated_at=excluded.updated_at",
                (style, time.time()),
            )
            self._conn.execute(f"UPDATE transition_signals SET {column}={column}+1,updated_at=? WHERE style=?", (time.time(), style))

    def transition_preference(self, style: str) -> float:
        with self._lock:
            row = self._conn.execute("SELECT likes,dislikes FROM transition_signals WHERE style=?", (str(style or "smooth").lower(),)).fetchone()
        if not row:
            return 0.0
        likes, dislikes = int(row["likes"] or 0), int(row["dislikes"] or 0)
        return max(-1.0, min(1.0, (likes - dislikes) / max(2.0, likes + dislikes + 1.0)))

    def save_moment(self, track: dict[str, Any], position_ms: int, label: str = "") -> int:
        key = self.track_key(track)
        if not key:
            raise ValueError("track is required")
        payload = json.dumps(self.playback_track_snapshot(track), ensure_ascii=False)
        with self._lock, self._conn:
            cur = self._conn.execute(
                "INSERT INTO moments(track_key,track_json,position_ms,label,created_at) VALUES(?,?,?,?,?)",
                (key, payload, max(0, int(position_ms)), str(label or ""), time.time()),
            )
            return int(cur.lastrowid or 0)

    def moments(self, limit: int = 200) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT id,track_key,track_json,position_ms,label,created_at FROM moments ORDER BY created_at DESC LIMIT ?",
                (max(1, int(limit)),),
            ).fetchall()
        out: list[dict[str, Any]] = []
        updates: list[tuple[str, int]] = []
        for row in rows:
            try:
                raw_track = json.loads(row["track_json"])
                if not isinstance(raw_track, dict):
                    raw_track = {}
            except Exception:
                raw_track = {}
            track = self.playback_track_snapshot(raw_track)
            payload = json.dumps(track, ensure_ascii=False)
            if payload != row["track_json"]:
                updates.append((payload, int(row["id"])))
            out.append({
                "id": int(row["id"]), "track_key": row["track_key"], "track": track,
                "position_ms": int(row["position_ms"] or 0), "label": str(row["label"] or ""),
                "created_at": float(row["created_at"] or 0),
            })
        if updates:
            with self._lock, self._conn:
                self._conn.executemany(
                    "UPDATE moments SET track_json=? WHERE id=?",
                    updates,
                )
        return out

    def delete_moment(self, moment_id: int) -> None:
        with self._lock, self._conn:
            self._conn.execute("DELETE FROM moments WHERE id=?", (int(moment_id),))

    def save_vibe(self, vibe_id: str, name: str, mode: str, minutes: int, adventure: float) -> None:
        vibe_id = str(vibe_id or "").strip()
        if not vibe_id:
            raise ValueError("vibe_id is required")
        now = time.time()
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO vibes(id,name,mode,minutes,adventure,created_at,updated_at) VALUES(?,?,?,?,?,?,?) "
                "ON CONFLICT(id) DO UPDATE SET name=excluded.name,mode=excluded.mode,minutes=excluded.minutes,adventure=excluded.adventure,updated_at=excluded.updated_at",
                (vibe_id, str(name or "Vibe"), str(mode or "balanced"), max(15, int(minutes)), max(0.0, min(1.0, float(adventure))), now, now),
            )

    def vibes(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT id,name,mode,minutes,adventure,created_at,updated_at FROM vibes ORDER BY updated_at DESC LIMIT ?",
                (max(1, int(limit)),),
            ).fetchall()
        return [dict(row) for row in rows]

    def delete_vibe(self, vibe_id: str) -> None:
        with self._lock, self._conn:
            self._conn.execute("DELETE FROM vibes WHERE id=?", (str(vibe_id or ""),))

    def artist_profiles(self, limit: int = 10) -> list[dict[str, Any]]:
        rows = self.track_signals(5000)
        grouped: dict[str, dict[str, Any]] = {}
        for row in rows:
            artist = str(row.get("artist") or "").strip()
            if not artist:
                continue
            key = artist.casefold()
            g = grouped.setdefault(key, {"artist": artist, "plays": 0, "completes": 0, "skips": 0, "loves": 0, "dislikes": 0, "keeps": 0})
            for field in ("plays", "completes", "skips", "loves", "dislikes", "keeps"):
                g[field] += int(row.get(field) or 0)
        for g in grouped.values():
            plays = max(1, int(g["plays"]))
            completion = int(g["completes"]) / plays
            skip_rate = int(g["skips"]) / plays
            g["score"] = 3.0 * int(g["loves"]) + 1.4 * int(g["keeps"]) + 1.2 * completion + 0.22 * math.log1p(int(g["plays"])) - 1.5 * skip_rate - 5.0 * int(g["dislikes"])
        return sorted(grouped.values(), key=lambda x: (float(x.get("score") or 0), int(x.get("plays") or 0)), reverse=True)[:max(1, int(limit))]

    @staticmethod
    def _taste_summary_from_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
        if not rows:
            return {"tracks": 0, "artists": 0, "plays": 0, "completion_rate": 0.0, "loved": 0, "skips": 0}
        plays = sum(int(r.get("plays") or 0) for r in rows)
        completes = sum(int(r.get("completes") or 0) for r in rows)
        skips = sum(int(r.get("skips") or 0) for r in rows)
        loved = sum(int(r.get("loves") or 0) for r in rows)
        artists = {str(r.get("artist") or "").strip().casefold() for r in rows if str(r.get("artist") or "").strip()}
        return {
            "tracks": len(rows), "artists": len(artists), "plays": plays,
            "completion_rate": completes / max(1, plays), "loved": loved, "skips": skips,
        }

    def taste_summary(self) -> dict[str, Any]:
        return self._taste_summary_from_rows(self.track_signals(5000))

    def taste_profile(self, *, adventure: float = 0.35, recent_limit: int = 20) -> dict[str, Any]:
        """Return a bounded, path-free view of locally learned taste layers."""
        from .taste_model import build_local_taste_model

        model = build_local_taste_model(
            self,
            adventure=adventure,
            recent_limit=recent_limit,
        )
        return model.as_dict()

    def taste_display_summary(self) -> str:
        """Build a private, concise Home summary without expanding LLM context."""
        from .taste_model import build_local_taste_model

        rows = self.track_signals(5000)
        summary = self._taste_summary_from_rows(rows)
        profile = build_local_taste_model(self, track_signals=rows).as_dict()
        identity = profile["identity"]
        highlights = [
            str(item["name"])
            for item in list(identity.get("artists") or [])[:2]
            if float(item.get("score") or 0.0) > 0.05
        ]
        highlights.extend(
            str(item["name"])
            for item in list(identity.get("genres") or [])[:2]
            if float(item.get("score") or 0.0) > 0.05
        )
        base = (
            f"Taste memory: {summary['tracks']} tracks learned · "
            f"{summary['artists']} artists · completion rate "
            f"{float(summary['completion_rate']) * 100:.0f}%"
        )
        detail = (
            "Leans toward: " + " · ".join(highlights)
            if highlights
            else "Still learning from your plays and feedback."
        )
        reactions = profile["session_reactions"]
        session_detail = (
            f"Recent session: {int(reactions['completed_tracks'])} completed · "
            f"{int(reactions['quick_skips'])} quick skips."
        )
        return f"{base}\n{detail}\n{session_detail} Your taste profile stays on this device."

    def recent_tracks(self, limit: int = 120) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT id,track_json,played_at,completed FROM listening_history ORDER BY played_at DESC LIMIT ?",
                (max(1, int(limit)),),
            ).fetchall()
        out: list[dict[str, Any]] = []
        updates: list[tuple[str, int]] = []
        for row in rows:
            try:
                raw_item = json.loads(row["track_json"])
                if not isinstance(raw_item, dict):
                    continue
            except Exception:
                continue
            item = self.playback_track_snapshot(raw_item)
            if not item:
                continue
            payload = json.dumps(item, ensure_ascii=False)
            if payload != row["track_json"]:
                updates.append((payload, int(row["id"])))
            item["_history_id"] = row["id"]
            item["_played_at"] = row["played_at"]
            item["_completed"] = bool(row["completed"])
            out.append(item)
        if updates:
            with self._lock, self._conn:
                self._conn.executemany(
                    "UPDATE listening_history SET track_json=? WHERE id=?",
                    updates,
                )
        return out

    def sessions(self, limit: int = 16, gap_minutes: int = 45) -> list[dict[str, Any]]:
        tracks = list(reversed(self.recent_tracks(500)))
        sessions: list[list[dict[str, Any]]] = []
        gap = max(5, int(gap_minutes)) * 60
        for item in tracks:
            stamp = float(item.get("_played_at") or 0)
            if not sessions:
                sessions.append([item])
                continue
            prev = float(sessions[-1][-1].get("_played_at") or 0)
            if stamp - prev > gap:
                sessions.append([item])
            else:
                sessions[-1].append(item)
        result: list[dict[str, Any]] = []
        for group in reversed(sessions[-max(1, int(limit)):]):
            if not group:
                continue
            result.append({
                "started_at": float(group[0].get("_played_at") or 0),
                "ended_at": float(group[-1].get("_played_at") or 0),
                "tracks": [dict(t) for t in group],
            })
        return result


    def pin(self, kind: str, pin_key: str, payload: dict[str, Any]) -> None:
        kind = str(kind or "item").strip() or "item"
        pin_key = str(pin_key or "").strip()
        if not pin_key:
            return
        data = json.dumps(dict(payload), ensure_ascii=False)
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO pins(kind,pin_key,payload_json,pinned_at) VALUES(?,?,?,?) "
                "ON CONFLICT(pin_key) DO UPDATE SET kind=excluded.kind,payload_json=excluded.payload_json,pinned_at=excluded.pinned_at",
                (kind, pin_key, data, time.time()),
            )

    def unpin(self, pin_key: str) -> None:
        with self._lock, self._conn:
            self._conn.execute("DELETE FROM pins WHERE pin_key=?", (str(pin_key or ""),))

    def is_pinned(self, pin_key: str) -> bool:
        with self._lock:
            row = self._conn.execute("SELECT 1 FROM pins WHERE pin_key=?", (str(pin_key or ""),)).fetchone()
        return bool(row)

    def pins(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT kind,pin_key,payload_json,pinned_at FROM pins ORDER BY pinned_at DESC LIMIT ?",
                (max(1, int(limit)),),
            ).fetchall()
        out: list[dict[str, Any]] = []
        for row in rows:
            try:
                payload = json.loads(row["payload_json"])
                if not isinstance(payload, dict):
                    payload = {}
            except Exception:
                payload = {}
            payload["_pin_kind"] = row["kind"]
            payload["_pin_key"] = row["pin_key"]
            payload["_pinned_at"] = row["pinned_at"]
            out.append(payload)
        return out

    def get_bool(self, key: str, default: bool = False) -> bool:
        with self._lock:
            row = self._conn.execute("SELECT value FROM preferences WHERE key=?", (key,)).fetchone()
        if not row:
            return bool(default)
        return str(row["value"]).strip().lower() in {"1", "true", "yes", "on"}

    def set_bool(self, key: str, value: bool) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO preferences(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, "1" if value else "0"),
            )

    def get_text(self, key: str, default: str = "") -> str:
        with self._lock:
            row = self._conn.execute("SELECT value FROM preferences WHERE key=?", (key,)).fetchone()
        return str(row["value"]) if row else str(default)

    def set_text(self, key: str, value: str) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO preferences(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, str(value)),
            )

    def save_playlist(self, playlist_id: str, name: str, description: str, source: str, payload: dict[str, Any]) -> None:
        playlist_id = str(playlist_id or '').strip()
        if not playlist_id:
            raise ValueError('playlist_id is required')
        now = time.time()
        data = json.dumps(dict(payload), ensure_ascii=False)
        with self._lock, self._conn:
            self._conn.execute(
                """
                INSERT INTO playlists(id,name,description,source,payload_json,created_at,updated_at)
                VALUES(?,?,?,?,?,?,?)
                ON CONFLICT(id) DO UPDATE SET
                  name=excluded.name,
                  description=excluded.description,
                  source=excluded.source,
                  payload_json=excluded.payload_json,
                  updated_at=excluded.updated_at
                """,
                (playlist_id, str(name or 'Playlist'), str(description or ''), str(source or ''), data, now, now),
            )

    def playlists(self, limit: int = 200) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT id,name,description,source,payload_json,created_at,updated_at FROM playlists ORDER BY updated_at DESC LIMIT ?",
                (max(1, int(limit)),),
            ).fetchall()
        out: list[dict[str, Any]] = []
        for row in rows:
            try:
                payload = json.loads(row['payload_json'])
                if not isinstance(payload, dict):
                    payload = {}
            except Exception:
                payload = {}
            out.append({
                'id': row['id'], 'name': row['name'], 'description': row['description'],
                'source': row['source'], 'created_at': row['created_at'], 'updated_at': row['updated_at'],
                'track_count': len(list(payload.get('rows') or payload.get('tracks') or [])),
                'payload': payload,
            })
        return out

    def get_playlist(self, playlist_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT id,name,description,source,payload_json,created_at,updated_at FROM playlists WHERE id=?",
                (str(playlist_id or ''),),
            ).fetchone()
        if not row:
            return None
        try:
            payload = json.loads(row['payload_json'])
            if not isinstance(payload, dict):
                payload = {}
        except Exception:
            payload = {}
        return {
            'id': row['id'], 'name': row['name'], 'description': row['description'],
            'source': row['source'], 'created_at': row['created_at'], 'updated_at': row['updated_at'],
            'payload': payload,
        }

    def delete_playlist(self, playlist_id: str) -> None:
        with self._lock, self._conn:
            self._conn.execute("DELETE FROM playlists WHERE id=?", (str(playlist_id or ''),))
