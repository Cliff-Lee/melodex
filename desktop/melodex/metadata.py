from __future__ import annotations

import hashlib
import html
import json
import re
import threading
import time
import urllib.parse
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

import requests


_MB_BASE = "https://musicbrainz.org/ws/2"
_CAA_BASE = "https://coverartarchive.org"
_WD_ENTITY_BASE = "https://www.wikidata.org/wiki/Special:EntityData"
_WM_FILE_PATH = "https://commons.wikimedia.org/wiki/Special:FilePath"
_WM_API = "https://commons.wikimedia.org/w/api.php"
_WP_API = "https://en.wikipedia.org/w/api.php"
_USER_AGENT = "Melodex/0.1 (https://github.com/Cliff-Lee/melodex)"
_LRC_RE = re.compile(r"\[(?P<m>\d{1,3}):(?P<s>\d{1,2})(?:[\.:](?P<f>\d{1,3}))?\]")
_VERSION_WORDS = re.compile(r"\b(live|remix|acoustic|cover|karaoke|instrumental|demo|edit|remaster(?:ed)?)\b", re.I)


def _norm(value: Any) -> str:
    text = str(value or "").casefold()
    text = re.sub(r"[^\w]+", " ", text, flags=re.UNICODE)
    return " ".join(text.split())


def _ratio(a: Any, b: Any) -> float:
    aa, bb = _norm(a), _norm(b)
    if not aa or not bb:
        return 0.0
    if aa == bb:
        return 1.0
    return SequenceMatcher(None, aa, bb).ratio()


def track_key(track: dict[str, Any]) -> str:
    pid = str(track.get("provider_id") or "")
    tid = str(track.get("track_id") or "")
    if pid and tid:
        return f"{pid}:{tid}"
    return "|".join((_norm(track.get("artist")), _norm(track.get("title")), _norm(track.get("album"))))


def parse_lrc(text: str) -> list[dict[str, Any]]:
    """Parse common LRC timestamps into sorted millisecond lyric lines."""
    out: list[dict[str, Any]] = []
    for raw in str(text or "").splitlines():
        matches = list(_LRC_RE.finditer(raw))
        if not matches:
            continue
        lyric = raw[matches[-1].end():].strip()
        for match in matches:
            minutes = int(match.group("m") or 0)
            seconds = int(match.group("s") or 0)
            frac = str(match.group("f") or "")
            if not frac:
                millis = 0
            elif len(frac) == 1:
                millis = int(frac) * 100
            elif len(frac) == 2:
                millis = int(frac) * 10
            else:
                millis = int(frac[:3])
            out.append({"time_ms": (minutes * 60 + seconds) * 1000 + millis, "text": lyric})
    out.sort(key=lambda row: int(row.get("time_ms") or 0))
    return out


@dataclass(slots=True)
class MetadataIdentity:
    recording_mbid: str = ""
    artist_mbid: str = ""
    release_mbid: str = ""
    release_group_mbid: str = ""
    artist: str = ""
    title: str = ""
    album: str = ""
    date: str = ""
    score: float = 0.0

    def as_dict(self) -> dict[str, Any]:
        return {
            "recording_mbid": self.recording_mbid,
            "artist_mbid": self.artist_mbid,
            "release_mbid": self.release_mbid,
            "release_group_mbid": self.release_group_mbid,
            "artist": self.artist,
            "title": self.title,
            "album": self.album,
            "date": self.date,
            "score": self.score,
        }


