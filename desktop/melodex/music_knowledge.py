from __future__ import annotations

import json
import sqlite3
import threading
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

from .user_state import UserState


def _norm(value: Any) -> str:
    return " ".join(str(value or "").strip().casefold().split())


def _edge_key(a: str, b: str, kind: str, label: str) -> tuple[str, str, str, str]:
    left, right = sorted((str(a), str(b)))
    return left, right, str(kind), _norm(label)


def _role_group(role: str) -> str:
    r = _norm(role)
    if any(word in r for word in ("producer", "engineer", "master", "mix")):
        return "people"
    if any(word in r for word in ("composer", "writer", "lyric", "arrang")):
        return "people"
    if any(
        word in r
        for word in (
            "perform",
            "vocal",
            "guitar",
            "bass",
            "drum",
            "piano",
            "keyboard",
            "sax",
            "violin",
            "cello",
            "conductor",
            "orchestra",
            "instrument",
        )
    ):
        return "people"
    return "people"


class MusicKnowledgeStore:
    """Small Core-owned persistent knowledge cache for the local Music Map.

    The store keeps only metadata Melodex has already learned explicitly. It
    performs no network access itself.
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
                CREATE TABLE IF NOT EXISTS track_knowledge (
                    track_key TEXT PRIMARY KEY,
                    payload_json TEXT NOT NULL,
                    updated_at REAL NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_track_knowledge_updated_at
                    ON track_knowledge(updated_at DESC);
                """
            )

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def get(self, track: dict[str, Any]) -> dict[str, Any]:
        key = UserState.track_key(dict(track or {}))
        if not key:
            return {}
        with self._lock:
            row = self._conn.execute(
                "SELECT payload_json,updated_at FROM track_knowledge WHERE track_key=?",
                (key,),
            ).fetchone()
        if row is None:
            return {}
        try:
            payload = json.loads(str(row["payload_json"] or "{}"))
            if not isinstance(payload, dict):
                return {}
            payload["_updated_at"] = float(row["updated_at"] or 0)
            return payload
        except Exception:
            return {}

    def remember(
        self,
        track: dict[str, Any],
        *,
        identity: dict[str, Any] | None = None,
        artist: dict[str, Any] | None = None,
        credits: list[dict[str, Any]] | None = None,
        context: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        track = dict(track or {})
        key = UserState.track_key(track)
        if not key:
            return {}

        current = self.get(track)
        current.pop("_updated_at", None)

        # Preserve canonical IDs that arrived from local file tags even before
        # any external metadata lookup happens.
        tagged_identity = {
            "recording_mbid": str(
                track.get("musicbrainz_recording_id")
                or track.get("recording_mbid")
                or ""
            ),
            "artist_mbid": str(
                track.get("musicbrainz_artist_id")
                or track.get("artist_mbid")
                or ""
            ),
            "release_mbid": str(
                track.get("musicbrainz_release_id")
                or track.get("release_mbid")
                or ""
            ),
            "release_group_mbid": str(
                track.get("musicbrainz_release_group_id")
                or track.get("release_group_mbid")
                or ""
            ),
            "artist": str(track.get("artist") or ""),
            "title": str(track.get("title") or ""),
            "album": str(track.get("album") or ""),
        }

        merged_identity = dict(current.get("identity") or {})
        for source in (tagged_identity, dict(identity or {})):
            for field, value in source.items():
                if value not in (None, ""):
                    merged_identity[field] = value
        if merged_identity:
            current["identity"] = merged_identity

        if isinstance(artist, dict) and artist:
            merged_artist = dict(current.get("artist") or {})
            merged_artist.update({k: v for k, v in artist.items() if v not in (None, "")})
            current["artist"] = merged_artist

        if credits is not None:
            current["credits"] = [
                dict(row) for row in credits if isinstance(row, dict)
            ][:80]

        if context is not None:
            current["context"] = [
                dict(card) for card in context if isinstance(card, dict)
            ][:40]

        now = time.time()
        with self._lock, self._conn:
            self._conn.execute(
                """
                INSERT INTO track_knowledge(track_key,payload_json,updated_at)
                VALUES(?,?,?)
                ON CONFLICT(track_key) DO UPDATE SET
                    payload_json=excluded.payload_json,
                    updated_at=excluded.updated_at
                """,
                (key, json.dumps(current, ensure_ascii=False), now),
            )
        current["_updated_at"] = now
        return current

    def snapshot(
        self, ref_map: dict[str, dict[str, Any]]
    ) -> dict[str, dict[str, Any]]:
        out: dict[str, dict[str, Any]] = {}
        for ref, track in ref_map.items():
            payload = self.get(dict(track or {}))
            # Also surface tag-carried IDs even when the track has never been
            # explicitly written into the knowledge database.
            identity = dict(payload.get("identity") or {})
            for field, source_fields in (
                (
                    "recording_mbid",
                    ("musicbrainz_recording_id", "recording_mbid"),
                ),
                ("artist_mbid", ("musicbrainz_artist_id", "artist_mbid")),
                ("release_mbid", ("musicbrainz_release_id", "release_mbid")),
                (
                    "release_group_mbid",
                    ("musicbrainz_release_group_id", "release_group_mbid"),
                ),
            ):
                if identity.get(field):
                    continue
                value = next(
                    (
                        str(track.get(name) or "").strip()
                        for name in source_fields
                        if str(track.get(name) or "").strip()
                    ),
                    "",
                )
                if value:
                    identity[field] = value
            if identity:
                identity.setdefault("artist", str(track.get("artist") or ""))
                identity.setdefault("title", str(track.get("title") or ""))
                identity.setdefault("album", str(track.get("album") or ""))
                payload["identity"] = identity
            if payload:
                out[str(ref)] = payload
        return out

    def count(self) -> int:
        with self._lock:
            row = self._conn.execute(
                "SELECT COUNT(*) AS n FROM track_knowledge"
            ).fetchone()
        return int(row["n"] or 0) if row is not None else 0


def _add_edge(
    edges: dict[tuple[str, str, str, str], dict[str, Any]],
    a: str,
    b: str,
    *,
    kind: str,
    label: str,
    strength: float = 0.8,
    evidence: str = "",
) -> None:
    if not a or not b or a == b:
        return
    key = _edge_key(a, b, kind, label)
    if key in edges:
        edges[key]["strength"] = max(
            float(edges[key].get("strength") or 0.0), float(strength)
        )
        return
    edges[key] = {
        "a": key[0],
        "b": key[1],
        "kind": str(kind),
        "label": str(label or kind),
        "strength": max(0.0, min(1.0, float(strength))),
        "evidence": str(evidence or ""),
    }


def _connect_group(
    edges: dict[tuple[str, str, str, str], dict[str, Any]],
    refs: list[str],
    *,
    kind: str,
    label: str,
    strength: float,
    evidence: str,
) -> None:
    unique = sorted(set(str(ref) for ref in refs if ref))
    if len(unique) < 2:
        return
    # Star links avoid O(n²) hairballs for an album artist, producer or work
    # that appears on many mapped tracks.
    anchor = unique[0]
    for ref in unique[1:]:
        _add_edge(
            edges,
            anchor,
            ref,
            kind=kind,
            label=label,
            strength=strength,
            evidence=evidence,
        )


def build_knowledge_graph(
    ref_map: dict[str, dict[str, Any]],
    knowledge: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Build readable track-level knowledge edges from cached metadata."""

    edges: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    recording_refs: dict[str, list[str]] = defaultdict(list)
    artist_refs: dict[str, list[str]] = defaultdict(list)
    artist_names: dict[str, str] = {}
    people_refs: dict[str, list[str]] = defaultdict(list)
    people_labels: dict[str, str] = {}
    work_refs: dict[str, list[str]] = defaultdict(list)
    work_labels: dict[str, str] = {}
    place_refs: dict[str, list[str]] = defaultdict(list)
    album_refs: dict[str, list[str]] = defaultdict(list)

    for ref, track in ref_map.items():
        payload = dict(knowledge.get(ref) or {})
        identity = dict(payload.get("identity") or {})

        recording_mbid = str(
            identity.get("recording_mbid")
            or track.get("musicbrainz_recording_id")
            or ""
        ).strip()
        artist_mbid = str(
            identity.get("artist_mbid")
            or track.get("musicbrainz_artist_id")
            or ""
        ).strip()
        if recording_mbid:
            recording_refs[recording_mbid].append(ref)
        if artist_mbid:
            artist_refs[artist_mbid].append(ref)
            artist_names[artist_mbid] = str(
                identity.get("artist") or track.get("artist") or "Same artist"
            )

        # A same-album overlay is useful even with no external metadata.
        album_key = _norm(track.get("album"))
        artist_key = _norm(track.get("artist"))
        if album_key and artist_key:
            album_refs[f"{artist_key}|{album_key}"].append(ref)

        for row in list(payload.get("credits") or []):
            if not isinstance(row, dict):
                continue
            kind = str(row.get("kind") or "artist")
            role = str(row.get("role") or "credit")
            name = str(row.get("name") or "").strip()
            mbid = str(row.get("mbid") or "").strip()
            if not name:
                continue
            if kind == "work":
                key = mbid or ("name:" + _norm(name))
                work_refs[key].append(ref)
                work_labels[key] = name
            else:
                key = mbid or ("name:" + _norm(name))
                people_refs[key].append(ref)
                people_labels[key] = f"{name} · {role}"

        for card in list(payload.get("context") or []):
            if not isinstance(card, dict):
                continue
            card_id = str(card.get("id") or "")
            title = str(card.get("title") or "")
            items = [
                item
                for item in list(card.get("items") or [])
                if isinstance(item, dict)
            ]
            if card_id == "linked-works" or _norm(title) == "composition & works":
                for item in items:
                    name = str(item.get("title") or "").strip()
                    if name:
                        key = "context:" + _norm(name)
                        work_refs[key].append(ref)
                        work_labels[key] = name
            elif card_id == "recording-places" or "record" in _norm(title) and "place" in _norm(title):
                for item in items:
                    name = str(item.get("title") or "").strip()
                    if name:
                        place_refs[_norm(name)].append(ref)
            elif card_id == "song-connections":
                for item in items:
                    canonical = (
                        item.get("canonical_ids")
                        if isinstance(item.get("canonical_ids"), dict)
                        else {}
                    )
                    target = str(
                        canonical.get("musicbrainz_recording_id") or ""
                    ).strip()
                    relation = str(item.get("relation") or item.get("badge") or "related")
                    if target and target in recording_refs:
                        for target_ref in recording_refs[target]:
                            _add_edge(
                                edges,
                                ref,
                                target_ref,
                                kind="song_relation",
                                label=relation,
                                strength=1.0,
                                evidence="context: Song Connections",
                            )

    # Same artist / album.
    for artist_mbid, refs in artist_refs.items():
        _connect_group(
            edges,
            refs,
            kind="artist",
            label=artist_names.get(artist_mbid) or "Same artist",
            strength=0.86,
            evidence="MusicBrainz artist identity",
        )
    for album_key, refs in album_refs.items():
        if len(refs) < 2:
            continue
        album_name = str(ref_map[refs[0]].get("album") or "Same album")
        _connect_group(
            edges,
            refs,
            kind="album",
            label=album_name,
            strength=0.74,
            evidence="local album metadata",
        )

    # Shared people, works and places.
    for key, refs in people_refs.items():
        _connect_group(
            edges,
            refs,
            kind=_role_group(people_labels.get(key, "")),
            label=people_labels.get(key) or "Shared credit",
            strength=0.90,
            evidence="MusicBrainz recording credits",
        )
    for key, refs in work_refs.items():
        _connect_group(
            edges,
            refs,
            kind="work",
            label=work_labels.get(key) or "Shared work",
            strength=0.95,
            evidence="MusicBrainz work relationship",
        )
    for place, refs in place_refs.items():
        _connect_group(
            edges,
            refs,
            kind="place",
            label=place.title(),
            strength=0.82,
            evidence="recording-place context",
        )

    # Related-artist links are artist-level relationships. Use one representative
    # mapped track per artist pair to keep the overlay legible.
    representative = {
        artist_mbid: sorted(set(refs))[0]
        for artist_mbid, refs in artist_refs.items()
        if refs
    }
    for ref, payload in knowledge.items():
        identity = dict(payload.get("identity") or {})
        source_artist = str(identity.get("artist_mbid") or "")
        if not source_artist or source_artist not in representative:
            continue
        artist = payload.get("artist") if isinstance(payload.get("artist"), dict) else {}
        for row in list(artist.get("related") or []):
            if not isinstance(row, dict):
                continue
            target_artist = str(row.get("id") or "")
            if not target_artist or target_artist not in representative:
                continue
            _add_edge(
                edges,
                representative[source_artist],
                representative[target_artist],
                kind="artist_relation",
                label=str(row.get("type") or "artist relationship"),
                strength=0.88,
                evidence="MusicBrainz artist relationship",
            )

    # The direct song-relation pass above may have run before the target MBID was
    # indexed if the target track appeared later in ref_map. Re-run only those
    # cards now that recording_refs is complete.
    for ref, payload in knowledge.items():
        for card in list(payload.get("context") or []):
            if not isinstance(card, dict) or str(card.get("id") or "") != "song-connections":
                continue
            for item in list(card.get("items") or []):
                if not isinstance(item, dict):
                    continue
                canonical = (
                    item.get("canonical_ids")
                    if isinstance(item.get("canonical_ids"), dict)
                    else {}
                )
                target = str(
                    canonical.get("musicbrainz_recording_id") or ""
                ).strip()
                relation = str(item.get("relation") or item.get("badge") or "related")
                for target_ref in recording_refs.get(target, []):
                    _add_edge(
                        edges,
                        ref,
                        target_ref,
                        kind="song_relation",
                        label=relation,
                        strength=1.0,
                        evidence="context: Song Connections",
                    )

    rows = sorted(
        edges.values(),
        key=lambda row: (
            str(row.get("kind") or ""),
            str(row.get("label") or "").casefold(),
            str(row.get("a") or ""),
            str(row.get("b") or ""),
        ),
    )
    counts: dict[str, int] = defaultdict(int)
    for row in rows:
        counts[str(row.get("kind") or "other")] += 1

    return {
        "edges": rows,
        "counts": dict(counts),
        "known_tracks": len(knowledge),
    }


__all__ = ["MusicKnowledgeStore", "build_knowledge_graph"]
