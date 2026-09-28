from __future__ import annotations

import json
import urllib.parse
import urllib.request
from typing import Any

from .. import __version__
from ..provider import MusicProvider, ProviderInfo


class JamendoProvider(MusicProvider):
    """Reference legal online provider.

    Users supply their own Jamendo developer client_id. Melodex does not ship a
    shared production credential. Results retain licence and source-page fields
    so the UI can satisfy attribution requirements.
    """

    API = "https://api.jamendo.com/v3.0"

    def __init__(self, client_id: str = ""):
        self.client_id = client_id.strip()

    @property
    def info(self) -> ProviderInfo:
        return ProviderInfo(
            id="jamendo", name="Jamendo (reference provider)",
            description="Independent music published under Creative Commons licences",
            capabilities=["search", "browse", "track", "artist", "album", "playback"],
            permissions={"network_hosts": ["api.jamendo.com", "usercontent.jamendo.com"], "offline_downloads": False, "local_files": False},
        )

    def configure(self, settings: dict[str, Any]) -> None:
        self.client_id = str(settings.get("client_id", self.client_id) or "").strip()

    def _request(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        if not self.client_id:
            raise RuntimeError("Add your Jamendo client ID in Sources → Jamendo settings")
        args = {"client_id": self.client_id, "format": "json", **params}
        url = f"{self.API}/{path}/?" + urllib.parse.urlencode(args, doseq=True)
        req = urllib.request.Request(url, headers={"User-Agent": f"Melodex/{__version__} (reference provider)"})
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.load(r)

    @staticmethod
    def _track(item: dict[str, Any]) -> dict[str, Any]:
        tid = str(item.get("id", ""))
        artist_id = str(item.get("artist_id", ""))
        # Jamendo content pages are the attribution destination required by API terms.
        source_page = str(item.get("shareurl") or (f"https://www.jamendo.com/track/{tid}" if tid else "https://www.jamendo.com/"))
        return {
            "provider_id": "jamendo", "track_id": tid, "rel": f"jamendo:{tid}",
            "title": str(item.get("name") or "Unknown track"),
            "artist": str(item.get("artist_name") or "Unknown artist"),
            "artist_id": artist_id, "album": str(item.get("album_name") or ""),
            "duration": float(item.get("duration") or 0), "artwork": str(item.get("image") or item.get("album_image") or ""),
            "stream_url": str(item.get("audio") or ""), "source": "jamendo",
            "source_page": source_page, "license_url": str(item.get("license_ccurl") or ""),
            "attribution": f"{item.get('artist_name','Unknown artist')} — via Jamendo",
        }

    def search(self, query: str, limit: int = 50) -> list[dict[str, Any]]:
        data = self._request("tracks", {"search": query, "limit": min(200, max(1, limit)), "include": "licenses", "audioformat": "mp32"})
        return [self._track(x) for x in data.get("results", []) if isinstance(x, dict)]

    def browse(self, kind: str = "featured", limit: int = 50) -> list[dict[str, Any]]:
        order = "popularity_total" if kind == "featured" else "releasedate_desc"
        data = self._request("tracks", {"limit": min(200, max(1, limit)), "order": order, "include": "licenses", "audioformat": "mp32"})
        return [self._track(x) for x in data.get("results", []) if isinstance(x, dict)]

    def resolve(self, track: dict[str, Any]) -> dict[str, Any]:
        if track.get("stream_url"):
            return dict(track)
        tid = str(track.get("track_id") or "")
        data = self._request("tracks", {"id": tid, "limit": 1, "include": "licenses", "audioformat": "mp32"})
        results = data.get("results", [])
        if not results:
            raise RuntimeError("Track is no longer available from Jamendo")
        return self._track(results[0])
