from __future__ import annotations

import json
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, QTimer, Signal, QObject
from PySide6.QtGui import QAction, QDesktopServices, QPixmap
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QListWidget,
    QListWidgetItem, QStackedWidget, QLineEdit, QComboBox, QFileDialog, QMessageBox,
    QSlider, QTextEdit, QInputDialog, QDialog, QFormLayout, QDialogButtonBox, QCheckBox
)

from .paths import app_data_dir
from .provider_manager import ProviderManager
from .flow import FlowEngine
from .mind import MindEngine
from .user_state import UserState
from .player import FlowPlayer
from .llm_bridge import LLMClient, LLMSettings
from .bridge_server import ProviderBridge
from .playlist_io import load_playlist, save_playlist
from .metadata import RichMetadataService
from .rich_now_playing import RichNowPlayingWidget


class WorkerSignals(QObject):
    done = Signal(object)
    error = Signal(str)


def _track_text(t: dict[str, Any]) -> str:
    artist = str(t.get("artist") or "Unknown artist")
    title = str(t.get("title") or "Unknown track")
    source = str(t.get("provider_id") or "")
    return f"{artist} — {title}" + (f"   ·   {source}" if source else "")


class MainWindow(QMainWindow):
    externalCommand = Signal(str, object, object)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Melodex")
        self.resize(1280, 800)
        self.data_dir = app_data_dir()
        self.providers = ProviderManager(self.data_dir)
        self.state = UserState(self.data_dir / "taste.sqlite3")
        self.flow = FlowEngine(self.data_dir / "flow.sqlite3")
        self.mind = MindEngine(self.state, self.flow)
        self.llm = LLMClient()
        self.metadata = RichMetadataService(self.data_dir)
        self.bridge: ProviderBridge | None = None
        self.current_history_id = 0
        self.current_track_started = 0.0
        self.current_track: dict[str, Any] | None = None
        self.current_page = "home"
        self.externalCommand.connect(self._on_external_command)

        self.player = FlowPlayer(
            self.providers.resolve, self._transition_for, self,
            playback_refresher=self.providers.refresh_playback,
        )
        self.player.trackChanged.connect(self._on_track_changed)
        self.player.positionChanged.connect(self._on_position)
        self.player.error.connect(lambda s: self.statusBar().showMessage(s, 7000))
        self.player.queueChanged.connect(self._refresh_queue)

        self._build_ui()
        self._show_home()
        self._start_local_bridge()

    # ------------------------------- UI
    def _build_ui(self):
        root = QWidget(); self.setCentralWidget(root)
        outer = QVBoxLayout(root); outer.setContentsMargins(0,0,0,0); outer.setSpacing(0)
        body = QWidget(); body_l = QHBoxLayout(body); body_l.setContentsMargins(0,0,0,0); body_l.setSpacing(0)
        outer.addWidget(body, 1)

        self.sidebar = QWidget(); self.sidebar.setObjectName("sidebar"); self.sidebar.setFixedWidth(220)
        side = QVBoxLayout(self.sidebar); side.setContentsMargins(16,18,16,14)
        brand = QHBoxLayout(); brand.setSpacing(10)
        mark = QLabel()
        mark_path = Path(__file__).resolve().parent / "assets" / "melodex-mark.png"
        pixmap = QPixmap(str(mark_path))
        if not pixmap.isNull():
            mark.setPixmap(
                pixmap.scaled(
                    44, 44, Qt.KeepAspectRatio, Qt.SmoothTransformation
                )
            )
        mark.setFixedSize(46, 46)
        titles = QVBoxLayout(); titles.setSpacing(0)
        logo = QLabel("MELODEX")
        logo.setStyleSheet("font-size:20px;font-weight:750;letter-spacing:2px")
        tagline = QLabel("Don't shuffle. Flow.")
        tagline.setObjectName("brandTagline")
        titles.addWidget(logo); titles.addWidget(tagline)
        brand.addWidget(mark); brand.addLayout(titles, 1)
        side.addLayout(brand); side.addSpacing(12)
        for text, page in [("Home","home"),("Now playing","now_playing"),("Play for me","for_you"),("Discover","discover"),("My music","library"),("Playlists","playlists"),("Moments","moments"),("Ask Melodex","ask"),("Sources","sources")]:
            b = QPushButton(text); b.setCursor(Qt.PointingHandCursor); b.clicked.connect(lambda _=False,p=page:self.open_page(p)); side.addWidget(b)
        side.addStretch(1)
        self.power_toggle = QCheckBox("Show power tools")
        self.power_toggle.stateChanged.connect(self._power_changed)
        side.addWidget(self.power_toggle)
        body_l.addWidget(self.sidebar)

        self.stack = QStackedWidget(); body_l.addWidget(self.stack, 1)
        self.pages: dict[str, QWidget] = {}
        for name in ["home","now_playing","for_you","discover","library","playlists","moments","ask","sources"]:
            w = QWidget(); self.pages[name]=w; self.stack.addWidget(w)
        self._build_home(); self._build_now_playing(); self._build_for_you(); self._build_discover(); self._build_library(); self._build_playlists(); self._build_moments(); self._build_ask(); self._build_sources()

        self.queue_panel = QWidget(); self.queue_panel.setFixedWidth(320)
        ql = QVBoxLayout(self.queue_panel); ql.setContentsMargins(12,12,12,12)
        qhead = QHBoxLayout(); qhead.addWidget(QLabel("Up next")); flow_btn=QPushButton("Flow queue"); flow_btn.clicked.connect(self._flow_queue); qhead.addWidget(flow_btn); ql.addLayout(qhead)
        self.queue_list = QListWidget(); self.queue_list.itemDoubleClicked.connect(self._queue_jump); ql.addWidget(self.queue_list,1)
        self.queue_panel.hide(); body_l.addWidget(self.queue_panel)

        # player bar
        bar = QWidget(); bar.setFixedHeight(112); bl=QHBoxLayout(bar); bl.setContentsMargins(20,8,20,8)
        prev=QPushButton("◀"); prev.clicked.connect(self.player.previous); play=QPushButton("▶ / ❚❚"); play.clicked.connect(self.player.play_pause); nxt=QPushButton("▶"); nxt.clicked.connect(self.player.next)
        bl.addWidget(prev); bl.addWidget(play); bl.addWidget(nxt)
        text_col=QVBoxLayout(); self.now_title=QLabel("Nothing playing"); self.now_title.setStyleSheet("font-weight:650;font-size:15px"); self.now_meta=QLabel(""); self.now_meta.setOpenExternalLinks(True); text_col.addWidget(self.now_title); text_col.addWidget(self.now_meta)
        self.seek=QSlider(Qt.Horizontal); self.seek.setRange(0,1000); self.seek.sliderReleased.connect(self._seek_released); text_col.addWidget(self.seek); bl.addLayout(text_col,1)
        keep=QPushButton("Keep"); keep.clicked.connect(self._keep); love=QPushButton("♥"); love.clicked.connect(lambda:self._feedback(True)); info=QPushButton("Info"); info.clicked.connect(lambda:self.open_page("now_playing")); match=QPushButton("Match"); match.clicked.connect(self._inspect_current_match); more=QPushButton("•••"); more.clicked.connect(self._more_actions); queue=QPushButton("Queue"); queue.clicked.connect(lambda:self.queue_panel.setVisible(not self.queue_panel.isVisible()))
        bl.addWidget(keep); bl.addWidget(love); bl.addWidget(info); bl.addWidget(match); bl.addWidget(more); bl.addWidget(queue)
        outer.addWidget(bar)

        self.setStyleSheet("""
            QMainWindow,QWidget{background:#0f1116;color:#f4f6fa;font-family:Arial;font-size:13px}
            QWidget#sidebar{background:#0b0d12;border-right:1px solid #242a34}
            QLabel#brandTagline{color:#8f9aaa;font-size:10px}
            QWidget#sidebar QPushButton{
                background:transparent;border:0;border-radius:9px;
                padding:10px 12px;text-align:left
            }
            QWidget#sidebar QPushButton:hover{background:#1a2130}
            QPushButton{
                background:#1a1f28;border:1px solid #2b3340;border-radius:9px;
                padding:9px 12px;text-align:left
            }
            QPushButton:hover{background:#232b37;border-color:#354154}
            QLineEdit,QComboBox,QTextEdit,QListWidget{
                background:#141820;border:1px solid #2b3340;border-radius:10px;padding:7px
            }
            QListWidget::item{padding:11px;border-bottom:1px solid #222934}
            QListWidget::item:selected{background:#233a59}
            QListWidget#sourcesList::item{padding:14px}
        """)

    def _page_layout(self, page: str, title: str, subtitle: str=""):
        lay=QVBoxLayout(self.pages[page]); lay.setContentsMargins(28,24,28,24)
        t=QLabel(title); t.setStyleSheet("font-size:28px;font-weight:700"); lay.addWidget(t)
        if subtitle:
            s=QLabel(subtitle); s.setWordWrap(True); s.setStyleSheet("color:#aab0ba"); lay.addWidget(s)
        return lay

    def _build_home(self):
        l=self._page_layout("home","Your music, without the work.","Press one button, search everything you have connected, or add your own collection.")
        hero=QPushButton("▶  Play for me"); hero.setMinimumHeight(74); hero.setStyleSheet("font-size:20px;font-weight:700;background:#2a5fd7"); hero.clicked.connect(lambda:self._play_for_me("balanced",60,0.35)); l.addWidget(hero)
        row=QHBoxLayout(); a=QPushButton("Comfort"); a.clicked.connect(lambda:self._play_for_me("comfort",60,0.15)); b=QPushButton("Surprise me"); b.clicked.connect(lambda:self._play_for_me("explore",60,0.82)); c=QPushButton("Add my music"); c.clicked.connect(self._choose_music_folder)
        row.addWidget(a); row.addWidget(b); row.addWidget(c); l.addLayout(row)
        self.home_status=QLabel(); self.home_status.setWordWrap(True); l.addWidget(self.home_status); l.addStretch(1)

    def _build_now_playing(self):
        l=self._page_layout("now_playing","Now playing","Artwork, local lyrics, artist relationships and recording credits are enriched independently from the playback source.")
        self.rich_now=RichNowPlayingWidget(self.metadata,self); l.addWidget(self.rich_now,1)

    def _build_for_you(self):
        l=self._page_layout("for_you","Play for me","Melodex uses only local listening history and audio analysis unless you explicitly connect an LLM.")
        row=QHBoxLayout(); self.mode=QComboBox(); self.mode.addItems(["balanced","comfort","rediscover","explore"]); self.minutes=QComboBox(); self.minutes.addItems(["30","60","90","120"]); self.adventure=QSlider(Qt.Horizontal); self.adventure.setRange(0,100); self.adventure.setValue(35)
        row.addWidget(QLabel("Mode")); row.addWidget(self.mode); row.addWidget(QLabel("Minutes")); row.addWidget(self.minutes); row.addWidget(QLabel("Familiar")); row.addWidget(self.adventure,1); row.addWidget(QLabel("Surprising")); l.addLayout(row)
        go=QPushButton("▶ Build this journey"); go.clicked.connect(lambda:self._play_for_me(self.mode.currentText(),int(self.minutes.currentText()),self.adventure.value()/100)); l.addWidget(go)
        self.taste_label=QLabel(); self.taste_label.setWordWrap(True); l.addWidget(self.taste_label); l.addStretch(1)

    def _build_discover(self):
        l=self._page_layout("discover","Discover","Search all connected music sources. Add a source in Sources if you want more places to search.")
        row=QHBoxLayout(); self.search_box=QLineEdit(); self.search_box.setPlaceholderText("Artist, track or album…"); self.search_source=QComboBox(); row.addWidget(self.search_box,1); row.addWidget(self.search_source); search=QPushButton("Search"); search.clicked.connect(self._search); row.addWidget(search); l.addLayout(row)
        self.search_box.returnPressed.connect(self._search)
        self.results=QListWidget(); self.results.itemDoubleClicked.connect(self._play_result); l.addWidget(self.results,1)
        row2=QHBoxLayout(); addq=QPushButton("Add selected to queue"); addq.clicked.connect(self._add_selected_to_queue); source_btn=QPushButton("Open source page"); source_btn.clicked.connect(self._open_selected_source); row2.addWidget(addq); row2.addWidget(source_btn); row2.addStretch(1); l.addLayout(row2)

    def _build_library(self):
        l=self._page_layout("library","My music","Local music stays on your device. Melodex analyses it locally for Flow.")
        row=QHBoxLayout(); add=QPushButton("Add folder…"); add.clicked.connect(self._choose_music_folder); scan=QPushButton("Rescan"); scan.clicked.connect(self._rescan); row.addWidget(add); row.addWidget(scan); row.addStretch(1); l.addLayout(row)
        self.library_list=QListWidget(); self.library_list.itemDoubleClicked.connect(self._play_library); l.addWidget(self.library_list,1)

    def _build_playlists(self):
        l=self._page_layout("playlists","Playlists","Saved journeys and imported playlists live locally. Import or export XSPF, M3U and M3U8.")
        self.playlists_list=QListWidget(); self.playlists_list.itemDoubleClicked.connect(self._play_saved_playlist); l.addWidget(self.playlists_list,1)
        row=QHBoxLayout(); imp=QPushButton("Import playlist…"); imp.clicked.connect(self._import_playlist_file); exp=QPushButton("Export selected…"); exp.clicked.connect(self._export_selected_playlist); expq=QPushButton("Export queue…"); expq.clicked.connect(self._export_queue); row.addWidget(imp); row.addWidget(exp); row.addWidget(expq); row.addStretch(1); l.addLayout(row)

    def _build_moments(self):
        l=self._page_layout("moments","Moments","Bookmarks inside songs — the exact musical moments you wanted to remember.")
        self.moments_list=QListWidget(); l.addWidget(self.moments_list,1)

    def _build_ask(self):
        l=self._page_layout("ask","Ask Melodex","Optional. Connect OpenWebUI, Ollama or another compatible model. The player still works without any LLM.")
        self.chat=QTextEdit(); self.chat.setReadOnly(True); l.addWidget(self.chat,1)
        row=QHBoxLayout(); self.ask_box=QLineEdit(); self.ask_box.setPlaceholderText("e.g. Keep this mood but make the next hour stranger"); self.ask_box.returnPressed.connect(self._ask); ask=QPushButton("Ask"); ask.clicked.connect(self._ask); cfg=QPushButton("Connect LLM…"); cfg.clicked.connect(self._llm_settings_dialog); row.addWidget(self.ask_box,1); row.addWidget(ask); row.addWidget(cfg); l.addLayout(row)

    def _build_sources(self):
        l=self._page_layout(
            "sources",
            "Music sources",
            "Connect Melodex to your music. Built-in sources stay simple; "
            "provider tools are available when you need them.",
        )
        self.sources_list=QListWidget(); self.sources_list.setObjectName("sourcesList"); l.addWidget(self.sources_list,1)

        row=QHBoxLayout()
        local=QPushButton("Add local folder…"); local.clicked.connect(self._choose_music_folder)
        jam=QPushButton("Jamendo settings…"); jam.clicked.connect(self._jamendo_settings)
        streams=QPushButton("User Streams…"); streams.clicked.connect(self._user_streams_dialog)
        row.addWidget(local); row.addWidget(jam); row.addWidget(streams)
        row.addStretch(1); l.addLayout(row)

        self.source_power_panel = QWidget()
        power=QVBoxLayout(self.source_power_panel); power.setContentsMargins(0,4,0,0); power.setSpacing(8)
        provider_row=QHBoxLayout()
        inst=QPushButton("Install .mdxprovider…"); inst.clicked.connect(self._install_provider)
        bridge=QPushButton("Provider Bridge…"); bridge.clicked.connect(self._bridge_dialog)
        provider_row.addWidget(inst); provider_row.addWidget(bridge); provider_row.addStretch(1)
        power.addLayout(provider_row)
        priority=QHBoxLayout()
        up=QPushButton("Prefer source ↑"); down=QPushButton("Prefer source ↓")
        up.clicked.connect(lambda:self._move_source(-1)); down.clicked.connect(lambda:self._move_source(1))
        priority.addWidget(up); priority.addWidget(down); priority.addStretch(1); power.addLayout(priority)
        self.source_power_panel.setVisible(self.power_toggle.isChecked())
        l.addWidget(self.source_power_panel)

    # ------------------------------- navigation/data
    def open_page(self, name: str):
        self.current_page=name; self.stack.setCurrentWidget(self.pages[name])
        if name=="home": self._show_home()
        elif name=="library": self._refresh_library()
        elif name=="sources": self._refresh_sources()
        elif name=="moments": self._refresh_moments()
        elif name=="playlists": self._refresh_playlists()
        elif name=="for_you": self._refresh_taste()
        elif name=="discover": self._refresh_source_combo()

    def _show_home(self):
        self._refresh_library(); self._refresh_sources(); self._refresh_taste()
        count=len(self.providers.local_catalog()); src=len(self.providers.providers)
        self.home_status.setText(f"{count:,} local tracks · {src} connected sources · Flow {'ready' if self.flow.analysis_available else 'works with metadata; install ffmpeg for deep analysis'}")

    def _power_changed(self, _):
        enabled = self.power_toggle.isChecked()
        if hasattr(self, "source_power_panel"):
            self.source_power_panel.setVisible(enabled)
        self.statusBar().showMessage("Power tools enabled" if enabled else "Simple mode", 2500)

    def _refresh_source_combo(self):
        current=self.search_source.currentData(); self.search_source.clear(); self.search_source.addItem("All sources","all")
        for pid in self.providers.provider_order():
            p=self.providers.providers[pid]; self.search_source.addItem(p.info.name,pid)
        idx=self.search_source.findData(current); self.search_source.setCurrentIndex(idx if idx>=0 else 0)

    def _refresh_sources(self):
        self.sources_list.clear()
        for pid in self.providers.provider_order():
            p=self.providers.providers[pid]
            name = p.info.name.replace(" (reference provider)", "")
            if pid == "local":
                count = len(self.providers.local_catalog())
                status = f"{count:,} TRACKS" if count else "ADD MUSIC"
                kind = "BUILT-IN"
            elif pid == "jamendo":
                configured = bool(str(self.providers.settings.get("jamendo_client_id", "")).strip())
                status = "READY" if configured else "SETUP NEEDED"
                kind = "REFERENCE"
            elif pid == "streams":
                count = len(self.providers.user_streams())
                status = f"{count} STREAM" if count == 1 else f"{count} STREAMS"
                kind = "BUILT-IN"
            else:
                status = "INSTALLED"
                kind = "PROVIDER"
            item=QListWidgetItem(
                f"{name}    ·    {kind}    ·    {status}\n{p.info.description}"
            )
            item.setData(Qt.UserRole,pid)
            self.sources_list.addItem(item)
        self._refresh_source_combo()

    def _move_source(self, delta):
        item=self.sources_list.currentItem()
        if not item:return
        pid=str(item.data(Qt.UserRole) or ""); order=self.providers.provider_order()
        if pid not in order:return
        i=order.index(pid); j=max(0,min(len(order)-1,i+int(delta)))
        if i==j:return
        order[i],order[j]=order[j],order[i]; self.providers.set_provider_order(order); self._refresh_sources(); self.sources_list.setCurrentRow(j)
        self.statusBar().showMessage("Source priority updated",2500)

    def _refresh_library(self):
        self.library_list.clear()
        for t in self.providers.local_catalog():
            it=QListWidgetItem(_track_text(t)); it.setData(Qt.UserRole,t); self.library_list.addItem(it)

    def _refresh_playlists(self):
        self.playlists_list.clear()
        for p in self.state.playlists():
            item=QListWidgetItem(f"{p.get('name')}\n{p.get('description','')}"); item.setData(Qt.UserRole,p); self.playlists_list.addItem(item)

    @staticmethod
    def _playlist_tracks(record):
        payload=dict(record.get("payload") or {})
        requested=payload.get("requested_tracks")
        if isinstance(requested,list):return [dict(x) for x in requested if isinstance(x,dict)]
        return [dict(x) for x in list(payload.get("tracks") or payload.get("rows") or []) if isinstance(x,dict)]

    def _play_saved_playlist(self,item):
        record=dict(item.data(Qt.UserRole) or {}); tracks=self._playlist_tracks(record)
        if not tracks:
            self.statusBar().showMessage("This playlist has no tracks",3000); return
        self.statusBar().showMessage("Resolving playlist across connected sources…")
        self._run_async(lambda:self.providers.resolve_playlist(tracks),self._start_resolved_playlist)

    def _start_resolved_playlist(self,result):
        tracks=list(result.get("tracks") or []); unresolved=list(result.get("unresolved") or [])
        if tracks:self.player.set_queue(tracks,0,True)
        msg=f"Playing {len(tracks)} matched tracks"
        if unresolved:msg+=f" · {len(unresolved)} could not be matched"
        self.statusBar().showMessage(msg,6000)

    def _import_playlist_file(self):
        filename,_=QFileDialog.getOpenFileName(self,"Import playlist",filter="Playlists (*.xspf *.m3u *.m3u8);;XSPF (*.xspf);;M3U/M3U8 (*.m3u *.m3u8)")
        if not filename:return
        try:data=load_playlist(Path(filename))
        except Exception as exc:QMessageBox.warning(self,"Could not import playlist",str(exc)); return
        requested=[dict(x) for x in list(data.get("tracks") or []) if isinstance(x,dict)]
        if not requested:QMessageBox.information(self,"Empty playlist","No tracks were found in this playlist."); return
        playlist_id=str(uuid.uuid4()); name=str(data.get("name") or Path(filename).stem); description=str(data.get("description") or "")
        self.statusBar().showMessage(f"Importing and matching {len(requested)} tracks…")
        self._run_async(lambda:self.providers.resolve_playlist(requested),lambda result:self._finish_playlist_file_import(playlist_id,name,description,str(data.get("format") or "playlist"),requested,result))

    def _finish_playlist_file_import(self,playlist_id,name,description,fmt,requested,result):
        tracks=list(result.get("tracks") or []); unresolved=list(result.get("unresolved") or [])
        payload={"tracks":tracks,"unresolved":unresolved,"requested_tracks":requested,"format":fmt}
        self.state.save_playlist(playlist_id,name,description,f"import:{fmt}",payload); self._refresh_playlists()
        msg=f"Imported {name}: {len(tracks)} playable"
        if unresolved:msg+=f" · {len(unresolved)} unresolved (kept for future matching)"
        self.statusBar().showMessage(msg,7000)

    def _playlist_export_path(self,title):
        path,chosen=QFileDialog.getSaveFileName(self,title,filter="XSPF Playlist (*.xspf);;M3U8 Playlist (*.m3u8);;M3U Playlist (*.m3u)")
        if not path:return None
        p=Path(path)
        if not p.suffix:
            suffix=".m3u8" if "M3U8" in chosen else ".m3u" if "M3U Playlist" in chosen else ".xspf"
            p=p.with_suffix(suffix)
        return p

    def _export_selected_playlist(self):
        item=self.playlists_list.currentItem()
        if not item:self.statusBar().showMessage("Select a playlist first",3000); return
        record=dict(item.data(Qt.UserRole) or {}); tracks=self._playlist_tracks(record)
        if not tracks:self.statusBar().showMessage("This playlist has no tracks",3000); return
        path=self._playlist_export_path("Export playlist")
        if not path:return
        try:save_playlist(path,tracks,str(record.get("name") or "Melodex playlist"),str(record.get("description") or "")); self.statusBar().showMessage(f"Exported {path.name}",5000)
        except Exception as exc:QMessageBox.warning(self,"Could not export playlist",str(exc))

    def _export_queue(self):
        tracks=[dict(x) for x in self.player.queue if isinstance(x,dict)]
        if not tracks:self.statusBar().showMessage("The queue is empty",3000); return
        path=self._playlist_export_path("Export queue")
        if not path:return
        try:save_playlist(path,tracks,"Melodex queue",""); self.statusBar().showMessage(f"Exported {path.name}",5000)
        except Exception as exc:QMessageBox.warning(self,"Could not export queue",str(exc))

    def _refresh_moments(self):
        self.moments_list.clear()
        for m in self.state.moments():
            t=m.get("track") if isinstance(m.get("track"),dict) else {}
            if not t:
                try: t=json.loads(m.get("track_json") or "{}")
                except Exception: t={}
            sec=int(m.get("position_ms",0))//1000
            self.moments_list.addItem(f"{_track_text(t)} · {sec//60}:{sec%60:02d}   {m.get('label','')}")

    def _refresh_taste(self):
        s=self.state.taste_summary(); self.taste_label.setText(f"Taste memory: {s.get('tracks',0)} tracks learned · {s.get('artists',0)} artists · completion rate {float(s.get('completion_rate',0))*100:.0f}%")

    # ------------------------------- sources/search
    def _choose_music_folder(self):
        folder=QFileDialog.getExistingDirectory(self,"Choose a music folder")
        if not folder: return
        roots=[Path(x) for x in self.providers.settings.get("local_roots",[])]
        p=Path(folder)
        if p not in roots: roots.append(p)
        count=self.providers.set_local_roots(roots); self.statusBar().showMessage(f"Found {count:,} tracks",5000); self._refresh_library(); self._show_home()

    def _rescan(self):
        roots=[Path(x) for x in self.providers.settings.get("local_roots",[])]
        count=self.providers.set_local_roots(roots); self.statusBar().showMessage(f"Rescanned {count:,} tracks",4000); self._refresh_library()

    def _jamendo_settings(self):
        value,ok=QInputDialog.getText(self,"Jamendo reference provider","Your Jamendo developer client ID:",text=str(self.providers.settings.get("jamendo_client_id","")))
        if ok:
            self.providers.set_jamendo_client_id(value.strip()); self.statusBar().showMessage("Jamendo source updated",3000)

    def _install_provider(self):
        path,_=QFileDialog.getOpenFileName(self,"Install provider",filter="Melodex Provider (*.mdxprovider *.zip)")
        if not path:return
        try:
            p=self.providers.install_package(Path(path)); QMessageBox.information(self,"Provider installed",f"Installed {p.info.name}"); self._refresh_sources()
        except Exception as exc: QMessageBox.critical(self,"Could not install provider",str(exc))

    def _stream_prompt(self, existing: dict[str, Any] | None = None):
        existing = existing or {}
        name, ok = QInputDialog.getText(
            self,
            "User Stream",
            "Name:",
            text=str(existing.get("name") or ""),
        )
        if not ok:
            return None
        url, ok = QInputDialog.getText(
            self,
            "User Stream",
            "HTTP(S) stream URL:",
            text=str(existing.get("url") or ""),
        )
        if not ok:
            return None
        genre, ok = QInputDialog.getText(
            self,
            "User Stream",
            "Genre (optional):",
            text=str(existing.get("genre") or ""),
        )
        if not ok:
            return None
        return {
            "name": name.strip() or "Untitled stream",
            "url": url.strip(),
            "genre": genre.strip(),
            "description": str(existing.get("description") or ""),
        }

    def _user_streams_dialog(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("User Streams")
        dialog.resize(720, 420)
        layout = QVBoxLayout(dialog)
        intro = QLabel(
            "Add internet radio or direct HTTP(S) audio streams. "
            "You can also import M3U, M3U8 or PLS stream playlists."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        rows = QListWidget()
        layout.addWidget(rows, 1)

        def refresh():
            rows.clear()
            for entry in self.providers.user_streams():
                detail = entry.get("genre") or entry.get("url") or ""
                item = QListWidgetItem(f"{entry.get('name','Untitled stream')}\n{detail}")
                item.setData(Qt.UserRole, entry)
                rows.addItem(item)

        def add_url():
            values = self._stream_prompt()
            if not values:
                return
            try:
                self.providers.add_user_stream(**values)
                refresh()
                self._refresh_sources()
            except Exception as exc:
                QMessageBox.critical(dialog, "Could not add stream", str(exc))

        def edit_selected():
            current = rows.currentItem()
            if not current:
                return
            entry = dict(current.data(Qt.UserRole) or {})
            values = self._stream_prompt(entry)
            if not values:
                return
            try:
                self.providers.update_user_stream(str(entry.get("id") or ""), **values)
                refresh()
                self._refresh_sources()
            except Exception as exc:
                QMessageBox.critical(dialog, "Could not update stream", str(exc))

        def import_playlist():
            filename, _ = QFileDialog.getOpenFileName(
                dialog,
                "Import stream playlist",
                filter="Stream playlists (*.m3u *.m3u8 *.pls)",
            )
            if not filename:
                return
            try:
                added = self.providers.import_user_stream_playlist(Path(filename))
                refresh()
                self._refresh_sources()
                QMessageBox.information(
                    dialog,
                    "Playlist imported",
                    f"Added {len(added)} new stream(s).",
                )
            except Exception as exc:
                QMessageBox.critical(dialog, "Could not import playlist", str(exc))

        def remove_selected():
            current = rows.currentItem()
            if not current:
                return
            entry = dict(current.data(Qt.UserRole) or {})
            if QMessageBox.question(
                dialog,
                "Remove stream",
                f"Remove {entry.get('name','this stream')}?",
                QMessageBox.Yes | QMessageBox.No,
            ) != QMessageBox.Yes:
                return
            self.providers.remove_user_stream(str(entry.get("id") or ""))
            refresh()
            self._refresh_sources()

        buttons = QHBoxLayout()
        add_button = QPushButton("Add URL"); add_button.clicked.connect(add_url)
        edit_button = QPushButton("Edit"); edit_button.clicked.connect(edit_selected)
        import_button = QPushButton("Import playlist"); import_button.clicked.connect(import_playlist)
        remove_button = QPushButton("Remove"); remove_button.clicked.connect(remove_selected)
        close_button = QPushButton("Close"); close_button.clicked.connect(dialog.accept)
        for button in (add_button, edit_button, import_button, remove_button):
            buttons.addWidget(button)
        buttons.addStretch(1); buttons.addWidget(close_button)
        layout.addLayout(buttons)

        rows.itemDoubleClicked.connect(lambda _item: edit_selected())
        refresh()
        dialog.exec()

    def _search(self):
        q=self.search_box.text().strip(); pid=str(self.search_source.currentData() or "all")
        if not q:return
        self.results.clear(); self.results.addItem("Searching…")
        self._run_async(lambda:self.providers.search(q,pid,100),self._show_results)

    def _show_results(self, tracks):
        self.results.clear()
        for t in tracks:
            it=QListWidgetItem(_track_text(t)); it.setData(Qt.UserRole,t); self.results.addItem(it)

    def _play_result(self,item):
        t=dict(item.data(Qt.UserRole) or {}); self.player.set_queue([t],0,True)

    def _open_selected_source(self):
        item=self.results.currentItem()
        if not item:return
        t=dict(item.data(Qt.UserRole) or {})
        url=str(t.get("source_page") or "")
        if url: QDesktopServices.openUrl(url)
        else: self.statusBar().showMessage("This source did not provide a content page",3000)

    def _play_library(self,item):
        t=dict(item.data(Qt.UserRole) or {}); tracks=self.providers.local_catalog(); idx=next((i for i,x in enumerate(tracks) if x.get('track_id')==t.get('track_id')),0); self.player.set_queue(tracks,idx,True)

    def _add_selected_to_queue(self):
        item=self.results.currentItem()
        if not item:return
        t=dict(item.data(Qt.UserRole) or {}); q=list(self.player.queue)
        if not q: self.player.set_queue([t],0,False)
        else: self.player.queue.append(t); self.player.queueChanged.emit(self.player.queue)

    # ------------------------------- Flow / Mind
    def _path_for(self,t):
        p=str(t.get("local_path") or ""); return Path(p) if p else None

    def _transition_for(self,a,b):
        aa=self.flow.cached_analysis_for(self._path_for(a)); bb=self.flow.cached_analysis_for(self._path_for(b)); return self.flow.transition(aa,bb).as_dict()

    def _flow_queue(self):
        q=list(self.player.queue)
        if len(q)<2:return
        self.statusBar().showMessage("Planning Flow…")
        self._run_async(lambda:self.flow.plan_order(q,self._path_for,start_index=max(0,self.player.index),adventurous=0.35),lambda plan:self._apply_flow(plan))

    def _apply_flow(self,plan):
        tracks=list(plan.get("tracks",[])); self.player.set_queue(tracks,0,True); self.statusBar().showMessage(f"Flow ready · {plan.get('analysed',0)} tracks audio-analysed",5000)

    def _play_for_me(self,mode,minutes,adventure):
        catalog=self.providers.local_catalog()
        if not catalog:
            QMessageBox.information(self,"Add music first","Play for Me needs at least some local music. Add a folder, then try again."); return
        self.statusBar().showMessage("Building your journey…")
        self._run_async(lambda:self.mind.build_session(catalog,self._path_for,minutes=minutes,adventure=adventure,mode=mode),lambda plan:self._apply_mind(plan))

    def _apply_mind(self,plan):
        tracks=list(plan.get("tracks",[]));
        if tracks:self.player.set_queue(tracks,0,True)
        self.statusBar().showMessage(f"Journey ready · {len(tracks)} tracks · {plan.get('new_to_you',0)} new to you",6000)

    # ------------------------------- player/taste
    def _on_track_changed(self,t):
        if self.current_track and self.current_track_started and time.time()-self.current_track_started<30:
            self.state.record_skip(self.current_track)
        self.current_track=dict(t); self.current_track_started=time.time(); self.current_history_id=self.state.record_play(t)
        self.now_title.setText(str(t.get("title") or "Unknown track")); base=f"{t.get('artist','Unknown artist')}   ·   {t.get('album','')}   ·   {t.get('provider_id','')}"; src=str(t.get("source_page") or ""); attr=str(t.get("attribution") or ""); self.now_meta.setText(base + ((f"   ·   <a href=\"{src}\">{attr or 'Source'}</a>") if src else ""))
        if hasattr(self,"rich_now"):self.rich_now.set_track(dict(t))

    def _on_position(self,pos,dur):
        if hasattr(self,"rich_now"):self.rich_now.set_position(pos)
        if dur>0:self.seek.setValue(int(1000*pos/dur))
        if dur>0 and pos>=dur-1500 and self.current_history_id:
            self.state.mark_completed(self.current_history_id); self.current_history_id=0

    def _seek_released(self):
        p=self.player.players[self.player.active]; dur=p.duration()
        if dur>0:self.player.seek(int(dur*self.seek.value()/1000))

    def _feedback(self,positive):
        if self.current_track:self.state.record_feedback(self.current_track,positive); self.statusBar().showMessage("Loved" if positive else "Not for me",2500)

    def _keep(self):
        if self.current_track:self.state.record_keep(self.current_track); self.statusBar().showMessage("Kept in taste memory",2500)

    def _more_actions(self):
        if not self.current_track:return
        label,ok=QInputDialog.getText(self,"Save a moment","Moment note (leave blank if you like):")
        if ok:
            pos=self.player.players[self.player.active].position(); self.state.save_moment(self.current_track,pos,label); self.statusBar().showMessage("Moment saved",3000)

    @staticmethod
    def _resolver_target(track):
        track=dict(track or {}); resolution=track.get("_resolution")
        if isinstance(resolution,dict) and isinstance(resolution.get("requested"),dict):
            requested=dict(resolution.get("requested") or {})
            if str(requested.get("title") or "").strip():return requested
        return {"artist":str(track.get("artist") or ""),"title":str(track.get("title") or ""),"album":str(track.get("album") or ""),"duration":track.get("duration") or 0}

    def _inspect_current_match(self):
        if not self.current_track:
            self.statusBar().showMessage("Play a track first, then inspect its source match",3500); return
        target=self._resolver_target(self.current_track)
        self.statusBar().showMessage("Checking resolver candidates…")
        self._run_async(lambda:self.providers.inspect_resolution(target,24),lambda info:self._show_resolver_inspector(target,info))

    def _show_resolver_inspector(self,target,info):
        d=QDialog(self); d.setWindowTitle("Resolver Inspector"); d.resize(760,560); lay=QVBoxLayout(d)
        requested=f"{target.get('artist','')} — {target.get('title','')}".strip(" —")
        album=str(target.get("album") or ""); head=QLabel(f"Requested: {requested}" + (f"  ·  {album}" if album else "")); head.setWordWrap(True); lay.addWidget(head)
        blocked=int(info.get("blocked_count") or 0); threshold=float(info.get("minimum_score") or 0.62); preferred=info.get("preferred")
        summary=QLabel(f"Automatic threshold: {threshold:.0%}  ·  Wrong matches remembered: {blocked}" + ("  ·  Preferred match remembered" if preferred else "")); summary.setWordWrap(True); summary.setStyleSheet("color:#aab0ba"); lay.addWidget(summary)
        rows=QListWidget(); lay.addWidget(rows,1)
        current_pid=str((self.current_track or {}).get("provider_id") or ""); current_tid=str((self.current_track or {}).get("track_id") or ""); current_row=-1
        for i,row in enumerate(list(info.get("candidates") or [])):
            if not isinstance(row,dict):continue
            t=dict(row.get("track") or {}); score=float(row.get("score") or 0); provider=str(row.get("provider_id") or t.get("provider_id") or "")
            flags=", ".join(list(row.get("flags") or [])); reasons=" · ".join(list(row.get("reasons") or []))
            duration=row.get("duration_delta"); duration_text=(f" · Δ{float(duration):.0f}s" if duration is not None else "")
            star="★ " if bool(row.get("preferred")) else ""
            line1=f"{star}{score:.0%}  {provider}  ·  {t.get('artist','Unknown artist')} — {t.get('title','Unknown track')}"
            line2=f"title {float(row.get('title_score') or 0):.0%} · artist {float(row.get('artist_score') or 0):.0%} · album {float(row.get('album_score') or 0):.0%}{duration_text}"
            if flags:line2+=f" · [{flags}]"
            if reasons:line2+=f"\n{reasons}"
            item=QListWidgetItem(line1+"\n"+line2); item.setData(Qt.UserRole,row); rows.addItem(item)
            if str(t.get("provider_id") or "")==current_pid and str(t.get("track_id") or "")==current_tid:current_row=rows.count()-1
        if rows.count()==0:
            rows.addItem("No resolver candidates were returned by the connected sources.")
        else:rows.setCurrentRow(current_row if current_row>=0 else 0)
        buttons=QHBoxLayout(); play=QPushButton("Play this match"); prefer=QPushButton("Prefer"); wrong=QPushButton("Wrong match"); reset=QPushButton("Reset memory"); close=QPushButton("Close")
        for b in (play,prefer,wrong,reset,close):buttons.addWidget(b)
        lay.addLayout(buttons)
        def selected():
            item=rows.currentItem(); data=item.data(Qt.UserRole) if item else None
            return dict(data or {}) if isinstance(data,dict) else {}
        play.clicked.connect(lambda:self._resolver_use_candidate(target,selected(),d,False))
        prefer.clicked.connect(lambda:self._resolver_use_candidate(target,selected(),d,True))
        wrong.clicked.connect(lambda:self._resolver_wrong_candidate(target,selected(),d))
        reset.clicked.connect(lambda:self._resolver_reset_memory(target,d))
        close.clicked.connect(d.reject)
        d.exec()

    def _resolver_use_candidate(self,target,row,dialog,remember):
        candidate=dict(row.get("track") or {}) if isinstance(row,dict) else {}
        if not candidate:
            self.statusBar().showMessage("Select a resolver candidate first",3000); return
        if remember:self.providers.prefer_resolution(target,candidate)
        dialog.accept(); self.statusBar().showMessage("Using preferred match…" if remember else "Loading selected match…")
        self._run_async(lambda:self.providers.resolve_exact(candidate,target),self._apply_resolver_match)

    def _resolver_wrong_candidate(self,target,row,dialog):
        candidate=dict(row.get("track") or {}) if isinstance(row,dict) else {}
        if not candidate:
            self.statusBar().showMessage("Select a resolver candidate first",3000); return
        self.providers.block_resolution(target,candidate); dialog.accept(); self.statusBar().showMessage("Wrong match remembered · trying the next candidate…")
        self._run_async(lambda:self.providers.resolve(target),self._apply_resolver_match)

    def _resolver_reset_memory(self,target,dialog):
        self.providers.clear_resolution_preference(target); self.providers.clear_resolution_blocks(target); dialog.accept(); self.statusBar().showMessage("Match memory reset for this song",3500)
        self._run_async(lambda:self.providers.inspect_resolution(target,24),lambda info:self._show_resolver_inspector(target,info))

    def _apply_resolver_match(self,resolved):
        if not isinstance(resolved,dict):return
        idx=self.player.index
        if idx<0:self.player.set_queue([resolved],0,True); return
        self.player.queue[idx]=dict(resolved); self.player.queueChanged.emit(self.player.queue); self.player.players[self.player.active].stop(); self.player._load_index(idx,True)
        mode=str((resolved.get("_resolution") or {}).get("mode") or "match") if isinstance(resolved.get("_resolution"),dict) else "match"
        self.statusBar().showMessage(f"Resolver match applied · {mode}",4000)

    def _refresh_queue(self,tracks):
        self.queue_list.clear()
        for i,t in enumerate(tracks):
            prefix="▶ " if i==self.player.index else ""; item=QListWidgetItem(prefix+_track_text(t)); item.setData(Qt.UserRole,i); self.queue_list.addItem(item)

    def _queue_jump(self,item):
        idx=int(item.data(Qt.UserRole)); self.player.players[self.player.active].stop(); self.player._load_index(idx,True)

    # ------------------------------- LLM
    def _llm_settings(self):
        return LLMSettings(
            provider=self.state.get_text("llm_provider","openwebui"),
            endpoint=self.state.get_text("llm_endpoint",LLMClient.default_endpoint(self.state.get_text("llm_provider","openwebui"))),
            model=self.state.get_text("llm_model",""), api_key=self.state.get_text("llm_api_key","")
        )

    def _llm_settings_dialog(self):
        d=QDialog(self); d.setWindowTitle("Connect an LLM"); f=QFormLayout(d)
        provider=QComboBox(); provider.addItems(["openwebui","ollama","openai","custom"]); provider.setCurrentText(self.state.get_text("llm_provider","openwebui"))
        endpoint=QLineEdit(self.state.get_text("llm_endpoint",LLMClient.default_endpoint(provider.currentText()))); model=QLineEdit(self.state.get_text("llm_model","")); key=QLineEdit(self.state.get_text("llm_api_key","")); key.setEchoMode(QLineEdit.Password)
        provider.currentTextChanged.connect(lambda p:endpoint.setText(LLMClient.default_endpoint(p)))
        f.addRow("Provider",provider); f.addRow("Endpoint",endpoint); f.addRow("Model",model); f.addRow("API key",key)
        buttons=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel); buttons.accepted.connect(d.accept); buttons.rejected.connect(d.reject); f.addRow(buttons)
        if d.exec():
            self.state.set_text("llm_provider",provider.currentText()); self.state.set_text("llm_endpoint",endpoint.text().strip()); self.state.set_text("llm_model",model.text().strip()); self.state.set_text("llm_api_key",key.text().strip())

    def _llm_context(self):
        return {"current_track":self.current_track,"queue":self.player.queue[self.player.index:self.player.index+12] if self.player.index>=0 else [],"current_page":self.current_page,"taste":self.state.taste_summary(),"recent":self.state.recent_tracks(15),"vibes":self.state.vibes(10)}

    def _ask(self):
        prompt=self.ask_box.text().strip();
        if not prompt:return
        self.ask_box.clear(); self.chat.append(f"You: {prompt}")
        settings=self._llm_settings(); self._run_async(lambda:self.llm.complete(settings,prompt,self._llm_context(),[]),lambda text:self._handle_llm(text))

    def _handle_llm(self,text):
        reply,actions=self.llm.parse_action_response(str(text)); self.chat.append(f"Melodex: {reply}")
        for a in actions:self._execute_action(a)

    def _execute_action(self,a):
        typ=str(a.get("type") or ""); args=dict(a.get("args") or {})
        if typ=="play_for_me":self._play_for_me(args.get("mode","balanced"),int(args.get("minutes",60)),float(args.get("adventure",0.35)))
        elif typ=="search": self.open_page("discover"); self.search_box.setText(str(args.get("query", ""))); self._search()
        elif typ=="play_pause":self.player.play_pause()
        elif typ=="next":self.player.next()
        elif typ=="previous":self.player.previous()
        elif typ=="flow_queue":self._flow_queue()
        elif typ=="save_moment":
            if self.current_track:self.state.save_moment(self.current_track,self.player.players[self.player.active].position(),str(args.get("label", "")))
        elif typ=="open_view":self.open_page(str(args.get("view","home")) if str(args.get("view","home")) in self.pages else "home")
        elif typ=="import_playlist":self._import_ai_playlist(args)

    def _import_ai_playlist(self,args):
        requested=[dict(x) for x in list(args.get("tracks") or []) if isinstance(x,dict)]
        if not requested:
            self.statusBar().showMessage("The AI playlist did not contain any tracks",4000); return
        playlist_id=str(uuid.uuid4()); name=str(args.get("name","AI playlist")); description=str(args.get("description",""))
        self.statusBar().showMessage(f"Matching {len(requested)} playlist tracks across your sources…")
        self._run_async(
            lambda:self.providers.resolve_playlist(requested),
            lambda result:self._finish_ai_playlist(playlist_id,name,description,result),
        )

    def _finish_ai_playlist(self,playlist_id,name,description,result):
        tracks=list(result.get("tracks") or []); unresolved=list(result.get("unresolved") or [])
        payload={"tracks":tracks,"unresolved":unresolved,"requested":int(result.get("requested") or len(tracks)+len(unresolved))}
        self.state.save_playlist(playlist_id,name,description,"llm",payload); self._refresh_playlists()
        if tracks:self.player.set_queue(tracks,0,True)
        msg=f"{name}: matched {len(tracks)} track{'s' if len(tracks)!=1 else ''}"
        if unresolved:msg+=f" · {len(unresolved)} unresolved"
        self.statusBar().showMessage(msg,7000)

    # ------------------------------- bridge / external control
    def _control_request(self, action, args):
        event=threading.Event(); box={}
        self.externalCommand.emit(str(action),dict(args or {}),(event,box))
        if not event.wait(12):raise RuntimeError("Melodex GUI did not answer the control request")
        if box.get("error"):raise RuntimeError(str(box["error"]))
        return box.get("result")

    def _on_external_command(self,action,args,reply):
        event,box=reply
        try:
            action=str(action or ""); args=dict(args or {})
            if action=="status":
                result=self.player.status(); result["page"]=self.current_page; result["taste"]=self.state.taste_summary()
            elif action=="set_queue":
                tracks=[dict(x) for x in list(args.get("tracks") or []) if isinstance(x,dict)]; self.player.set_queue(tracks,int(args.get("start",0)),bool(args.get("autoplay",True))); result=self.player.status()
            elif action=="append_queue":
                tracks=[dict(x) for x in list(args.get("tracks") or []) if isinstance(x,dict)]; self.player.append_queue(tracks,bool(args.get("autoplay",False))); result=self.player.status()
            elif action=="play_pause":self.player.play_pause(); result=self.player.status()
            elif action=="next":self.player.next(); result=self.player.status()
            elif action=="previous":self.player.previous(); result=self.player.status()
            elif action=="stop":self.player.stop(); result=self.player.status()
            elif action=="clear_queue":self.player.clear_queue(); result=self.player.status()
            elif action=="seek_ms":self.player.seek(int(args.get("value",0))); result=self.player.status()
            elif action=="set_volume":self.player.set_volume(float(args.get("value",1.0))); result=self.player.status()
            elif action=="flow_queue":self._flow_queue(); result={"started":True,"queue_length":len(self.player.queue)}
            elif action=="love_current":self._feedback(True); result={"recorded":bool(self.current_track)}
            elif action=="dislike_current":self._feedback(False); result={"recorded":bool(self.current_track)}
            elif action=="keep_current":self._keep(); result={"recorded":bool(self.current_track)}
            elif action=="save_moment":
                if self.current_track:
                    moment_id=self.state.save_moment(self.current_track,self.player.players[self.player.active].position(),str(args.get("label", ""))); result={"saved":True,"id":moment_id}
                else:result={"saved":False,"reason":"nothing playing"}
            elif action=="open_view":
                view=str(args.get("view","home")); self.open_page(view if view in self.pages else "home"); result={"page":self.current_page}
            else:raise RuntimeError(f"Unsupported control action: {action}")
            box["result"]=result
        except Exception as exc:box["error"]=str(exc)
        finally:event.set()

    def _start_local_bridge(self):
        if self.bridge:return
        try:
            self.bridge=ProviderBridge(self.providers,"127.0.0.1",0,controller=self._control_request,state_path=self.data_dir/"bridge.json"); self.bridge.start()
        except Exception as exc:
            self.bridge=None; self.statusBar().showMessage(f"AI control bridge could not start: {exc}",7000)

    def _restart_bridge(self,host):
        token=self.bridge.token if self.bridge else ""; port=self.bridge.port if self.bridge else 0
        if self.bridge:self.bridge.stop()
        self.bridge=ProviderBridge(self.providers,host,port,token=token,controller=self._control_request,state_path=self.data_dir/"bridge.json"); self.bridge.start()

    def _bridge_dialog(self):
        if not self.bridge:
            self._start_local_bridge()
            if not self.bridge:return
        if self.bridge.host=="127.0.0.1":
            choice=QMessageBox.question(self,"Provider Bridge",f"The private AI control bridge is running locally on port {self.bridge.port}.\n\nAllow phones/computers on your LAN to use the provider bridge too?\n\nChoose No to keep it local-only.",QMessageBox.Yes|QMessageBox.No)
            if choice==QMessageBox.Yes:
                try:self._restart_bridge("0.0.0.0"); QMessageBox.information(self,"Provider Bridge",f"LAN bridge enabled on port {self.bridge.port}.\n\nBearer token:\n{self.bridge.token}\n\nKeep this token private.")
                except Exception as exc:self.statusBar().showMessage(str(exc),7000)
        else:
            choice=QMessageBox.question(self,"Provider Bridge",f"The bridge currently accepts LAN connections on port {self.bridge.port}.\n\nRestrict it to this computer only?",QMessageBox.Yes|QMessageBox.No)
            if choice==QMessageBox.Yes:
                try:self._restart_bridge("127.0.0.1"); self.statusBar().showMessage("Provider bridge restricted to this computer",4000)
                except Exception as exc:self.statusBar().showMessage(str(exc),7000)

    # ------------------------------- helpers
    def _run_async(self,fn,done):
        sig=WorkerSignals(); sig.done.connect(done); sig.error.connect(lambda e:QMessageBox.warning(self,"Melodex",e)); self._last_worker=sig
        def work():
            try:sig.done.emit(fn())
            except Exception as exc:sig.error.emit(str(exc))
        threading.Thread(target=work,daemon=True).start()

    def closeEvent(self,event):
        if self.bridge:self.bridge.stop()
        self.player.close(); self.metadata.close(); self.providers.close(); self.flow.close(); self.state.close(); super().closeEvent(event)
