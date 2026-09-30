from __future__ import annotations

import json
import csv
import io
import re
import urllib.parse
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

XSPF_NS = "http://xspf.org/ns/0/"
MELODEX_META = "https://melodex.app/meta/"


def _text(value: Any) -> str:
    return str(value or "").strip()


def _location(track: dict[str, Any]) -> str:
    local = _text(track.get("local_path"))
    if local:
        try:
            return Path(local).expanduser().resolve().as_uri()
        except Exception:
            return local
    return _text(track.get("stream_url") or track.get("url"))


def _portable_track(track: dict[str, Any]) -> dict[str, Any]:
    keep = {
        "artist", "title", "album", "duration", "year", "reason",
        "provider_id", "track_id", "source_page", "license_url", "attribution",
    }
    out = {k: track[k] for k in keep if track.get(k) not in (None, "")}
    loc = _location(track)
    if loc:
        out["location"] = loc
    return out


def _split_display(display: str) -> tuple[str, str]:
    display = _text(display)
    for sep in (" - ", " — ", " – "):
        if sep in display:
            artist, title = display.split(sep, 1)
            return artist.strip(), title.strip()
    return "", display


def _from_location(location: str, base_dir: Path) -> dict[str, Any]:
    loc = _text(location)
    if not loc:
        return {}
    parsed = urllib.parse.urlparse(loc)
    if parsed.scheme in {"http", "https"}:
        return {"stream_url": loc, "url": loc, "source": "playlist-url"}
    if parsed.scheme == "file":
        path = Path(urllib.parse.unquote(parsed.path))
        return {"local_path": str(path), "source": "playlist-file"}
    if parsed.scheme == "melodex" and parsed.netloc == "resolve":
        q = urllib.parse.parse_qs(parsed.query)
        return {
            "artist": q.get("artist", [""])[0],
            "title": q.get("title", [""])[0],
            "album": q.get("album", [""])[0],
            "source": "melodex-playlist",
        }
    path = Path(loc).expanduser()
    if not path.is_absolute():
        path = (base_dir / path).resolve()
    return {"local_path": str(path), "source": "playlist-file"}


def _melodex_uri(track: dict[str, Any]) -> str:
    params = {
        "artist": _text(track.get("artist")),
        "title": _text(track.get("title")),
        "album": _text(track.get("album")),
    }
    return "melodex://resolve?" + urllib.parse.urlencode(params)


def load_playlist(path: Path) -> dict[str, Any]:
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix in {".m3u", ".m3u8"}:
        return load_m3u(path)
    if suffix == ".xspf":
        return load_xspf(path)
    raise ValueError("Supported playlist formats are .xspf, .m3u and .m3u8")


def parse_playlist_text(text: str) -> dict[str, Any]:
    """Parse a playlist copied from an AI chat or a plain-text playlist file.

    The parser accepts Melodex JSON, common JSON playlist shapes, Markdown
    tables, CSV/TSV, M3U text, and one-track-per-line lists. It intentionally
    extracts metadata only; playback matching is handled by the resolver.
    """
    source = str(text or "").strip().lstrip("\ufeff")
    if not source:
        raise ValueError("Paste a playlist first.")

    cleaned = re.sub(r"^\s*```(?:json|markdown|md|text|csv|m3u)?\s*", "", source, flags=re.I)
    cleaned = re.sub(r"\s*```\s*$", "", cleaned)
    json_candidate = _find_json_playlist(cleaned)
    if json_candidate is not None:
        return _normalize_playlist_object(json_candidate)

    if cleaned.lstrip().startswith("#EXTM3U"):
        tracks = _parse_m3u_text(cleaned)
        if tracks:
            return {"name": "Pasted playlist", "description": "", "tracks": tracks, "format": "m3u"}

    table = _parse_markdown_table(cleaned)
    if table:
        return {"name": "Pasted playlist", "description": "", "tracks": table, "format": "markdown"}

    delimited = _parse_delimited_text(cleaned)
    if delimited:
        return {"name": "Pasted playlist", "description": "", "tracks": delimited, "format": "text"}

    tracks = []
    for raw in cleaned.splitlines():
        line = re.sub(r"^\s*(?:[-*•]|\d+[.)])\s*", "", raw).strip()
        if not line or line.startswith("#") or _is_heading_or_separator(line):
            continue
        track = _track_from_display(line)
        if track:
            tracks.append(track)
    if tracks:
        return {"name": "Pasted playlist", "description": "", "tracks": tracks, "format": "text"}
    raise ValueError("I couldn’t find any tracks. Try pasting an artist and title per line, a Markdown table, CSV, or JSON.")


