from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence


@dataclass(frozen=True)
class ScanActivityState:
    stage: str
    label: str
    progress_min: int
    progress_max: int
    progress_value: int
    progress_format: str
    pause_text: str


def scan_roots_key(roots: Sequence[Path]) -> tuple[str, ...]:
    return tuple(str(Path(root)) for root in roots)


def format_elapsed(seconds: float) -> str:
    total = max(0, int(seconds))
    minutes, seconds = divmod(total, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours:d}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:d}:{seconds:02d}"


def idle_scan_session() -> dict[str, Any]:
    return {
        "status": "idle",
        "running": False,
        "pending_rescan": False,
        "storage_state": "unknown",
    }


def start_scan_session(reason: str, root_count: int) -> dict[str, Any]:
    return {
        "status": "running",
        "reason": str(reason or "scan")[:80],
        "phase": "discovering",
        "running": True,
        "paused": False,
        "pending_rescan": False,
        "elapsed_seconds": 0.0,
        "files_seen": 0,
        "audio_files_seen": 0,
        "directories_seen": 0,
        "completed": 0,
        "total": 0,
        "unchanged": 0,
        "resumed": 0,
        "added": 0,
        "changed": 0,
        "removed": 0,
        "stat_failures": 0,
        "storage_state": "checking",
        "root_count": max(0, int(root_count)),
        "roots_unavailable": 0,
        "roots_incomplete": 0,
        "io_retries": 0,
    }


def scan_progress_patch(
    payload: Mapping[str, Any],
    *,
    elapsed_seconds: float,
    pending_rescan: bool,
) -> dict[str, Any]:
    return {
        "status": "running",
        "running": True,
        "paused": bool(payload.get("paused")),
        "pending_rescan": bool(pending_rescan),
        "elapsed_seconds": round(max(0.0, elapsed_seconds), 3),
        "phase": str(payload.get("phase") or ""),
        "files_seen": int(payload.get("files_seen") or 0),
        "audio_files_seen": int(payload.get("audio_files_seen") or 0),
        "directories_seen": int(payload.get("directories_seen") or 0),
        "completed": int(payload.get("completed") or 0),
        "total": int(payload.get("total") or 0),
        "unchanged": int(payload.get("unchanged") or 0),
        "resumed": int(payload.get("resumed") or 0),
        "added": int(payload.get("added") or 0),
        "changed": int(payload.get("changed") or 0),
        "removed": int(payload.get("removed") or 0),
        "stat_failures": int(payload.get("stat_failures") or 0),
    }


def scan_progress_message(payload: Mapping[str, Any]) -> str | None:
    phase = str(payload.get("phase") or "")
    if phase == "discovering":
        found = int(payload.get("audio_files_seen") or 0)
        return f"Indexing music · discovering files · {found:,} tracks found"

    if phase == "metadata":
        completed = int(payload.get("completed") or 0)
        total = int(payload.get("total") or 0)
        found = int(payload.get("audio_files_seen") or 0)
        unchanged = int(payload.get("unchanged") or 0)
        if total == 0 and completed:
            return (
                "Indexing music · reading metadata as files are found · "
                f"{completed:,} read"
                + (f" · {found:,} found" if found else "")
            )
        if total == 0 and found:
            return (
                "Indexing music · metadata already up to date · "
                f"{unchanged or found:,} reused"
            )
        return f"Indexing music · reading metadata · {completed:,}/{total:,}"

    if phase == "saving":
        return "Indexing music · saving local library index…"
    return None


def scan_activity_state(
    payload: Mapping[str, Any] | None,
    *,
    elapsed_seconds: float,
    paused: bool,
) -> ScanActivityState:
    data = dict(payload or {})
    phase = str(data.get("phase") or "discovering")
    found = max(0, int(data.get("audio_files_seen") or 0))
    completed = max(0, int(data.get("completed") or 0))
    total = max(0, int(data.get("total") or 0))

    progress_min = 0
    progress_max = 0
    progress_value = 0
    progress_format = ""

    if phase == "metadata" and total:
        stage = f"Reading tags · {completed:,}/{total:,}"
        progress_max = total
        progress_value = min(completed, total)
        progress_format = "%v / %m"
    elif phase == "metadata" and completed:
        stage = (
            f"Reading tags while discovering · {completed:,} read"
            + (f" · {found:,} found" if found else "")
        )
    elif phase == "saving":
        stage = "Saving library index"
    else:
        stage = f"Discovering files · {found:,} found" if found else "Discovering files"

    if paused:
        stage = "Paused · " + stage

    elapsed = format_elapsed(elapsed_seconds)
    return ScanActivityState(
        stage=stage,
        label=(
            f"Indexing music · {stage} · {elapsed} elapsed · "
            "You can keep using Melodex"
        ),
        progress_min=progress_min,
        progress_max=progress_max,
        progress_value=progress_value,
        progress_format=progress_format,
        pause_text="Resume" if paused else "Pause",
    )


def scan_change_suffix(changes: Mapping[str, Any]) -> str:
    parts: list[str] = []
    for key, label in (
        ("unchanged", "unchanged"),
        ("added", "new"),
        ("changed", "updated"),
        ("removed", "removed"),
    ):
        value = max(0, int(changes.get(key) or 0))
        if value:
            parts.append(f"{value:,} {label}")
    return (" · " + " · ".join(parts)) if parts else ""
