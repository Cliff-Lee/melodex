"""Pure queue rules for a user-steered, continuously replannable journey."""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Any


def _text(value: Any) -> str:
    return " ".join(str(value or "").strip().casefold().split())


def _track_key(track: dict[str, Any]) -> tuple[str, ...]:
    track = dict(track or {})
    for key in ("track_id", "local_path"):
        value = str(track.get(key) or "").strip()
        if value:
            return (key, value)
    return (
        "metadata",
        _text(track.get("provider_id")),
        _text(track.get("artist")),
        _text(track.get("title")),
        _text(track.get("album")),
    )


def queue_track_key(track: dict[str, Any]) -> tuple[str, ...]:
    """Stable in-memory identity for matching queue intent to player tracks."""
    return _track_key(track)


@dataclass
class QueueEntry:
    """A track plus private queue intent that is not mixed into track metadata."""

    track: dict[str, Any]
    origin: str = "route"
    pinned: bool = False
    locked: bool = False

    @property
    def protected(self) -> bool:
        """Protected entries survive an automatic route replacement."""
        return self.pinned or self.locked or self.origin == "manual"

    def copy(self) -> "QueueEntry":
        return QueueEntry(
            track=dict(self.track),
            origin=self.origin,
            pinned=self.pinned,
            locked=self.locked,
        )