def _find_json_playlist(text: str) -> Any | None:
    decoder = json.JSONDecoder()
    for index, char in enumerate(text):
        if char not in "[{":
            continue
        try:
            value, _ = decoder.raw_decode(text[index:])
        except (json.JSONDecodeError, RecursionError):
            continue
        if isinstance(value, list):
            return value
        if isinstance(value, dict) and any(key in value for key in ("tracks", "songs", "items", "playlist")):
            return value
    return None


def _normalize_playlist_object(value: Any) -> dict[str, Any]:
    if isinstance(value, list):
        data: dict[str, Any] = {"tracks": value}
    elif isinstance(value, dict):
        data = value
    else:
        raise ValueError("Playlist JSON must be an object or a list of tracks.")
    raw_tracks = data.get("tracks", data.get("songs", data.get("items", data.get("playlist"))))
    if isinstance(raw_tracks, dict):
        raw_tracks = raw_tracks.get("tracks", raw_tracks.get("items", []))
    if not isinstance(raw_tracks, list):
        raise ValueError("Playlist JSON needs a tracks list.")
    tracks = []
    for raw in raw_tracks:
        if isinstance(raw, dict):
            track = _normalize_track_fields(raw)
        elif isinstance(raw, str):
            track = _track_from_display(raw)
        else:
            track = None
        if track:
            tracks.append(track)
    if not tracks:
        raise ValueError("The playlist JSON did not contain any readable tracks.")
    return {
        "name": str(data.get("name") or data.get("title") or "AI playlist"),
        "description": str(data.get("description") or ""),
        "tracks": tracks,
        "format": "json",
    }


def _normalize_track_fields(raw: dict[str, Any]) -> dict[str, Any] | None:
    aliases = {
        "artist": ("artist", "artists", "performer", "band"),
        "title": ("title", "track", "song", "track_title", "name"),
        "album": ("album", "record", "release"),
        "year": ("year", "release_year"),
        "reason": ("reason", "notes", "why"),
    }
    normalized = {str(key).strip().lower().replace(" ", "_"): value for key, value in raw.items()}
    out: dict[str, Any] = {}
    for field, keys in aliases.items():
        for key in keys:
            value = normalized.get(key)
            if isinstance(value, list):
                value = ", ".join(str(v) for v in value if v)
            if value not in (None, ""):
                out[field] = str(value).strip() if field != "year" else value
                break
    for field in ("local_path", "stream_url", "url", "provider_id", "track_id", "duration", "source_page"):
        value = normalized.get(field)
        if value not in (None, ""):
            out[field] = value
    if not out.get("title") and out.get("artist"):
        return None
    if not out.get("artist") and not out.get("title"):
        return None
    return out


def _parse_markdown_table(text: str) -> list[dict[str, Any]]:
    lines = [line.strip() for line in text.splitlines() if "|" in line]
    if len(lines) < 2:
        return []
    rows = [[cell.strip() for cell in line.strip().strip("|").split("|")] for line in lines]
    header = [_header_key(cell) for cell in rows[0]]
    if not any(x in {"artist", "title", "track", "song"} for x in header):
        return []
    tracks = []
    for row in rows[1:]:
        if all(re.fullmatch(r"[:\-\s]+", cell or "-") for cell in row):
            continue
        item = {header[i]: cell for i, cell in enumerate(row[:len(header)]) if i < len(header) and header[i]}
        track = _normalize_track_fields(item)
        if track:
            tracks.append(track)
    return tracks


def _header_key(value: str) -> str:
    key = re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")
    return {"track_name": "title", "song_title": "title", "track_title": "title", "artist_name": "artist", "release_year": "year"}.get(key, key)


