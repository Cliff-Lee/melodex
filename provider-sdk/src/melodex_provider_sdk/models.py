from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class Artist:
    provider_id: str
    provider_artist_id: str
    name: str
    artwork_url: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"type": "artist", **asdict(self)}


@dataclass(slots=True)
class Album:
    provider_id: str
    provider_album_id: str
    title: str
    artist: str = ""
    year: int | None = None
    artwork_url: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"type": "album", **asdict(self)}


@dataclass(slots=True)
class Track:
    provider_id: str
    provider_track_id: str
    title: str
    artist: str = ""
    album: str = ""
    duration_ms: int | None = None
    artwork_url: str | None = None
    isrc: str | None = None
    musicbrainz_recording_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"type": "track", **asdict(self)}


@dataclass(slots=True)
class PlaybackResource:
    kind: str
    url: str
    headers: dict[str, str] = field(default_factory=dict)
    cookies: dict[str, str] = field(default_factory=dict)
    mime_type: str | None = None
    expires_at: str | None = None
    seekable: bool = True
    cache_policy: str = "session"
    refresh_token: str | None = None
    request_timeout_seconds: float = 30.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ProviderError(RuntimeError):
    def __init__(self, code: str, message: str, retryable: bool = False):
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable

    def to_dict(self) -> dict[str, Any]:
        return {
            "error": {
                "code": self.code,
                "message": self.message,
                "retryable": self.retryable,
            }
        }