class LivingQueue:
    """Queue editing semantics independent of the player UI and Qt runtime.

    The currently playing entry is immutable through these editing operations.
    Manual inserts, pinned entries, and locked entries are protected anchors:
    route replans can replace generated music around them but cannot discard or
    reorder them.
    """

    def __init__(
        self,
        tracks: list[dict[str, Any]] | None = None,
        current_index: int = 0,
    ) -> None:
        self.entries = [
            QueueEntry(dict(track), origin="route")
            for track in list(tracks or [])
            if isinstance(track, dict)
        ]
        if self.entries:
            requested_index = int(current_index)
            self.current_index = (
                -1
                if requested_index < 0
                else min(requested_index, len(self.entries) - 1)
            )
        else:
            self.current_index = -1
        self._undo_generated_tail: list[dict[str, Any]] | None = None

    def tracks(self) -> list[dict[str, Any]]:
        """Return clean track dictionaries without Living Queue metadata."""
        return [dict(entry.track) for entry in self.entries]

    def sync_from_tracks(
        self,
        tracks: list[dict[str, Any]],
        current_index: int,
        *,
        new_origin: str = "route",
    ) -> None:
        """Reconcile player state while retaining intent for matching tracks."""
        incoming = [
            dict(raw) for raw in list(tracks or []) if isinstance(raw, dict)
        ]
        current_keys = [_track_key(entry.track) for entry in self.entries]
        incoming_keys = [_track_key(track) for track in incoming]
        if self._undo_generated_tail is not None and current_keys != incoming_keys:
            # A separate player queue edit supersedes the automatic change
            # being undone. Keep undo available through playback advancement
            # and the player echo of our own replan, both of which retain order.
            self._undo_generated_tail = None

        previous: dict[tuple[str, ...], deque[QueueEntry]] = defaultdict(deque)
        for entry in self.entries:
            previous[_track_key(entry.track)].append(entry)

        entries: list[QueueEntry] = []
        for track in incoming:
            matches = previous.get(_track_key(track))
            if matches:
                entry = matches.popleft().copy()
                entry.track = track
            else:
                entry = QueueEntry(track, origin=str(new_origin or "route"))
            entries.append(entry)

        self.entries = entries
        requested_index = int(current_index)
        if not entries or requested_index < 0:
            self.current_index = -1
        else:
            self.current_index = min(requested_index, len(entries) - 1)

    def pin(self, index: int, value: bool = True) -> bool:
        index = int(index)
        if not self._is_upcoming(index):
            return False
        self.entries[index].pinned = bool(value)
        return True

    def lock_next(self, count: int) -> int:
        """Lock the next ``count`` tracks, returning the number newly locked."""
        start = max(0, self.current_index + 1)
        stop = min(len(self.entries), start + max(0, int(count)))
        changed = 0
        for entry in self.entries[start:stop]:
            if not entry.locked:
                entry.locked = True
                changed += 1
        return changed

    def set_locked(self, index: int, value: bool = True) -> bool:
        index = int(index)
        if not self._is_upcoming(index):
            return False
        self.entries[index].locked = bool(value)
        return True

    def unlock(self, index: int) -> bool:
        index = int(index)
        if not self._is_upcoming(index) or not self.entries[index].locked:
            return False
        self.entries[index].locked = False
        return True

    def remove(self, index: int) -> bool:
        index = int(index)
        if not self.can_remove(index):
            return False
        del self.entries[index]
        return True

    def can_remove(self, index: int) -> bool:
        index = int(index)
        return bool(
            self._is_upcoming(index)
            and not self.entries[index].pinned
            and not self.entries[index].locked
        )

    def insert(self, track: dict[str, Any], index: int | None = None) -> bool:
        if not isinstance(track, dict) or not track:
            return False
        if self.current_index < 0:
            self.entries = [QueueEntry(dict(track), origin="manual")]
            self.current_index = -1
            return True
        target = self.current_index + 1 if index is None else int(index)
        if target <= self.current_index or target > len(self.entries):
            return False
        self.entries.insert(target, QueueEntry(dict(track), origin="manual"))
        return True

    def move(self, source: int, target: int) -> bool:
        source, target = int(source), int(target)
        if not self.can_move(source, target):
            return False
        entry = self.entries.pop(source)
        self.entries.insert(target, entry)
        return True

    def can_move(self, source: int, target: int) -> bool:
        source, target = int(source), int(target)
        if not self._is_upcoming(source) or not self._is_upcoming(target):
            return False
        if source == target or self.entries[source].locked:
            return False
        locked_positions = {
            index
            for index, entry in enumerate(self.entries)
            if entry.locked
        }
        if source < target and any(source < index <= target for index in locked_positions):
            return False
        if target < source and any(target <= index < source for index in locked_positions):
            return False
        return True

    def replace_generated_tail(
        self,
        tracks: list[dict[str, Any]],
        *,
        _save_undo: bool = True,
        _dedupe_candidates: bool = True,
    ) -> None:
        """Replace generated upcoming tracks while preserving user intent.

        Protected entries remain in order. The new route fills the old open
        positions around them, then any additional generated tracks are added
        after the final protected entry. Duplicate candidates are ignored.
        """
        if not self.entries:
            if _save_undo:
                self._undo_generated_tail = []
            seen: set[tuple[str, ...]] = set()
            self.entries = []
            for track in list(tracks or []):
                if not isinstance(track, dict):
                    continue
                key = _track_key(track)
                if _dedupe_candidates and key in seen:
                    continue
                seen.add(key)
                self.entries.append(QueueEntry(dict(track), origin="route"))
            self.current_index = -1
            return

        tail_start = max(0, self.current_index + 1)
        prefix = self.entries[:tail_start]
        tail = self.entries[tail_start:]
        if _save_undo:
            self._undo_generated_tail = [
                dict(entry.track) for entry in tail if not entry.protected
            ]
        protected = [entry.copy() for entry in tail if entry.protected]
        reserved = (
            {_track_key(self.entries[self.current_index].track)}
            if self.current_index >= 0
            else set()
        )
        for entry in protected:
            reserved.add(_track_key(entry.track))

        candidates: list[QueueEntry] = []
        seen_candidates: set[tuple[str, ...]] = set()
        for track in list(tracks or []):
            if not isinstance(track, dict):
                continue
            key = _track_key(track)
            if key in reserved or (
                _dedupe_candidates and key in seen_candidates
            ):
                continue
            seen_candidates.add(key)
            candidates.append(QueueEntry(dict(track), origin="route"))

        new_tail: list[QueueEntry] = []
        cursor = 0
        old_gap = 0
        for old_entry in tail:
            if not old_entry.protected:
                old_gap += 1
                continue
            # Keep roughly the same amount of route space before each anchor.
            available = min(old_gap, max(0, len(candidates) - cursor))
            new_tail.extend(candidates[cursor : cursor + available])
            cursor += available
            old_gap = 0
            new_tail.append(old_entry.copy())
        new_tail.extend(candidates[cursor:])
        self.entries = prefix + new_tail

    @property
    def can_undo_replan(self) -> bool:
        return self._undo_generated_tail is not None

    def undo_replan(self) -> bool:
        """Restore the prior generated tail, keeping current protected choices.

        Only the latest automatic replacement is reversible. The queue's
        current track and any protected entries remain governed by the normal
        replacement rules, so undo remains safe after playback advances or the
        listener adds a manual choice.
        """
        if self._undo_generated_tail is None:
            return False
        previous = self._undo_generated_tail
        self._undo_generated_tail = None
        self.replace_generated_tail(
            previous,
            _save_undo=False,
            _dedupe_candidates=False,
        )
        return True

    def _is_upcoming(self, index: int) -> bool:
        return self.current_index < index < len(self.entries)


__all__ = ["LivingQueue", "QueueEntry", "queue_track_key"]