def _parse_delimited_text(text: str) -> list[dict[str, Any]]:
    sample = "\n".join(text.splitlines()[:12])
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",\t;")
        rows = list(csv.reader(io.StringIO(text), dialect))
    except csv.Error:
        return []
    if len(rows) < 2 or not rows[0]:
        return []
    header = [_header_key(cell) for cell in rows[0]]
    if not any(x in {"artist", "title", "track", "song"} for x in header):
        return []
    tracks = []
    for row in rows[1:]:
        item = {header[i]: cell for i, cell in enumerate(row[:len(header)]) if i < len(header) and header[i]}
        track = _normalize_track_fields(item)
        if track:
            tracks.append(track)
    return tracks


def _parse_m3u_text(text: str) -> list[dict[str, Any]]:
    tracks = []
    pending: dict[str, Any] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("#EXTINF:"):
            duration_text, _, display = line[len("#EXTINF:"):].partition(",")
            pending = _track_from_display(display) or {}
            try:
                pending["duration"] = max(0, int(float(duration_text)))
            except ValueError:
                pass
            continue
        if line.startswith("#MELODEX:"):
            try:
                extra = json.loads(line[len("#MELODEX:"):])
                if isinstance(extra, dict):
                    pending.update(extra)
            except (json.JSONDecodeError, TypeError):
                pass
            continue
        if not line or line.startswith("#"):
            continue
        parsed = urllib.parse.urlparse(line)
        if parsed.scheme in {"http", "https"}:
            pending.update({"stream_url": line, "url": line})
        else:
            pending.setdefault("title", Path(line).stem)
        if pending:
            tracks.append(pending)
        pending = {}
    return tracks


def _track_from_display(value: str) -> dict[str, Any] | None:
    line = re.sub(r"\s+", " ", str(value or "").strip().strip("`*_"))
    for sep in (" — ", " – ", " - ", " | ", "\t"):
        if sep in line:
            left, right = line.split(sep, 1)
            left = re.sub(r"^\s*\d+[.)]\s*", "", left).strip(" \"'“”")
            right = right.strip(" \"'“”")
            if left and right:
                return {"artist": left, "title": right}
    match = re.match(r"^(.+?)\s+by\s+(.+)$", line, flags=re.I)
    if match:
        return {"artist": match.group(2).strip(" \"'“”"), "title": match.group(1).strip(" \"'“”")}
    return None


def _is_heading_or_separator(line: str) -> bool:
    stripped = line.strip("# *_-")
    return not stripped or line.startswith("#") or stripped.lower() in {"artist - title", "track list", "playlist", "tracks"}


def save_playlist(path: Path, tracks: list[dict[str, Any]], name: str = "Melodex playlist", description: str = "") -> Path:
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix in {".m3u", ".m3u8"}:
        return save_m3u(path, tracks, utf8=suffix == ".m3u8")
    if suffix == ".xspf":
        return save_xspf(path, tracks, name=name, description=description)
    raise ValueError("Supported playlist formats are .xspf, .m3u and .m3u8")


def load_m3u(path: Path) -> dict[str, Any]:
    path = Path(path)
    text = path.read_text("utf-8-sig", errors="replace")
    tracks: list[dict[str, Any]] = []
    pending: dict[str, Any] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#EXTINF:"):
            payload = line[len("#EXTINF:"):]
            duration_text, _, display = payload.partition(",")
            try:
                seconds = int(float(duration_text))
            except Exception:
                seconds = 0
            artist, title = _split_display(display)
            pending = {"artist": artist, "title": title, "duration": max(0, seconds)}
            continue
        if line.startswith("#MELODEX:"):
            try:
                data = json.loads(line[len("#MELODEX:"):])
                if isinstance(data, dict):
                    pending.update(data)
            except Exception:
                pass
            continue
        if line.startswith("#"):
            continue
        item = _from_location(line, path.parent)
        item.update({k: v for k, v in pending.items() if v not in (None, "")})
        if not item.get("title") and item.get("local_path"):
            item["title"] = Path(str(item["local_path"])).stem
        tracks.append(item)
        pending = {}
    return {"name": path.stem, "description": "", "tracks": tracks, "format": path.suffix.lower().lstrip(".")}