class RichMetadataService:
    """Local-first enrichment with a small MusicBrainz/Cover Art cache.

    The service never fetches web lyrics. Lyrics come from user-owned files/tags;
    online lyric services can be added later behind a separate provider interface.
    """

    _mb_lock = threading.Lock()
    _mb_last_request = 0.0

    def __init__(self, data_dir: Path, session: requests.Session | None = None, capability_broker: Any | None = None):
        self.data_dir = Path(data_dir)
        self.cache_dir = self.data_dir / "metadata-cache"
        self.json_cache = self.cache_dir / "json"
        self.art_cache = self.cache_dir / "artwork"
        self.artwork_index_path = self.cache_dir / "artwork-index.json"
        self.json_cache.mkdir(parents=True, exist_ok=True)
        self.art_cache.mkdir(parents=True, exist_ok=True)
        self._artwork_index_lock = threading.Lock()
        self._artwork_index = self._load_artwork_index()
        self.session = session or requests.Session()
        self.capability_broker = capability_broker
        self.session.headers.update({"User-Agent": _USER_AGENT, "Accept": "application/json"})

    # ---------------------------- cache / HTTP
    @staticmethod
    def _hash(value: str) -> str:
        return hashlib.sha256(value.encode("utf-8", errors="ignore")).hexdigest()

    def _cache_path(self, key: str) -> Path:
        return self.json_cache / f"{self._hash(key)}.json"


    def _load_artwork_index(self) -> dict[str, dict[str, Any]]:
        try:
            raw = json.loads(self.artwork_index_path.read_text("utf-8"))
            if not isinstance(raw, dict):
                return {}
            return {
                str(key): dict(value)
                for key, value in raw.items()
                if isinstance(value, dict)
            }
        except Exception:
            return {}

    def _save_artwork_index(self) -> None:
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        temp = self.artwork_index_path.with_suffix(".tmp")
        temp.write_text(
            json.dumps(self._artwork_index, ensure_ascii=False, indent=2),
            "utf-8",
        )
        temp.replace(self.artwork_index_path)

    @staticmethod
    def _album_artwork_keys(track: dict[str, Any]) -> list[str]:
        album = _norm(track.get("album"))
        artist = _norm(track.get("artist"))
        album_artist = _norm(track.get("album_artist"))
        year = str(track.get("year") or "")
        local_path = str(track.get("local_path") or "").strip()
        keys: list[str] = []
        if local_path:
            folder = Path(local_path).expanduser().parent
            if re.fullmatch(r"(?:cd|disc|disk)\s*[-_]?\s*\d+", folder.name, flags=re.I):
                folder = folder.parent
            try:
                folder = folder.resolve()
            except Exception:
                pass
            keys.append("folder:" + _norm(str(folder)))
        if album and album_artist:
            keys.append(f"album-artist:{album_artist}|{album}|{year}")
        if album and artist and artist not in {"unknown artist", "various artists"}:
            keys.append(f"artist-album:{artist}|{album}|{year}")
        if album and year:
            keys.append(f"album-year:{album}|{year}")
        if album and artist in {"", "unknown artist", "various artists"}:
            keys.append(f"album:{album}")
        key = track_key(track)
        if key:
            keys.append("track:" + key)
        return list(dict.fromkeys(key for key in keys if key))

    @staticmethod
    def _artist_artwork_keys(artist: dict[str, Any]) -> list[str]:
        keys: list[str] = []
        qid = str(artist.get("wikidata_qid") or "").strip()
        mbid = str(artist.get("mbid") or artist.get("artist_mbid") or "").strip()
        name = _norm(artist.get("name") or artist.get("artist"))
        if qid:
            keys.append("artist-qid:" + qid)
        if mbid:
            keys.append("artist-mbid:" + mbid)
        if name:
            keys.append("artist-name:" + name)
        return keys

    def _cached_artwork_by_keys(self, keys: list[str]) -> dict[str, Any]:
        for key in keys:
            row = self._artwork_index.get(str(key))
            if not isinstance(row, dict):
                continue
            path = Path(str(row.get("path") or "")).expanduser()
            if path.is_file():
                return dict(row)
        return {}

    def _remember_artwork_by_keys(
        self,
        keys: list[str],
        path: str | Path,
        *,
        source: str = "",
        source_url: str = "",
        attribution: str = "",
        license_name: str = "",
    ) -> dict[str, Any]:
        path_obj = Path(path).expanduser()
        if not path_obj.is_file():
            return {}
        row = {
            "path": str(path_obj),
            "source": str(source or ""),
            "source_url": str(source_url or ""),
            "attribution": str(attribution or ""),
            "license": str(license_name or ""),
        }
        with self._artwork_index_lock:
            for key in keys:
                if key:
                    self._artwork_index[str(key)] = dict(row)
            self._save_artwork_index()
        return dict(row)

    def remember_artwork(
        self,
        track: dict[str, Any],
        path: str | Path,
        *,
        source: str = "",
        source_url: str = "",
        attribution: str = "",
        license_name: str = "",
    ) -> dict[str, Any]:
        return self._remember_artwork_by_keys(
            self._album_artwork_keys(track),
            path,
            source=source,
            source_url=source_url,
            attribution=attribution,
            license_name=license_name,
        )

    def cached_artist_photo(self, artist: dict[str, Any]) -> dict[str, Any]:
        return self._cached_artwork_by_keys(self._artist_artwork_keys(artist))

    def remember_artist_photo_file(
        self,
        artist: dict[str, Any],
        source_path: str | Path,
    ) -> dict[str, Any]:
        source=Path(source_path).expanduser()
        if not source.is_file():
            return {}
        try:
            data=source.read_bytes()
        except Exception:
            return {}
        suffix=source.suffix.lower()
        if suffix not in {".jpg",".jpeg",".png",".webp"}:
            return {}
        target=self.art_cache / (
            "artist-user-" + hashlib.sha256(data).hexdigest()[:24] + suffix
        )
        try:
            if not target.exists():
                target.write_bytes(data)
        except Exception:
            return {}
        return self._remember_artwork_by_keys(
            self._artist_artwork_keys(artist),
            target,
            source="User-selected artist photo",
        )


    def _cached_json(self, key: str, max_age: float) -> Any | None:
        path = self._cache_path(key)
        try:
            if not path.exists() or time.time() - path.stat().st_mtime > max_age:
                return None
            return json.loads(path.read_text("utf-8"))
        except Exception:
            return None

    def _save_json(self, key: str, value: Any) -> None:
        path = self._cache_path(key)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(value, ensure_ascii=False), "utf-8")
        tmp.replace(path)

    def _mb_json(self, path: str, params: dict[str, Any], max_age: float = 30 * 86400) -> dict[str, Any]:
        query = urllib.parse.urlencode(sorted((str(k), str(v)) for k, v in params.items()))
        key = f"mb:{path}?{query}"
        cached = self._cached_json(key, max_age)
        if isinstance(cached, dict):
            return cached
        with self._mb_lock:
            wait = 1.05 - (time.monotonic() - self.__class__._mb_last_request)
            if wait > 0:
                time.sleep(wait)
            response = self.session.get(f"{_MB_BASE}/{path.lstrip('/')}", params=params, timeout=12)
            self.__class__._mb_last_request = time.monotonic()
        response.raise_for_status()
        data = response.json()
        if isinstance(data, dict):
            self._save_json(key, data)
            return data
        return {}

    def _caa_json(self, path: str, max_age: float = 30 * 86400) -> dict[str, Any]:
        key = f"caa:{path}"
        cached = self._cached_json(key, max_age)
        if isinstance(cached, dict):
            return cached
        response = self.session.get(f"{_CAA_BASE}/{path.lstrip('/')}", timeout=12)
        if response.status_code == 404:
            self._save_json(key, {})
            return {}
        response.raise_for_status()
        data = response.json()
        if isinstance(data, dict):
            self._save_json(key, data)
            return data
        return {}

    # ---------------------------- local lyrics / artwork
    def local_lyrics(self, track: dict[str, Any]) -> dict[str, Any]:
        path_text = str(track.get("local_path") or "")
        if not path_text:
            return {"text": "", "synced": [], "source": ""}
        path = Path(path_text)
        if not path.exists():
            return {"text": "", "synced": [], "source": ""}

        for ext in (".lrc", ".txt"):
            sidecar = path.with_suffix(ext)
            if sidecar.exists():
                try:
                    text = sidecar.read_text("utf-8-sig", errors="replace")
                    synced = parse_lrc(text) if ext == ".lrc" else []
                    plain = "\n".join(row["text"] for row in synced if row.get("text")) if synced else text.strip()
                    return {"text": plain, "synced": synced, "source": sidecar.name}
                except Exception:
                    pass

        try:
            from mutagen import File
            audio = File(path, easy=False)
            tags = getattr(audio, "tags", None)
            if tags:
                # ID3: synchronized lyrics first, then unsynchronized lyrics.
                if hasattr(tags, "getall"):
                    for frame in tags.getall("SYLT"):
                        rows = []
                        for entry in getattr(frame, "text", []) or []:
                            if isinstance(entry, (tuple, list)) and len(entry) >= 2:
                                lyric, stamp = entry[0], entry[1]
                                rows.append({"time_ms": int(stamp), "text": str(lyric)})
                        if rows:
                            return {"text": "\n".join(x["text"] for x in rows), "synced": rows, "source": "embedded SYLT"}
                    frames = tags.getall("USLT")
                    if frames:
                        text = str(getattr(frames[0], "text", "") or "").strip()
                        if text:
                            synced = parse_lrc(text)
                            return {"text": "\n".join(x["text"] for x in synced) if synced else text, "synced": synced, "source": "embedded lyrics"}

                for key in ("LYRICS", "UNSYNCEDLYRICS", "lyrics", "\xa9lyr"):
                    try:
                        value = tags.get(key)
                    except Exception:
                        value = None
                    if not value:
                        continue
                    if isinstance(value, (list, tuple)):
                        value = value[0] if value else ""
                    text = str(value or "").strip()
                    if text:
                        synced = parse_lrc(text)
                        return {"text": "\n".join(x["text"] for x in synced) if synced else text, "synced": synced, "source": "embedded lyrics"}
        except Exception:
            pass
        return {"text": "", "synced": [], "source": ""}

    def _embedded_artwork(self, track: dict[str, Any]) -> Path | None:
        path_text = str(track.get("local_path") or "")
        if not path_text:
            return None
        path = Path(path_text)
        if not path.exists():
            return None
        try:
            from mutagen import File
            audio = File(path, easy=False)
            blob: bytes | None = None
            mime = "image/jpeg"
            pictures = getattr(audio, "pictures", None)
            if pictures:
                pic = pictures[0]
                blob = bytes(getattr(pic, "data", b"") or b"")
                mime = str(getattr(pic, "mime", mime) or mime)
            tags = getattr(audio, "tags", None)
            if blob is None and tags is not None and hasattr(tags, "getall"):
                frames = tags.getall("APIC")
                if frames:
                    blob = bytes(getattr(frames[0], "data", b"") or b"")
                    mime = str(getattr(frames[0], "mime", mime) or mime)
            if blob is None and tags:
                cover = tags.get("covr") or tags.get("artwork")
                if isinstance(cover, (list, tuple)) and cover:
                    blob = bytes(cover[0])
            if not blob:
                return None
            ext = ".png" if "png" in mime.casefold() else ".jpg"
            out = self.art_cache / f"embedded-{self._hash(str(path.resolve()) + str(path.stat().st_mtime_ns))}{ext}"
            if not out.exists():
                out.write_bytes(blob)
            return out
        except Exception:
            return None

    def local_artwork(self, track: dict[str, Any]) -> dict[str, Any]:
        """Return local/embedded cover art without making a network request."""
        supplied = str(track.get("artwork") or "").strip()
        if supplied:
            path = Path(supplied).expanduser()
            if path.is_file():
                return {"path": str(path), "source": "track artwork", "source_url": ""}

        local_path = str(track.get("local_path") or "").strip()
        if local_path:
            folder = Path(local_path).expanduser().parent
            folders = [folder]
            if re.fullmatch(r"(?:cd|disc|disk)\s*[-_]?\s*\d+", folder.name, flags=re.I):
                folders.append(folder.parent)
            for candidate_folder in folders:
                try:
                    files = {
                        item.name.casefold(): item
                        for item in candidate_folder.iterdir()
                        if item.is_file()
                    }
                    for name in (
                        "cover.jpg", "cover.jpeg", "cover.png", "cover.webp",
                        "folder.jpg", "folder.jpeg", "folder.png", "folder.webp",
                        "front.jpg", "front.jpeg", "front.png", "front.webp",
                    ):
                        path = files.get(name)
                        if path is not None:
                            return {"path": str(path), "source": "local cover file", "source_url": ""}
                except Exception:
                    continue

        embedded = self._embedded_artwork(track)
        if embedded:
            return {"path": str(embedded), "source": "embedded artwork", "source_url": ""}

        remembered = self._cached_artwork_by_keys(self._album_artwork_keys(track))
        if remembered:
            return remembered
        return {"path": "", "source": "", "source_url": ""}

    def _download_artwork(self, url: str) -> Path | None:
        if not str(url or "").startswith(("https://", "http://")):
            return None
        key = self._hash(url)
        existing = next(iter(self.art_cache.glob(f"web-{key}.*")), None)
        if existing and existing.exists():
            return existing
        try:
            response = self.session.get(url, timeout=15, headers={"Accept": "image/*", "User-Agent": _USER_AGENT})
            response.raise_for_status()
            ctype = str(response.headers.get("Content-Type") or "").casefold()
            ext = ".png" if "png" in ctype else ".webp" if "webp" in ctype else ".jpg"
            out = self.art_cache / f"web-{key}{ext}"
            out.write_bytes(response.content)
            return out
        except Exception:
            return None

    # ---------------------------- MusicBrainz matching
    def identify(self, track: dict[str, Any]) -> MetadataIdentity:
        existing = str(track.get("musicbrainz_recording_id") or track.get("recording_mbid") or "").strip()
        if existing:
            return MetadataIdentity(
                recording_mbid=existing,
                artist_mbid=str(track.get("musicbrainz_artist_id") or track.get("artist_mbid") or ""),
                release_mbid=str(track.get("musicbrainz_release_id") or track.get("release_mbid") or ""),
                release_group_mbid=str(track.get("musicbrainz_release_group_id") or track.get("release_group_mbid") or ""),
                artist=str(track.get("artist") or ""), title=str(track.get("title") or ""), album=str(track.get("album") or ""), score=1.0,
            )
        title = str(track.get("title") or "").strip()
        artist = str(track.get("artist") or "").strip()
        album = str(track.get("album") or "").strip()
        artist_known = _norm(artist) not in {"", "unknown artist", "unknown", "various artists"}
        if not title and not album:
            return MetadataIdentity(artist=artist, title=title, album=album)

        terms=[]
        if title:
            terms.append(f'recording:"{title}"')
        if artist_known:
            terms.append(f'artist:"{artist}"')
        elif album:
            terms.append(f'release:"{album}"')
        query = " AND ".join(terms)
        data = self._mb_json("recording/", {"query": query, "fmt": "json", "limit": 10}, 21 * 86400)
        best: tuple[float, dict[str, Any], dict[str, Any] | None] | None = None
        for rec in list(data.get("recordings") or []):
            if not isinstance(rec, dict):
                continue
            credited = "".join(str(x.get("name") or "") + str(x.get("joinphrase") or "") for x in list(rec.get("artist-credit") or []) if isinstance(x, dict)).strip()
            title_score = _ratio(title, rec.get("title")) if title else 0.75
            artist_score = _ratio(artist, credited) if artist_known else 0.75
            releases = [x for x in list(rec.get("releases") or []) if isinstance(x, dict)]
            release = max(releases, key=lambda x: _ratio(album, x.get("title"))) if releases and album else (releases[0] if releases else None)
            album_score = _ratio(album, (release or {}).get("title")) if album else 0.75
            if artist_known:
                score = 0.55 * title_score + 0.35 * artist_score + 0.10 * album_score
                threshold = 0.62
            else:
                score = 0.68 * title_score + 0.32 * album_score
                threshold = 0.72
            requested_flags = set(_VERSION_WORDS.findall(title))
            candidate_flags = set(_VERSION_WORDS.findall(str(rec.get("title") or "")))
            if requested_flags != candidate_flags and (requested_flags or candidate_flags):
                score -= 0.10
            if best is None or score > best[0]:
                best = (score, rec, release)
        if not best or best[0] < threshold:
            return MetadataIdentity(artist=artist, title=title, album=album, score=max(0.0, best[0] if best else 0.0))
        score, rec, release = best
        credit = list(rec.get("artist-credit") or [])
        artist_obj = next((x.get("artist") for x in credit if isinstance(x, dict) and isinstance(x.get("artist"), dict)), {}) or {}
        rg = (release or {}).get("release-group") if isinstance((release or {}).get("release-group"), dict) else {}
        return MetadataIdentity(
            recording_mbid=str(rec.get("id") or ""),
            artist_mbid=str(artist_obj.get("id") or ""),
            release_mbid=str((release or {}).get("id") or ""),
            release_group_mbid=str((rg or {}).get("id") or ""),
            artist=str(artist_obj.get("name") or artist), title=str(rec.get("title") or title),
            album=str((release or {}).get("title") or album), date=str((release or {}).get("date") or ""), score=float(score),
        )

    def resolve_artist(self, name: str) -> dict[str, Any]:
        """Resolve an artist name conservatively through MusicBrainz.

        This is used only for explicit artist-photo enrichment when a local
        track did not already supply an artist MBID. Exact/near-exact names
        are preferred and ambiguous matches are rejected.
        """
        name = str(name or "").strip()
        if not name or _norm(name) in {"unknown artist", "unknown", "various artists"}:
            return {}
        data = self._mb_json(
            "artist/",
            {"query": f'artist:"{name}"', "fmt": "json", "limit": 8},
            45 * 86400,
        )
        best: tuple[float, dict[str, Any]] | None = None
        for row in list(data.get("artists") or []):
            if not isinstance(row, dict):
                continue
            score = _ratio(name, row.get("name"))
            for alias in list(row.get("aliases") or []):
                if isinstance(alias, dict):
                    score = max(score, _ratio(name, alias.get("name")))
            if best is None or score > best[0]:
                best = (score, row)
        if not best or best[0] < 0.88:
            return {}
        mbid = str(best[1].get("id") or "").strip()
        if not mbid:
            return {}
        info = self.artist_info(mbid)
        if not info:
            return {}
        info["match_score"] = float(best[0])
        return info

    def artist_info(self, artist_mbid: str) -> dict[str, Any]:
        if not artist_mbid:
            return {}
        data = self._mb_json(
            f"artist/{artist_mbid}",
            {"fmt": "json", "inc": "aliases+genres+tags+url-rels+artist-rels"},
            45 * 86400,
        )
        area = data.get("area") if isinstance(data.get("area"), dict) else {}
        begin_area = data.get("begin-area") if isinstance(data.get("begin-area"), dict) else {}
        life = data.get("life-span") if isinstance(data.get("life-span"), dict) else {}
        genres = [str(x.get("name") or "") for x in list(data.get("genres") or []) if isinstance(x, dict) and x.get("name")]
        if not genres:
            genres = [str(x.get("name") or "") for x in list(data.get("tags") or []) if isinstance(x, dict) and x.get("name")][:8]
        members: list[dict[str, Any]] = []
        related: list[dict[str, Any]] = []
        links: list[dict[str, str]] = []
        for rel in list(data.get("relations") or []):
            if not isinstance(rel, dict):
                continue
            typ = str(rel.get("type") or "")
            target = rel.get("artist") if isinstance(rel.get("artist"), dict) else None
            if target:
                row = {"type": typ, "name": str(target.get("name") or ""), "id": str(target.get("id") or ""), "ended": bool(rel.get("ended"))}
                if "member" in typ.casefold():
                    members.append(row)
                elif row["name"]:
                    related.append(row)
            url = rel.get("url") if isinstance(rel.get("url"), dict) else None
            if url and url.get("resource"):
                links.append({"type": typ, "url": str(url.get("resource"))})
        return {
            "mbid": str(data.get("id") or artist_mbid), "name": str(data.get("name") or ""),
            "sort_name": str(data.get("sort-name") or ""), "type": str(data.get("type") or ""),
            "country": str(data.get("country") or ""), "area": str(area.get("name") or ""),
            "begin_area": str(begin_area.get("name") or ""), "begin": str(life.get("begin") or ""),
            "end": str(life.get("end") or ""), "ended": bool(life.get("ended")),
            "disambiguation": str(data.get("disambiguation") or ""), "genres": genres[:10],
            "members": members[:30], "related": related[:20], "links": links[:20],
            "wikidata_qid": self._extract_wikidata_qid({"links": links}),
        }

    def recording_credits(self, recording_mbid: str) -> list[dict[str, str]]:
        if not recording_mbid:
            return []
        data = self._mb_json(
            f"recording/{recording_mbid}",
            {"fmt": "json", "inc": "artist-rels+work-rels+releases+release-groups"},
            45 * 86400,
        )
        rows: list[dict[str, str]] = []
        for rel in list(data.get("relations") or []):
            if not isinstance(rel, dict):
                continue
            typ = str(rel.get("type") or "credit").replace("_", " ").strip()
            kind = "artist"
            target = rel.get("artist") if isinstance(rel.get("artist"), dict) else None
            if target is None and isinstance(rel.get("work"), dict):
                target = rel.get("work")
                kind = "work"
            if not target:
                continue
            name = str(target.get("name") or target.get("title") or "")
            if name:
                rows.append(
                    {
                        "role": typ,
                        "name": name,
                        "mbid": str(target.get("id") or ""),
                        "kind": kind,
                    }
                )
        # De-duplicate while keeping the most useful order from MusicBrainz.
        seen: set[tuple[str, str]] = set()
        out: list[dict[str, str]] = []
        for row in rows:
            key = (row["role"].casefold(), row["name"].casefold())
            if key not in seen:
                seen.add(key); out.append(row)
        return out[:40]

    # ---------------------------- artwork
    @staticmethod
    def _front_image(data: dict[str, Any]) -> tuple[str, str]:
        images = [x for x in list(data.get("images") or []) if isinstance(x, dict)]
        image = next((x for x in images if bool(x.get("front"))), images[0] if images else None)
        if not image:
            return "", ""
        thumbs = image.get("thumbnails") if isinstance(image.get("thumbnails"), dict) else {}
        url = str(thumbs.get("500") or thumbs.get("1200") or thumbs.get("250") or image.get("image") or "")
        return url, str(image.get("comment") or "")

    @staticmethod
    def _extract_wikidata_qid(artist: dict[str, Any]) -> str:
        explicit=str(artist.get("wikidata_qid") or "").strip()
        if re.fullmatch(r"Q\d+",explicit):
            return explicit
        for row in list(artist.get("links") or []):
            if not isinstance(row, dict):
                continue
            url = str(row.get("url") or "")
            m = re.search(r"wikidata\.org/(?:wiki/)?(Q\d+)", url)
            if m:
                return m.group(1)
        return ""

    def _remote_json(self, key: str, url: str, max_age: float = 45 * 86400) -> dict[str, Any]:
        cached = self._cached_json(key, max_age)
        if isinstance(cached, dict):
            return cached
        response = self.session.get(url, timeout=15, headers={"Accept": "application/json", "User-Agent": _USER_AGENT})
        response.raise_for_status()
        data = response.json()
        if isinstance(data, dict):
            self._save_json(key, data)
            return data
        return {}

    @staticmethod
    def _plain_extmetadata(value: Any) -> str:
        """Turn Commons extmetadata HTML into safe plain text for display."""
        if isinstance(value, dict):
            value = value.get("value") or ""
        text = str(value or "")
        text = re.sub(r"<br\s*/?>", " · ", text, flags=re.I)
        text = re.sub(r"<[^>]+>", "", text)
        return " ".join(html.unescape(text).split())

    @staticmethod
    def _meta_value(extmetadata: dict[str, Any], key: str) -> str:
        value = extmetadata.get(key) if isinstance(extmetadata, dict) else None
        return RichMetadataService._plain_extmetadata(value)

    def _commons_file_info(self, image_name: str) -> dict[str, Any]:
        """Fetch the actual Commons file URL and machine-readable credit/licence metadata."""
        image_name = str(image_name or "").strip()
        if not image_name:
            return {}
        key = f"commons-file:{image_name.casefold()}"
        cached = self._cached_json(key, 45 * 86400)
        if isinstance(cached, dict):
            return cached
        params = {
            "action": "query",
            "format": "json",
            "formatversion": "2",
            "prop": "imageinfo",
            "titles": f"File:{image_name}",
            "iiprop": "url|extmetadata",
            "iiurlwidth": "640",
            "iiextmetadatalanguage": "en",
            "iiextmetadatafilter": "Artist|Credit|Attribution|LicenseShortName|LicenseUrl|UsageTerms|Copyrighted|AttributionRequired",
        }
        response = self.session.get(_WM_API, params=params, timeout=15, headers={"Accept": "application/json", "User-Agent": _USER_AGENT})
        response.raise_for_status()
        payload = response.json()
        pages = ((payload.get("query") or {}).get("pages") if isinstance(payload, dict) else None) or []
        page = pages[0] if pages and isinstance(pages[0], dict) else {}
        info_rows = page.get("imageinfo") if isinstance(page.get("imageinfo"), list) else []
        info = info_rows[0] if info_rows and isinstance(info_rows[0], dict) else {}
        ext = info.get("extmetadata") if isinstance(info.get("extmetadata"), dict) else {}
        direct_url = str(info.get("thumburl") or info.get("url") or "")
        description_url = str(info.get("descriptionurl") or "")
        if not description_url:
            description_url = "https://commons.wikimedia.org/wiki/File:" + urllib.parse.quote(image_name.replace(" ", "_"))
        result = {
            "image_url": direct_url,
            "description_url": description_url,
            "creator": self._meta_value(ext, "Artist"),
            "credit": self._meta_value(ext, "Credit"),
            "explicit_attribution": self._meta_value(ext, "Attribution"),
            "license_name": self._meta_value(ext, "LicenseShortName") or self._meta_value(ext, "UsageTerms"),
            "license_url": self._meta_value(ext, "LicenseUrl"),
            "usage_terms": self._meta_value(ext, "UsageTerms"),
            "copyrighted": self._meta_value(ext, "Copyrighted"),
            "attribution_required": self._meta_value(ext, "AttributionRequired"),
        }
        self._save_json(key, result)
        return result

    @staticmethod
    def _commons_credit_line(info: dict[str, Any]) -> str:
        explicit = str(info.get("explicit_attribution") or "").strip()
        if explicit:
            return explicit
        creator = str(info.get("creator") or "").strip()
        credit = str(info.get("credit") or "").strip()
        license_name = str(info.get("license_name") or "").strip()
        parts: list[str] = []
        if creator:
            parts.append(creator)
        if credit and credit.casefold() not in {creator.casefold(), "own work"}:
            parts.append(credit)
        parts.append("Wikimedia Commons")
        if license_name:
            parts.append(license_name)
        return " / ".join(dict.fromkeys(x for x in parts if x))

    @staticmethod
    def _artist_photo_filename_ok(image_name: str) -> bool:
        name=_norm(Path(str(image_name or "")).stem)
        if not name:
            return False
        blocked={
            "logo","wordmark","signature","album","cover","poster",
            "artwork","record sleeve","vinyl","compact disc",
        }
        return not any(token in name for token in blocked)

    @staticmethod
    def _wikipedia_link(artist: dict[str, Any], entity: dict[str, Any]) -> tuple[str, str]:
        sitelinks=entity.get("sitelinks") if isinstance(entity,dict) else {}
        if isinstance(sitelinks,dict):
            preferred=[
                "enwiki","dewiki","frwiki","eswiki","itwiki","ptwiki",
                "nlwiki","svwiki","nowiki","plwiki","ruwiki","jawiki",
                "kowiki","zhwiki",
            ]
            ordered=preferred + sorted(
                key
                for key in sitelinks
                if key.endswith("wiki") and key not in preferred
            )
            for key in ordered:
                row=sitelinks.get(key)
                if not isinstance(row,dict) or not row.get("title"):
                    continue
                lang=key[:-4]
                if not re.fullmatch(r"[a-z0-9-]+",lang):
                    continue
                title=str(row.get("title") or "").strip()
                api=_WP_API if lang=="en" else f"https://{lang}.wikipedia.org/w/api.php"
                return api,title

        for row in list(artist.get("links") or []):
            if not isinstance(row,dict):
                continue
            url=str(row.get("url") or "").strip()
            match=re.match(
                r"https?://(?P<lang>[a-z0-9-]+)\.wikipedia\.org/wiki/(?P<title>[^#?]+)",
                url,
                flags=re.I,
            )
            if not match:
                continue
            lang=match.group("lang")
            title=urllib.parse.unquote(match.group("title")).replace("_"," ")
            return f"https://{lang}.wikipedia.org/w/api.php", title
        return "", ""

    def _wikipedia_artist_page_by_name(
        self,
        artist: dict[str, Any],
    ) -> tuple[str, str]:
        """Find a likely English Wikipedia artist page without blind guessing."""
        artist_name=str(artist.get("name") or artist.get("artist") or "").strip()
        tokens=[x for x in _norm(artist_name).split() if x]
        if not artist_name or not tokens:
            return "", ""

        hints=[]
        artist_type=_norm(artist.get("type"))
        if artist_type == "group":
            hints.append("band")
        elif artist_type == "person":
            hints.append("musician")
        disambiguation=str(artist.get("disambiguation") or "").strip()
        if disambiguation:
            hints.append(disambiguation)
        query=" ".join([f'"{artist_name}"', *(hints or ["music"])])

        params={
            "action":"query",
            "format":"json",
            "formatversion":"2",
            "list":"search",
            "srlimit":"8",
            "srsearch":query,
        }
        url=_WP_API+"?"+urllib.parse.urlencode(params)
        data=self._remote_json(
            f"wikipedia-artist-search:{artist_name.casefold()}:{'|'.join(hints).casefold()}",
            url,
            45 * 86400,
        )
        rows=((data.get("query") or {}).get("search") if isinstance(data,dict) else None) or []
        music_hints={
            "musician","singer","band","rapper","producer","composer","dj",
            "musical","electronic","rock","hip hop","jazz","folk","ambient",
        }

        best: tuple[float,str] | None=None
        for row in rows:
            if not isinstance(row,dict):
                continue
            title=str(row.get("title") or "").strip()
            if not title:
                continue
            base=re.sub(r"\s*\([^)]*\)\s*$","",title).strip()
            title_score=max(_ratio(artist_name,title),_ratio(artist_name,base))
            snippet=_norm(self._plain_extmetadata(row.get("snippet") or ""))
            has_music_hint=any(hint in snippet for hint in music_hints)
            exact=_norm(base)==_norm(artist_name)

            # Multi-word exact titles can pass with a weaker snippet. Common or
            # single-word stage names must look explicitly musical.
            if len(tokens)==1 and not has_music_hint:
                continue
            if not exact and (title_score < 0.90 or not has_music_hint):
                continue

            score=title_score + (0.25 if exact else 0.0) + (0.15 if has_music_hint else 0.0)
            if best is None or score > best[0]:
                best=(score,title)
        return (_WP_API,best[1]) if best else ("","")

    def _wikipedia_page_image(
        self,
        artist: dict[str, Any],
        entity: dict[str, Any],
    ) -> tuple[str, str]:
        api,title=self._wikipedia_link(artist,entity)
        if not api or not title:
            api,title=self._wikipedia_artist_page_by_name(artist)
        if not api or not title:
            return "", ""
        params={
            "action":"query",
            "format":"json",
            "formatversion":"2",
            "redirects":"1",
            "prop":"pageimages",
            "piprop":"name",
            "pilicense":"free",
            "titles":title,
        }
        url=api+"?"+urllib.parse.urlencode(params)
        data=self._remote_json(
            f"wikipedia-pageimage:{api}:{title.casefold()}",
            url,
            45 * 86400,
        )
        pages=((data.get("query") or {}).get("pages") if isinstance(data,dict) else None) or []
        page=pages[0] if pages and isinstance(pages[0],dict) else {}
        image_name=str(page.get("pageimage") or "").strip()
        if image_name and self._artist_photo_filename_ok(image_name):
            page_title=str(page.get("title") or title)
            lang_match=re.match(r"https?://(?P<lang>[a-z0-9-]+)\.wikipedia\.org",api,re.I)
            lang=lang_match.group("lang") if lang_match else "en"
            page_url=(
                f"https://{lang}.wikipedia.org/wiki/"
                + urllib.parse.quote(page_title.replace(" ","_"))
            )
            return image_name,page_url
        return "", ""

    def _commons_artist_image(self, artist_name: str) -> tuple[str, str]:
        """Last-resort free-image search with conservative matching.

        This deliberately avoids general web image search. Candidates must
        contain the artist name and look music-related, and album/logo artwork
        is rejected.
        """
        artist_name=str(artist_name or "").strip()
        tokens=[x for x in _norm(artist_name).split() if len(x)>1]
        if not artist_name or not tokens:
            return "", ""

        params={
            "action":"query",
            "format":"json",
            "formatversion":"2",
            "list":"search",
            "srnamespace":"6",
            "srlimit":"12",
            "srsearch":f'"{artist_name}" musician singer band performer',
        }
        response=self.session.get(
            _WM_API,
            params=params,
            timeout=15,
            headers={"Accept":"application/json","User-Agent":_USER_AGENT},
        )
        response.raise_for_status()
        payload=response.json()
        rows=((payload.get("query") or {}).get("search") if isinstance(payload,dict) else None) or []
        music_hints={
            "musician","singer","band","rapper","producer","composer",
            "performer","concert","festival","dj","music",
        }
        best: tuple[float,str,str] | None=None
        for row in rows:
            if not isinstance(row,dict):
                continue
            title=str(row.get("title") or "")
            image_name=title.split(":",1)[1] if ":" in title else title
            if not self._artist_photo_filename_ok(image_name):
                continue
            snippet=self._plain_extmetadata(row.get("snippet") or "")
            haystack=_norm(image_name+" "+snippet)
            if not all(token in haystack for token in tokens):
                continue
            words=set(haystack.split())
            has_music_hint=bool(words & music_hints)
            # Single-word stage names such as Bonobo are especially ambiguous.
            if len(tokens)==1 and not has_music_hint:
                continue
            filename_norm=_norm(Path(image_name).stem)
            score=_ratio(artist_name,filename_norm)
            if has_music_hint:
                score+=0.25
            if _norm(artist_name) in filename_norm:
                score+=0.25
            if score < 0.70:
                continue
            description_url=(
                "https://commons.wikimedia.org/wiki/File:"
                + urllib.parse.quote(image_name.replace(" ","_"))
            )
            candidate=(score,image_name,description_url)
            if best is None or candidate[0] > best[0]:
                best=candidate
        return (best[1],best[2]) if best else ("","")

    def _artist_photo_from_commons(
        self,
        artist: dict[str, Any],
        image_name: str,
        *,
        qid: str = "",
        discovery_source: str = "",
    ) -> dict[str, Any]:
        empty = {
            "path":"", "source":"", "source_url":"", "attribution":"",
            "wikidata_qid":qid, "filename":"", "creator":"", "credit":"",
            "license_name":"", "license_url":"", "description_url":"",
            "attribution_required":"", "copyrighted":"",
        }
        image_name=str(image_name or "").strip()
        if not image_name or not self._artist_photo_filename_ok(image_name):
            return empty
        commons=self._commons_file_info(image_name)
        image_url=str(commons.get("image_url") or "")
        if not image_url:
            return empty
        downloaded=self._download_artwork(image_url)
        result={
            **empty,
            "path":str(downloaded or ""),
            "source":"Wikimedia Commons",
            "source_url":str(commons.get("description_url") or image_url),
            "description_url":str(commons.get("description_url") or ""),
            "attribution":self._commons_credit_line(commons),
            "wikidata_qid":qid,
            "filename":image_name,
            "creator":str(commons.get("creator") or ""),
            "credit":str(commons.get("credit") or ""),
            "license_name":str(commons.get("license_name") or ""),
            "license_url":str(commons.get("license_url") or ""),
            "attribution_required":str(commons.get("attribution_required") or ""),
            "copyrighted":str(commons.get("copyrighted") or ""),
            "discovery_source":str(discovery_source or ""),
        }
        if downloaded:
            keys=self._artist_artwork_keys({**artist,"wikidata_qid":qid})
            self._remember_artwork_by_keys(
                keys,
                downloaded,
                source="Wikimedia Commons",
                source_url=str(commons.get("description_url") or image_url),
                attribution=str(result.get("attribution") or ""),
                license_name=str(result.get("license_name") or ""),
            )
        return result

    def artist_photo(self, artist: dict[str, Any]) -> dict[str, Any]:
        remembered=self.cached_artist_photo(artist)
        if remembered:
            return {
                **remembered,
                "wikidata_qid":str(artist.get("wikidata_qid") or ""),
                "filename":"",
                "creator":"",
                "credit":"",
                "license_name":str(remembered.get("license") or ""),
                "license_url":"",
                "description_url":str(remembered.get("source_url") or ""),
                "attribution_required":"",
                "copyrighted":"",
                "discovery_source":"cache",
            }

        working=dict(artist or {})
        artist_name=str(working.get("name") or working.get("artist") or "").strip()
        qid=self._extract_wikidata_qid(working)
        if not qid and artist_name and not working.get("links"):
            try:
                resolved=self.resolve_artist(artist_name)
            except Exception:
                resolved={}
            if resolved:
                working={**working,**resolved}
                qid=self._extract_wikidata_qid(working)

        empty={
            "path":"", "source":"", "source_url":"", "attribution":"",
            "wikidata_qid":qid, "filename":"", "creator":"", "credit":"",
            "license_name":"", "license_url":"", "description_url":"",
            "attribution_required":"", "copyrighted":"",
            "discovery_source":"",
        }
        entity={}
        if qid:
            try:
                data=self._remote_json(
                    f"wikidata:{qid}",
                    f"{_WD_ENTITY_BASE}/{qid}.json",
                )
                entity=(data.get("entities") or {}).get(qid) if isinstance(data.get("entities"),dict) else {}
            except Exception:
                entity={}

        # 1. Wikidata's explicit image claim is the strongest free-image match.
        if isinstance(entity,dict):
            claims=entity.get("claims") if isinstance(entity.get("claims"),dict) else {}
            try:
                p18=list(claims.get("P18") or [])
                mainsnak=p18[0].get("mainsnak") if p18 and isinstance(p18[0],dict) else {}
                datavalue=mainsnak.get("datavalue") if isinstance(mainsnak,dict) else {}
                image_name=str(datavalue.get("value") or "") if isinstance(datavalue,dict) else ""
            except Exception:
                image_name=""
            if image_name:
                result=self._artist_photo_from_commons(
                    working,image_name,qid=qid,discovery_source="Wikidata portrait",
                )
                if result.get("path"):
                    return result

        # 2. Wikipedia often has a freely licensed lead image even when the
        # Wikidata P18 field is empty.
        try:
            image_name,page_url=self._wikipedia_page_image(working,entity)
        except Exception:
            image_name,page_url="",""
        if image_name:
            result=self._artist_photo_from_commons(
                working,image_name,qid=qid,discovery_source="Wikipedia lead image",
            )
            if result.get("path"):
                if page_url:
                    result["wikipedia_url"]=page_url
                return result

        # 3. Optional artwork extensions may know artist portraits from
        # additional user-chosen sources. The capability contract keeps
        # provenance attached and avoids baking another service into core.
        broker=self.capability_broker
        if broker is not None:
            try:
                subject=broker.entity_ref(
                    {"artist":artist_name,"name":artist_name},
                    {
                        "artist":artist_name,
                        "artist_mbid":str(working.get("mbid") or ""),
                        "wikidata_id":qid,
                    },
                    entity_type="artist",
                )
                lookup=broker.lookup_artwork(
                    subject,
                    roles=["portrait","thumbnail"],
                    max_results=8,
                )
                for asset in list(lookup.get("assets") or []):
                    if not isinstance(asset,dict):
                        continue
                    url=str(asset.get("url") or "").strip()
                    if not url:
                        continue
                    role=_norm(asset.get("role"))
                    if role and role not in {"portrait","thumbnail"}:
                        continue
                    downloaded=self._download_artwork(url)
                    if not downloaded:
                        continue
                    provenance=(
                        dict(asset.get("provenance") or {})
                        if isinstance(asset.get("provenance"),dict)
                        else {}
                    )
                    extension_id=str(
                        provenance.get("source_extension_id")
                        or asset.get("_extension_id")
                        or "artwork extension"
                    )
                    result={
                        **empty,
                        "path":str(downloaded),
                        "source":extension_id,
                        "source_url":str(provenance.get("source_url") or url),
                        "attribution":str(provenance.get("attribution") or ""),
                        "license_name":str(provenance.get("license") or ""),
                        "discovery_source":"Artwork plugin",
                        "wikidata_qid":qid,
                    }
                    self._remember_artwork_by_keys(
                        self._artist_artwork_keys({**working,"wikidata_qid":qid}),
                        downloaded,
                        source=extension_id,
                        source_url=result["source_url"],
                        attribution=result["attribution"],
                        license_name=result["license_name"],
                    )
                    return result
            except Exception:
                pass

        # 4. Last resort: search Wikimedia Commons itself. Matching is
        # deliberately conservative to avoid showing the wrong person/band.
        try:
            image_name,_description_url=self._commons_artist_image(artist_name)
        except Exception:
            image_name=""
        if image_name:
            result=self._artist_photo_from_commons(
                working,image_name,qid=qid,discovery_source="Wikimedia artist search",
            )
            if result.get("path"):
                return result

        return empty

    def discography(self, artist_mbid: str, limit: int = 18) -> list[dict[str, Any]]:
        """Return release metadata quickly; artwork is hydrated in a later stage.

        Do not download cover thumbnails here. A discography can contain many
        releases and serial image requests made the old all-in-one enrichment
        path appear frozen before the basic track identity reached the UI.
        """
        if not artist_mbid:
            return []
        data = self._mb_json(
            "release-group/",
            {"artist": artist_mbid, "fmt": "json", "limit": max(1, min(int(limit), 50)), "type": "album|ep|single"},
            45 * 86400,
        )
        groups = [x for x in list(data.get("release-groups") or []) if isinstance(x, dict)]
        rows: list[dict[str, Any]] = []
        for group in groups:
            rgid = str(group.get("id") or "")
            date = str(group.get("first-release-date") or "")
            year = int(date[:4]) if len(date) >= 4 and date[:4].isdigit() else 9999
            rows.append({
                "id": rgid,
                "title": str(group.get("title") or ""),
                "primary_type": str(group.get("primary-type") or ""),
                "secondary_types": [str(x) for x in list(group.get("secondary-types") or []) if x],
                "date": date,
                "year": None if year == 9999 else year,
                "cover_url": f"{_CAA_BASE}/release-group/{rgid}/front-250" if rgid else "",
                "cover_path": "",
            })
        rows.sort(key=lambda row: (row.get("year") if row.get("year") is not None else 9999, str(row.get("title") or "").casefold()))
        return rows[:limit]

    def hydrate_discography_covers(self, rows: list[dict[str, Any]], limit: int = 8) -> list[dict[str, Any]]:
        """Download only a small visible subset of release thumbnails.

        This is intentionally separate from ``discography`` so a missing or
        slow Cover Art Archive image can never delay track identification.
        """
        out = [dict(row) for row in rows]
        remaining = max(0, int(limit))
        for row in out:
            if remaining <= 0:
                break
            if row.get("cover_path"):
                continue
            url = str(row.get("cover_url") or "")
            if not url:
                continue
            downloaded = self._download_artwork(url)
            if downloaded:
                row["cover_path"] = str(downloaded)
            remaining -= 1
        return out

    def artwork(self, track: dict[str, Any], identity: MetadataIdentity) -> dict[str, Any]:
        local = self.local_artwork(track)
        if str(local.get("path") or ""):
            return local
        supplied = str(track.get("artwork") or track.get("artwork_url") or "")
        if supplied:
            downloaded = self._download_artwork(supplied)
            if downloaded:
                result={"path": str(downloaded), "source": str(track.get("provider_id") or "provider") + " artwork", "source_url": supplied}
                self.remember_artwork(track, downloaded, source=result["source"], source_url=supplied)
                return result

        broker = self.capability_broker
        if broker is not None:
            try:
                subject = broker.entity_ref(track, identity.as_dict())
                result = broker.lookup_artwork(
                    subject,
                    roles=["cover", "thumbnail", "other"],
                    max_results=8,
                )
                for asset in list(result.get("assets") or []):
                    if not isinstance(asset, dict):
                        continue
                    url = str(asset.get("url") or "")
                    downloaded = self._download_artwork(url)
                    if not downloaded:
                        continue
                    provenance = (
                        dict(asset.get("provenance") or {})
                        if isinstance(asset.get("provenance"), dict)
                        else {}
                    )
                    extension_id = str(
                        provenance.get("source_extension_id")
                        or asset.get("_extension_id")
                        or "extension"
                    )
                    result = {
                        "path": str(downloaded),
                        "source": extension_id,
                        "source_url": str(provenance.get("source_url") or url),
                        "attribution": str(provenance.get("attribution") or ""),
                        "license": str(provenance.get("license") or ""),
                        "provenance": provenance,
                    }
                    self.remember_artwork(
                        track,
                        downloaded,
                        source=extension_id,
                        source_url=result["source_url"],
                        attribution=result["attribution"],
                        license_name=result["license"],
                    )
                    return result
            except Exception:
                pass

        for kind, mbid in (("release-group", identity.release_group_mbid), ("release", identity.release_mbid)):
            if not mbid:
                continue
            try:
                data = self._caa_json(f"{kind}/{mbid}")
                url, comment = self._front_image(data)
                if url:
                    downloaded = self._download_artwork(url)
                    if downloaded:
                        result={"path": str(downloaded), "source": "Cover Art Archive", "source_url": url, "comment": comment}
                        self.remember_artwork(
                            track,
                            downloaded,
                            source="Cover Art Archive",
                            source_url=url,
                        )
                        return result
            except Exception:
                continue
        return {"path": "", "source": "", "source_url": ""}

    @staticmethod
    def identity_from_dict(data: dict[str, Any]) -> MetadataIdentity:
        return MetadataIdentity(
            recording_mbid=str(data.get("recording_mbid") or ""),
            artist_mbid=str(data.get("artist_mbid") or ""),
            release_mbid=str(data.get("release_mbid") or ""),
            release_group_mbid=str(data.get("release_group_mbid") or ""),
            artist=str(data.get("artist") or ""),
            title=str(data.get("title") or ""),
            album=str(data.get("album") or ""),
            date=str(data.get("date") or ""),
            score=float(data.get("score") or 0.0),
        )

    def enrich_identity(self, track: dict[str, Any]) -> dict[str, Any]:
        """Fast first stage: local data, capability extensions, then built-in identity."""
        track = dict(track or {})
        out: dict[str, Any] = {
            "track_key": track_key(track),
            "track": track,
            "errors": [],
            "ecosystem": {},
        }
        out["lyrics"] = self.local_lyrics(track)
        broker = self.capability_broker
        identity_data: dict[str, Any] | None = None

        if broker is not None:
            try:
                identity_result = broker.resolve_identity(
                    broker.entity_ref(track), max_candidates=5
                )
                out["ecosystem"]["identity"] = identity_result
                candidates = [
                    x
                    for x in list(identity_result.get("candidates") or [])
                    if isinstance(x, dict)
                ]
                if identity_result.get("status") == "matched" and candidates:
                    identity_data = broker.legacy_identity(track, candidates[0])
            except Exception as exc:
                out["ecosystem"]["identity"] = {"errors": [str(exc)]}

        if identity_data is None:
            try:
                identity_data = self.identify(track).as_dict()
            except Exception as exc:
                identity_data = MetadataIdentity(
                    artist=str(track.get("artist") or ""),
                    title=str(track.get("title") or ""),
                    album=str(track.get("album") or ""),
                ).as_dict()
                out["errors"].append(f"MusicBrainz match: {exc}")

        if broker is not None:
            try:
                subject = broker.entity_ref(track, identity_data)
                metadata_result = broker.enrich_metadata(
                    subject,
                    requested_fields=["title", "artist", "album", "year"],
                )
                out["ecosystem"]["metadata"] = metadata_result
                fields = dict(metadata_result.get("fields") or {})
                for field_name in ("title", "artist", "album"):
                    sourced = fields.get(field_name)
                    if isinstance(sourced, dict) and sourced.get("value") not in (None, ""):
                        identity_data[field_name] = str(sourced.get("value"))
                year = fields.get("year")
                if (
                    not identity_data.get("date")
                    and isinstance(year, dict)
                    and year.get("value") not in (None, "")
                ):
                    identity_data["date"] = str(year.get("value"))
            except Exception as exc:
                out["ecosystem"]["metadata"] = {"errors": [str(exc)]}

            if not str((out.get("lyrics") or {}).get("text") or "").strip():
                try:
                    lyrics_result = broker.lookup_lyrics(
                        broker.entity_ref(track, identity_data),
                        kinds=["synchronized", "plain"],
                    )
                    out["ecosystem"]["lyrics"] = lyrics_result
                    entries = [
                        x
                        for x in list(lyrics_result.get("entries") or [])
                        if isinstance(x, dict)
                    ]
                    if entries:
                        entry = entries[0]
                        rows = []
                        for raw in list(entry.get("lines") or []):
                            if not isinstance(raw, dict):
                                continue
                            rows.append(
                                {
                                    "time_ms": int(raw.get("start_ms") or 0),
                                    "text": str(raw.get("text") or ""),
                                }
                            )
                        text_value = str(entry.get("text") or "").strip()
                        if not text_value and rows:
                            text_value = "\n".join(
                                row["text"] for row in rows if row["text"]
                            )
                        provenance = (
                            dict(entry.get("provenance") or {})
                            if isinstance(entry.get("provenance"), dict)
                            else {}
                        )
                        out["lyrics"] = {
                            "text": text_value,
                            "synced": rows,
                            "source": str(
                                provenance.get("source_extension_id")
                                or entry.get("_extension_id")
                                or "extension"
                            ),
                            "provenance": provenance,
                        }
                except Exception as exc:
                    out["ecosystem"]["lyrics"] = {"errors": [str(exc)]}

        out["identity"] = identity_data
        return out

    def enrich_context(
        self, track: dict[str, Any], identity: dict[str, Any]
    ) -> dict[str, Any]:
        broker = self.capability_broker
        if broker is None:
            return {"cards": [], "errors": []}
        try:
            result = broker.lookup_context(
                broker.entity_ref(dict(track or {}), dict(identity or {})),
                max_cards=20,
            )
            return {
                "cards": [
                    dict(card)
                    for card in list(result.get("cards") or [])
                    if isinstance(card, dict)
                ],
                "errors": [str(x) for x in list(result.get("errors") or []) if x],
            }
        except Exception as exc:
            return {"cards": [], "errors": [f"Context: {exc}"]}

    def enrich_artwork(self, track: dict[str, Any], identity: dict[str, Any]) -> dict[str, Any]:
        try:
            return {"artwork": self.artwork(dict(track or {}), self.identity_from_dict(identity)), "errors": []}
        except Exception as exc:
            return {"artwork": {"path": "", "source": "", "source_url": ""}, "errors": [f"Artwork: {exc}"]}

    def enrich_artist(self, identity: dict[str, Any]) -> dict[str, Any]:
        try:
            return {"artist": self.artist_info(str(identity.get("artist_mbid") or "")), "errors": []}
        except Exception as exc:
            return {"artist": {}, "errors": [f"Artist information: {exc}"]}

    def enrich_artist_photo(self, artist: dict[str, Any]) -> dict[str, Any]:
        try:
            return {"artist_photo": self.artist_photo(dict(artist or {})), "errors": []}
        except Exception as exc:
            return {"artist_photo": {"path": "", "source": "", "source_url": "", "attribution": ""}, "errors": [f"Artist photo: {exc}"]}

    def enrich_credits(self, identity: dict[str, Any]) -> dict[str, Any]:
        try:
            return {"credits": self.recording_credits(str(identity.get("recording_mbid") or "")), "errors": []}
        except Exception as exc:
            return {"credits": [], "errors": [f"Credits: {exc}"]}

    def enrich_discography(self, identity: dict[str, Any]) -> dict[str, Any]:
        try:
            return {"discography": self.discography(str(identity.get("artist_mbid") or "")), "errors": []}
        except Exception as exc:
            return {"discography": [], "errors": [f"Discography: {exc}"]}

    def enrich(self, track: dict[str, Any]) -> dict[str, Any]:
        """Compatibility all-in-one enrichment.

        The GUI no longer calls this method because progressive stages are much
        more responsive. Keeping it makes existing integrations/tests work.
        Discography cover thumbnails are deliberately *not* hydrated here.
        """
        bundle = self.enrich_identity(track)
        identity = bundle.get("identity") if isinstance(bundle.get("identity"), dict) else {}
        for stage in (
            self.enrich_artwork(track, identity),
            self.enrich_artist(identity),
            self.enrich_credits(identity),
            self.enrich_discography(identity),
        ):
            bundle.update({k: v for k, v in stage.items() if k != "errors"})
            bundle.setdefault("errors", []).extend(stage.get("errors") or [])
        artist = bundle.get("artist") if isinstance(bundle.get("artist"), dict) else {}
        photo = self.enrich_artist_photo(artist)
        bundle.update({k: v for k, v in photo.items() if k != "errors"})
        bundle.setdefault("errors", []).extend(photo.get("errors") or [])
        return bundle

    def close(self) -> None:
        try:
            self.session.close()
        except Exception:
            pass
