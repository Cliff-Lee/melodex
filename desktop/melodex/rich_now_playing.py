from __future__ import annotations

import html
import threading
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QColor, QDesktopServices, QImage, QPixmap
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QPushButton, QTabWidget, QTextBrowser, QVBoxLayout, QWidget
)

from .metadata import RichMetadataService, track_key


class _MetadataSignals(QObject):
    loaded = Signal(str, object)


def _escape(value: Any) -> str:
    return html.escape(str(value or ""))


class RichNowPlayingWidget(QWidget):
    def __init__(self, metadata: RichMetadataService, parent=None):
        super().__init__(parent)
        self.metadata = metadata
        self.track: dict[str, Any] = {}
        self.bundle: dict[str, Any] = {}
        self.synced: list[dict[str, Any]] = []
        self._lyric_index = -2
        self._signals = _MetadataSignals(self)
        self._signals.loaded.connect(self._loaded)
        self._build()

    def _build(self) -> None:
        outer = QVBoxLayout(self); outer.setContentsMargins(0, 8, 0, 0); outer.setSpacing(16)
        hero = QHBoxLayout(); hero.setSpacing(24); outer.addLayout(hero)
        self.art = QLabel("♫"); self.art.setAlignment(Qt.AlignCenter); self.art.setFixedSize(350, 350)
        self.art.setStyleSheet("background:#181b20;border:1px solid #303640;border-radius:18px;font-size:90px;color:#596270")
        hero.addWidget(self.art, 0, Qt.AlignTop)
        right = QVBoxLayout(); right.setSpacing(8); hero.addLayout(right, 1)
        self.title = QLabel("Nothing playing"); self.title.setWordWrap(True); self.title.setStyleSheet("font-size:34px;font-weight:750")
        self.artist = QLabel(""); self.artist.setWordWrap(True); self.artist.setStyleSheet("font-size:21px;color:#c8ccd2")
        self.album = QLabel(""); self.album.setWordWrap(True); self.album.setStyleSheet("font-size:15px;color:#aab0ba")
        self.facts = QLabel(""); self.facts.setWordWrap(True); self.facts.setStyleSheet("color:#8f96a1")
        self.links = QLabel(""); self.links.setOpenExternalLinks(True); self.links.setWordWrap(True)
        right.addWidget(self.title); right.addWidget(self.artist); right.addWidget(self.album); right.addWidget(self.facts); right.addWidget(self.links); right.addStretch(1)
        self.art_source = QLabel(""); self.art_source.setWordWrap(True); self.art_source.setStyleSheet("color:#777f8a;font-size:11px"); right.addWidget(self.art_source)

        self.tabs = QTabWidget(); outer.addWidget(self.tabs, 1)
        self.lyrics = QTextBrowser(); self.artist_info = QTextBrowser(); self.credits = QTextBrowser(); self.info = QTextBrowser()
        for browser in (self.lyrics, self.artist_info, self.credits, self.info):
            browser.setOpenExternalLinks(True)
        self.tabs.addTab(self.lyrics, "Lyrics")
        self.tabs.addTab(self.artist_info, "Artist")
        self.tabs.addTab(self.credits, "Credits")
        self.tabs.addTab(self.info, "Info")
        self._empty_tabs()

    def _empty_tabs(self) -> None:
        self.lyrics.setHtml("<p style='color:#9097a2'>Play a local track with embedded lyrics, a matching .lrc file, or a .txt lyric sidecar.</p>")
        self.artist_info.setHtml("<p style='color:#9097a2'>Artist information will appear here when MusicBrainz can identify the track.</p>")
        self.credits.setHtml("<p style='color:#9097a2'>Structured recording/work credits will appear here when available.</p>")
        self.info.setHtml("<p style='color:#9097a2'>Source and MusicBrainz identifiers will appear here.</p>")

    def set_track(self, track: dict[str, Any]) -> None:
        self.track = dict(track or {}); self.bundle = {}; self.synced = []; self._lyric_index = -2
        self.title.setText(str(self.track.get("title") or "Unknown track"))
        self.artist.setText(str(self.track.get("artist") or "Unknown artist"))
        album = str(self.track.get("album") or "")
        self.album.setText(album)
        provider = str(self.track.get("provider_id") or self.track.get("source") or "")
        duration = float(self.track.get("duration") or 0)
        duration_text = f"{int(duration)//60}:{int(duration)%60:02d}" if duration > 0 else ""
        self.facts.setText(" · ".join(x for x in (provider, duration_text) if x))
        self.links.clear(); self.art_source.clear(); self._set_art("") ; self._empty_tabs()
        key = track_key(self.track)
        if not key:
            return
        requested_track = dict(self.track)
        def work():
            try:
                bundle = self.metadata.enrich(requested_track)
            except Exception as exc:
                bundle = {"track_key": key, "track": requested_track, "errors": [str(exc)]}
            self._signals.loaded.emit(key, bundle)
        threading.Thread(target=work, daemon=True).start()

    def _loaded(self, key: str, bundle: object) -> None:
        if key != track_key(self.track) or not isinstance(bundle, dict):
            return
        self.apply_metadata(bundle)

    def apply_metadata(self, bundle: dict[str, Any]) -> None:
        self.bundle = dict(bundle or {})
        identity = self.bundle.get("identity") if isinstance(self.bundle.get("identity"), dict) else {}
        artist = self.bundle.get("artist") if isinstance(self.bundle.get("artist"), dict) else {}
        artwork = self.bundle.get("artwork") if isinstance(self.bundle.get("artwork"), dict) else {}
        lyrics = self.bundle.get("lyrics") if isinstance(self.bundle.get("lyrics"), dict) else {}
        credits = [x for x in list(self.bundle.get("credits") or []) if isinstance(x, dict)]

        if identity.get("title"): self.title.setText(str(identity.get("title")))
        if identity.get("artist"): self.artist.setText(str(identity.get("artist")))
        album = str(identity.get("album") or self.track.get("album") or "")
        date = str(identity.get("date") or "")
        self.album.setText(" · ".join(x for x in (album, date[:4] if date else "") if x))
        facts = []
        if artist.get("type"): facts.append(str(artist.get("type")))
        place = str(artist.get("begin_area") or artist.get("area") or artist.get("country") or "")
        if place: facts.append(place)
        genres = [str(x) for x in list(artist.get("genres") or []) if x]
        if genres: facts.append(" · ".join(genres[:4]))
        if not facts:
            provider = str(self.track.get("provider_id") or "")
            if provider: facts.append(provider)
        self.facts.setText("   |   ".join(facts))

        art_path = str(artwork.get("path") or "")
        self._set_art(art_path)
        source = str(artwork.get("source") or "")
        self.art_source.setText(("Artwork: " + source) if source else "")

        mb_links = []
        if identity.get("recording_mbid"):
            mb_links.append(f'<a href="https://musicbrainz.org/recording/{_escape(identity.get("recording_mbid"))}">MusicBrainz recording</a>')
        if identity.get("artist_mbid"):
            mb_links.append(f'<a href="https://musicbrainz.org/artist/{_escape(identity.get("artist_mbid"))}">artist</a>')
        if identity.get("release_mbid"):
            mb_links.append(f'<a href="https://musicbrainz.org/release/{_escape(identity.get("release_mbid"))}">release</a>')
        self.links.setText(" · ".join(mb_links))

        self.synced = [dict(x) for x in list(lyrics.get("synced") or []) if isinstance(x, dict)]
        lyric_text = str(lyrics.get("text") or "")
        lyric_source = str(lyrics.get("source") or "")
        if self.synced:
            self._lyric_index = -2; self._render_synced(-1)
        elif lyric_text:
            self.lyrics.setHtml(f"<div style='font-size:18px;line-height:1.6'>{'<br>'.join(_escape(lyric_text).splitlines())}</div><p style='color:#777'>Source: {_escape(lyric_source)}</p>")
        else:
            self.lyrics.setHtml("<p style='color:#9097a2'>No local lyrics found. Add a .lrc or .txt file beside the audio file, or embed lyrics in the audio tags.</p>")

        self.artist_info.setHtml(self._artist_html(artist))
        self.credits.setHtml(self._credits_html(credits))
        self.info.setHtml(self._info_html(identity, artwork, self.bundle.get("errors") or []))

    def _set_art(self, path: str) -> None:
        if path and Path(path).exists():
            pix = QPixmap(path)
            if not pix.isNull():
                self.art.setText("")
                self.art.setPixmap(pix.scaled(self.art.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
                self._apply_accent(QImage(path))
                return
        self.art.setPixmap(QPixmap()); self.art.setText("♫")
        self.setStyleSheet("")

    def _apply_accent(self, image: QImage) -> None:
        if image.isNull(): return
        small = image.scaled(24, 24, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
        r = g = b = count = 0
        for y in range(small.height()):
            for x in range(small.width()):
                c = QColor(small.pixel(x, y)); mx, mn = max(c.red(), c.green(), c.blue()), min(c.red(), c.green(), c.blue())
                if mx < 28 or (mx - mn < 8 and mx > 220):
                    continue
                r += c.red(); g += c.green(); b += c.blue(); count += 1
        if not count: return
        accent = QColor(r // count, g // count, b // count)
        if accent.lightness() < 80: accent = accent.lighter(155)
        if accent.lightness() > 200: accent = accent.darker(125)
        dark = QColor(accent); dark = dark.darker(420)
        self.title.setStyleSheet(f"font-size:34px;font-weight:750;color:{accent.name()}")
        self.art.setStyleSheet(f"background:#181b20;border:2px solid {accent.name()};border-radius:18px")
        self.setStyleSheet(f"RichNowPlayingWidget{{background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 {dark.name()},stop:0.48 #101114,stop:1 #101114);border-radius:14px}}")

    def _artist_html(self, artist: dict[str, Any]) -> str:
        if not artist:
            return "<p style='color:#9097a2'>No MusicBrainz artist information found.</p>"
        parts = [f"<h2>{_escape(artist.get('name'))}</h2>"]
        dis = str(artist.get("disambiguation") or "")
        if dis: parts.append(f"<p>{_escape(dis)}</p>")
        details = []
        if artist.get("type"): details.append(str(artist.get("type")))
        if artist.get("begin_area"): details.append("From " + str(artist.get("begin_area")))
        elif artist.get("area"): details.append(str(artist.get("area")))
        if artist.get("begin"): details.append("Active from " + str(artist.get("begin")))
        if details: parts.append(f"<p>{_escape(' · '.join(details))}</p>")
        genres = [str(x) for x in list(artist.get("genres") or []) if x]
        if genres: parts.append("<p><b>Genres / tags:</b> " + _escape(", ".join(genres)) + "</p>")
        members = [x for x in list(artist.get("members") or []) if isinstance(x, dict)]
        if members:
            parts.append("<h3>Members / membership</h3><ul>" + "".join(f"<li>{_escape(x.get('name'))} — {_escape(x.get('type'))}{' (former)' if x.get('ended') else ''}</li>" for x in members) + "</ul>")
        related = [x for x in list(artist.get("related") or []) if isinstance(x, dict)]
        if related:
            parts.append("<h3>Related artists / projects</h3><ul>" + "".join(f"<li>{_escape(x.get('name'))} — {_escape(x.get('type'))}</li>" for x in related[:15]) + "</ul>")
        links = [x for x in list(artist.get("links") or []) if isinstance(x, dict) and x.get("url")]
        if links:
            parts.append("<h3>Links</h3><ul>" + "".join(f'<li><a href="{_escape(x.get("url"))}">{_escape(x.get("type") or "website")}</a></li>' for x in links[:12]) + "</ul>")
        return "".join(parts)

    @staticmethod
    def _credits_html(rows: list[dict[str, Any]]) -> str:
        if not rows:
            return "<p style='color:#9097a2'>No structured credits were returned for this recording. MusicBrainz coverage varies by release.</p>"
        return "<h2>Credits & relationships</h2><ul>" + "".join(f"<li><b>{_escape(x.get('role'))}</b> — {_escape(x.get('name'))}</li>" for x in rows) + "</ul>"

    @staticmethod
    def _info_html(identity: dict[str, Any], artwork: dict[str, Any], errors: list[Any]) -> str:
        rows = []
        for label, key in (("Recording MBID", "recording_mbid"), ("Artist MBID", "artist_mbid"), ("Release MBID", "release_mbid"), ("Release-group MBID", "release_group_mbid")):
            if identity.get(key): rows.append(f"<tr><td><b>{label}</b></td><td>{_escape(identity.get(key))}</td></tr>")
        if identity.get("score") is not None: rows.append(f"<tr><td><b>Metadata match</b></td><td>{float(identity.get('score') or 0):.0%}</td></tr>")
        if artwork.get("source"): rows.append(f"<tr><td><b>Artwork</b></td><td>{_escape(artwork.get('source'))}</td></tr>")
        body = "<h2>Track identity</h2><table cellspacing='7'>" + "".join(rows) + "</table>" if rows else "<p>No external identity data.</p>"
        if errors:
            body += "<h3>Enrichment notes</h3><ul>" + "".join(f"<li>{_escape(x)}</li>" for x in errors) + "</ul>"
        body += "<p style='color:#777'>Online metadata: MusicBrainz. Cover images: Cover Art Archive or the playback provider. Lyrics: local files/tags only.</p>"
        return body

    def set_position(self, position_ms: int) -> None:
        if not self.synced:
            return
        idx = -1
        for i, row in enumerate(self.synced):
            if int(row.get("time_ms") or 0) <= int(position_ms): idx = i
            else: break
        if idx != self._lyric_index:
            self._lyric_index = idx; self._render_synced(idx)

    def _render_synced(self, current: int) -> None:
        parts = ["<div style='font-size:18px;line-height:1.65'>"]
        for i, row in enumerate(self.synced):
            line = _escape(row.get("text")) or "&nbsp;"
            if i == current:
                parts.append(f"<div style='font-size:22px;font-weight:700;color:#ffffff;margin:8px 0'>{line}</div>")
            elif current >= 0 and abs(i-current) <= 2:
                parts.append(f"<div style='color:#c7ccd4'>{line}</div>")
            else:
                parts.append(f"<div style='color:#7e858f'>{line}</div>")
        parts.append("</div>")
        self.lyrics.setHtml("".join(parts))