def save_m3u(path: Path, tracks: list[dict[str, Any]], utf8: bool = True) -> Path:
    path = Path(path)
    lines = ["#EXTM3U"]
    for raw in tracks:
        track = dict(raw)
        artist = _text(track.get("artist"))
        title = _text(track.get("title")) or "Unknown track"
        duration = int(float(track.get("duration") or 0))
        display = f"{artist} - {title}" if artist else title
        lines.append(f"#EXTINF:{duration},{display}")
        meta = _portable_track(track)
        lines.append("#MELODEX:" + json.dumps(meta, ensure_ascii=False, separators=(",", ":")))
        lines.append(_location(track) or _melodex_uri(track))
    path.parent.mkdir(parents=True, exist_ok=True)
    encoding = "utf-8" if utf8 else "utf-8"
    path.write_text("\n".join(lines) + "\n", encoding=encoding)
    return path


def load_xspf(path: Path) -> dict[str, Any]:
    path = Path(path)
    root = ET.parse(path).getroot()

    def tag(name: str) -> str:
        return f"{{{XSPF_NS}}}{name}"

    name = _text(root.findtext(tag("title"))) or path.stem
    description = _text(root.findtext(tag("annotation")))
    tracks: list[dict[str, Any]] = []
    track_list = root.find(tag("trackList"))
    if track_list is None:
        return {"name": name, "description": description, "tracks": [], "format": "xspf"}
    for node in track_list.findall(tag("track")):
        item: dict[str, Any] = {
            "title": _text(node.findtext(tag("title"))),
            "artist": _text(node.findtext(tag("creator"))),
            "album": _text(node.findtext(tag("album"))),
        }
        duration_ms = _text(node.findtext(tag("duration")))
        if duration_ms:
            try:
                item["duration"] = max(0.0, float(duration_ms) / 1000.0)
            except Exception:
                pass
        location = _text(node.findtext(tag("location")))
        if location:
            item.update(_from_location(location, path.parent))
        for meta in node.findall(tag("meta")):
            rel = _text(meta.attrib.get("rel"))
            value = _text(meta.text)
            if rel.startswith(MELODEX_META) and value:
                key = rel[len(MELODEX_META):]
                if key in {"provider_id", "track_id", "year", "reason", "source_page", "license_url", "attribution"}:
                    item[key] = value
        if item.get("title") or item.get("artist") or item.get("local_path") or item.get("stream_url"):
            tracks.append(item)
    return {"name": name, "description": description, "tracks": tracks, "format": "xspf"}


def save_xspf(path: Path, tracks: list[dict[str, Any]], name: str = "Melodex playlist", description: str = "") -> Path:
    path = Path(path)
    ET.register_namespace("", XSPF_NS)

    def tag(value: str) -> str:
        return f"{{{XSPF_NS}}}{value}"

    root = ET.Element(tag("playlist"), {"version": "1"})
    ET.SubElement(root, tag("title")).text = _text(name) or "Melodex playlist"
    if description:
        ET.SubElement(root, tag("annotation")).text = _text(description)
    track_list = ET.SubElement(root, tag("trackList"))
    for raw in tracks:
        track = dict(raw)
        node = ET.SubElement(track_list, tag("track"))
        location = _location(track)
        if location:
            ET.SubElement(node, tag("location")).text = location
        title = _text(track.get("title"))
        artist = _text(track.get("artist"))
        album = _text(track.get("album"))
        if title:
            ET.SubElement(node, tag("title")).text = title
        if artist:
            ET.SubElement(node, tag("creator")).text = artist
        if album:
            ET.SubElement(node, tag("album")).text = album
        duration = float(track.get("duration") or 0)
        if duration > 0:
            ET.SubElement(node, tag("duration")).text = str(int(round(duration * 1000)))
        for key in ("provider_id", "track_id", "year", "reason", "source_page", "license_url", "attribution"):
            value = track.get(key)
            if value not in (None, ""):
                meta = ET.SubElement(node, tag("meta"), {"rel": MELODEX_META + key})
                meta.text = str(value)
    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    path.parent.mkdir(parents=True, exist_ok=True)
    tree.write(path, encoding="utf-8", xml_declaration=True)
    return path
