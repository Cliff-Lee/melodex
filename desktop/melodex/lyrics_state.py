"""Canonical lyrics state shared by Now Playing and immersive visual presentations."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Mapping


def _line_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _safe_int(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError, OverflowError):
        return 0


@dataclass(frozen=True, slots=True)
class LyricLine:
    time_ms: int
    text: str

    def as_payload(self) -> dict[str, Any]:
        return {"time_ms": self.time_ms, "text": self.text}


@dataclass(frozen=True, slots=True)
class LyricFrame:
    previous: str
    current: str
    following: str
    synced: bool
    source: str
    index: int = -1


@dataclass(frozen=True, slots=True)
class LyricsDocument:
    """Normalized, renderer-safe lyrics document.

    Source-specific payloads are normalized once.  Both the practical reader
    and Lyric Flow consume this same object, so timing/current-line semantics
    cannot drift between the two presentations.
    """

    text: str = ""
    lines: tuple[LyricLine, ...] = ()
    source: str = ""
    instrumental: bool = False
    status: str = ""
    error: str = ""
    cache: str = ""
    provenance: tuple[tuple[str, Any], ...] = ()
    match: tuple[tuple[str, Any], ...] = ()
    user_added: bool = False
    path: str = ""

    @classmethod
    def empty(cls) -> "LyricsDocument":
        return cls()

    @property
    def synced(self) -> bool:
        return bool(self.lines)

    @property
    def has_content(self) -> bool:
        return bool(self.text.strip() or self.lines or self.instrumental)

    @property
    def provenance_dict(self) -> dict[str, Any]:
        return dict(self.provenance)

    @property
    def match_dict(self) -> dict[str, Any]:
        return dict(self.match)

    @property
    def searchable_text(self) -> str:
        if self.text.strip():
            return self.text
        return "\n".join(line.text for line in self.lines if line.text)

    def current_index(self, position_ms: int) -> int:
        if not self.lines:
            return -1
        position = _safe_int(position_ms)
        index = -1
        for i, line in enumerate(self.lines):
            if line.time_ms <= position:
                index = i
            else:
                break
        return index

    def frame(self, position_ms: int, duration_ms: int) -> LyricFrame:
        if self.lines:
            index = self.current_index(position_ms)
            if index < 0:
                return LyricFrame("", "", self.lines[0].text, True, self.source, -1)
            return LyricFrame(
                self.lines[index - 1].text if index > 0 else "",
                self.lines[index].text,
                self.lines[index + 1].text if index + 1 < len(self.lines) else "",
                True,
                self.source,
                index,
            )

        lines = [_line_text(line) for line in re.split(r"[\r\n]+", self.text) if _line_text(line)]
        if not lines:
            return LyricFrame("", "", "", False, self.source, -1)
        position = _safe_int(position_ms)
        duration = _safe_int(duration_ms)
        fraction = min(1.0, position / duration) if duration else 0.0
        index = min(len(lines) - 1, int(fraction * len(lines)))
        return LyricFrame(
            lines[index - 1] if index else "",
            lines[index],
            lines[index + 1] if index + 1 < len(lines) else "",
            False,
            self.source,
            index,
        )

    def as_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "text": self.text,
            "synced": [line.as_payload() for line in self.lines],
            "source": self.source,
        }
        if self.instrumental:
            payload["instrumental"] = True
        if self.status:
            payload["status"] = self.status
        if self.error:
            payload["error"] = self.error
        if self.cache:
            payload["cache"] = self.cache
        if self.provenance:
            payload["provenance"] = dict(self.provenance)
        if self.match:
            payload["match"] = dict(self.match)
        if self.user_added:
            payload["user_added"] = True
        if self.path:
            payload["path"] = self.path
        return payload


def build_lyrics_document(value: LyricsDocument | Mapping[str, Any] | None) -> LyricsDocument:
    if isinstance(value, LyricsDocument):
        return value
    raw = value if isinstance(value, Mapping) else {}

    parsed: list[LyricLine] = []
    for row in raw.get("synced", ()) or ():
        if not isinstance(row, Mapping):
            continue
        parsed.append(LyricLine(_safe_int(row.get("time_ms")), _line_text(row.get("text"))))
    parsed.sort(key=lambda line: line.time_ms)

    provenance = raw.get("provenance")
    match = raw.get("match")
    return LyricsDocument(
        text=str(raw.get("text") or ""),
        lines=tuple(parsed),
        source=str(raw.get("source") or ""),
        instrumental=bool(raw.get("instrumental")),
        status=str(raw.get("status") or ""),
        error=str(raw.get("error") or "").strip(),
        cache=str(raw.get("cache") or ""),
        provenance=tuple(dict(provenance).items()) if isinstance(provenance, Mapping) else (),
        match=tuple(dict(match).items()) if isinstance(match, Mapping) else (),
        user_added=bool(raw.get("user_added")),
        path=str(raw.get("path") or ""),
    )


def lyrics_have_content(value: LyricsDocument | Mapping[str, Any] | None) -> bool:
    return build_lyrics_document(value).has_content


def lyric_frame(
    value: LyricsDocument | Mapping[str, Any] | None,
    position_ms: int,
    duration_ms: int,
) -> LyricFrame:
    return build_lyrics_document(value).frame(position_ms, duration_ms)
