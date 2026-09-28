from __future__ import annotations

import json
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
