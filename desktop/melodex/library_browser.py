from __future__ import annotations

from collections import defaultdict
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from .album_wall_model import build_album_wall
from .ux_components import CoverLabel, EmptyState, set_help


def _norm(value: Any) -> str:
    return " ".join(str(value or "").casefold().split())


class AlbumCard(QFrame):
    playRequested = Signal(object)
    queueRequested = Signal(object)
    selected = Signal(object)

    def __init__(self, album: dict[str, Any], parent=None):
        super().__init__(parent)
        self.album = dict(album)
        self.key = str(album.get("key") or "")
        self.setObjectName("albumCard")
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedWidth(176)
        self.setMinimumHeight(238)
        self.setMouseTracking(True)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(7, 7, 7, 9)
        outer.setSpacing(5)

        self.cover = CoverLabel(160)
        self.cover.set_cover(
            "",
            title=str(album.get("title") or ""),
            key=self.key,
        )
        outer.addWidget(self.cover, 0, Qt.AlignHCenter)

        title = QLabel(str(album.get("title") or "Unknown album"))
        title.setObjectName("albumCardTitle")
        title.setWordWrap(False)
        title.setToolTip(str(album.get("title") or "Unknown album"))
        outer.addWidget(title)

        meta = str(album.get("artist") or "Unknown artist")
        year = int(album.get("year") or 0)
        if year:
            meta += f"  ·  {year}"
        artist = QLabel(meta)
        artist.setObjectName("albumCardMeta")
        artist.setToolTip(meta)
        outer.addWidget(artist)

        self.actions = QWidget()
        actions = QHBoxLayout(self.actions)
        actions.setContentsMargins(0, 3, 0, 0)
        actions.setSpacing(5)
        play = QPushButton("▶ Play")
        play.setObjectName("miniButton")
        queue = QPushButton("+ Queue")
        queue.setObjectName("miniButton")
        set_help(
            play,
            "Play album",
            "Starts this album from track one and keeps its disc and track order.",
        )
        set_help(
            queue,
            "Queue album",
            "Adds the whole album after the music already in your queue.",
        )
        play.clicked.connect(lambda: self.playRequested.emit(dict(self.album)))
        queue.clicked.connect(lambda: self.queueRequested.emit(dict(self.album)))
        actions.addWidget(play)
        actions.addWidget(queue)
        self.actions.hide()
        outer.addWidget(self.actions)

        self.setToolTip(
            f"<b>{album.get('title') or 'Unknown album'}</b><br>"
            f"{album.get('artist') or 'Unknown artist'}<br>"
            f"{int(album.get('track_count') or 0)} tracks"
        )

    def set_cover(self, path: str) -> None:
        self.cover.set_cover(
            path,
            title=str(self.album.get("title") or ""),
            key=self.key,
        )

    def enterEvent(self, event):
        self.actions.show()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.actions.hide()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.selected.emit(dict(self.album))
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.playRequested.emit(dict(self.album))
            event.accept()
            return
        super().mouseDoubleClickEvent(event)


class LibraryBrowser(QWidget):
    playAlbumRequested = Signal(object)
    queueAlbumRequested = Signal(object)
    playTrackRequested = Signal(object)
    addFolderRequested = Signal()
    rescanRequested = Signal()
    albumWallRequested = Signal()
    momentsRequested = Signal()
    artworkRequested = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.catalog: list[dict[str, Any]] = []
        self.albums: list[dict[str, Any]] = []
        self.cards: dict[str, AlbumCard] = {}
        self._visible_albums: list[dict[str, Any]] = []
        self._art_requested: set[str] = set()
        self._last_columns = 0

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(12)

        top = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search your music…")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._apply_filter)
        top.addWidget(self.search, 1)

        self.view_group = QButtonGroup(self)
        self.view_group.setExclusive(True)
        self.view_buttons: dict[str, QPushButton] = {}
        for index, (key, label) in enumerate(
            (("albums", "Albums"), ("artists", "Artists"), ("tracks", "Tracks"))
        ):
            button = QPushButton(label)
            button.setCheckable(True)
            button.setObjectName("segmentButton")
            button.clicked.connect(lambda _checked=False, name=key: self.set_view(name))
            self.view_group.addButton(button, index)
            self.view_buttons[key] = button
            top.addWidget(button)
        self.view_buttons["albums"].setChecked(True)
        outer.addLayout(top)

        actions = QHBoxLayout()
        add = QPushButton("+ Add music")
        add.setObjectName("secondaryButton")
        add.clicked.connect(self.addFolderRequested)
        rescan = QPushButton("Rescan")
        rescan.setObjectName("quietButton")
        rescan.clicked.connect(self.rescanRequested)
        wall = QPushButton("Explore Album Wall")
        wall.setObjectName("quietButton")
        wall.clicked.connect(self.albumWallRequested)
        moments = QPushButton("Moments")
        moments.setObjectName("quietButton")
        moments.clicked.connect(self.momentsRequested)
        set_help(
            add,
            "Add music",
            "Choose a folder containing your own music files. Melodex indexes it locally.",
        )
        set_help(
            rescan,
            "Rescan library",
            "Checks your selected folders again for new, removed or retagged music.",
        )
        set_help(
            wall,
            "Album Wall",
            "Browse the same collection spatially instead of alphabetically.",
        )
        set_help(
            moments,
            "Moments",
            "Open the exact positions inside songs that you previously chose to remember.",
        )
        actions.addWidget(add)
        actions.addWidget(rescan)
        actions.addWidget(wall)
        actions.addWidget(moments)
        actions.addStretch(1)
        outer.addLayout(actions)

        self.stack = QStackedWidget()
        outer.addWidget(self.stack, 1)

        # Albums
        self.album_page = QWidget()
        album_page_layout = QVBoxLayout(self.album_page)
        album_page_layout.setContentsMargins(0, 0, 0, 0)
        self.album_scroll = QScrollArea()
        self.album_scroll.setWidgetResizable(True)
        self.album_scroll.setFrameShape(QFrame.NoFrame)
        self.album_scroll.viewport().installEventFilter(self)
        self.album_container = QWidget()
        self.album_grid = QGridLayout(self.album_container)
        self.album_grid.setContentsMargins(0, 0, 0, 0)
        self.album_grid.setHorizontalSpacing(14)
        self.album_grid.setVerticalSpacing(16)
        self.album_grid.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.album_scroll.setWidget(self.album_container)
        album_page_layout.addWidget(self.album_scroll, 1)
        self.stack.addWidget(self.album_page)

        # Artists
        self.artist_list = QListWidget()
        self.artist_list.setObjectName("libraryList")
        self.artist_list.itemActivated.connect(self._artist_activated)
        self.stack.addWidget(self.artist_list)

        # Tracks
        self.track_list = QListWidget()
        self.track_list.setObjectName("libraryList")
        self.track_list.itemActivated.connect(self._track_activated)
        self.stack.addWidget(self.track_list)

        self.empty = EmptyState(
            "Your library is waiting",
            "Add a folder of music and Melodex will organise it into albums while keeping everything on this computer.",
            "Add my music",
        )
        self.empty.actionRequested.connect(self.addFolderRequested)
        self.stack.addWidget(self.empty)

    def eventFilter(self, watched, event):
        if watched is self.album_scroll.viewport() and event.type() == event.Resize:
            self._layout_cards()
        return super().eventFilter(watched, event)

    def set_catalog(self, catalog: list[dict[str, Any]]) -> None:
        self.catalog = [dict(item) for item in catalog if isinstance(item, dict)]
        self._art_requested.clear()
        if not self.catalog:
            self.albums = []
            self.cards.clear()
            self.stack.setCurrentWidget(self.empty)
            return

        wall = build_album_wall(self.catalog, max_albums=4000)
        self.albums = [
            dict(album)
            for album in list(wall.get("albums") or [])
            if isinstance(album, dict)
        ]
        self._rebuild_artists()
        self._rebuild_tracks()
        self._apply_filter()
        self.set_view(self.current_view())
        self._request_artwork()

    def current_view(self) -> str:
        for key, button in self.view_buttons.items():
            if button.isChecked():
                return key
        return "albums"

    def set_view(self, name: str) -> None:
        if not self.catalog:
            self.stack.setCurrentWidget(self.empty)
            return
        name = str(name or "albums")
        if name not in self.view_buttons:
            name = "albums"
        self.view_buttons[name].setChecked(True)
        target = {
            "albums": self.album_page,
            "artists": self.artist_list,
            "tracks": self.track_list,
        }[name]
        self.stack.setCurrentWidget(target)
        self._apply_filter()

    def _apply_filter(self) -> None:
        if not self.catalog:
            return
        query = _norm(self.search.text())
        self._visible_albums = [
            album
            for album in self.albums
            if not query
            or query
            in _norm(
                f"{album.get('artist','')} {album.get('title','')} "
                + " ".join(str(x) for x in list(album.get("genres") or []))
            )
        ]
        self._layout_cards()

        for row in range(self.artist_list.count()):
            item = self.artist_list.item(row)
            item.setHidden(bool(query) and query not in _norm(item.text()))

        for row in range(self.track_list.count()):
            item = self.track_list.item(row)
            item.setHidden(bool(query) and query not in _norm(item.text()))

    def _layout_cards(self) -> None:
        while self.album_grid.count():
            item = self.album_grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)

        width = max(400, self.album_scroll.viewport().width())
        columns = max(2, min(8, width // 190))
        self._last_columns = columns

        visible_keys = set()
        for index, album in enumerate(self._visible_albums):
            key = str(album.get("key") or "")
            visible_keys.add(key)
            card = self.cards.get(key)
            if card is None:
                card = AlbumCard(album)
                card.playRequested.connect(self.playAlbumRequested)
                card.queueRequested.connect(self.queueAlbumRequested)
                self.cards[key] = card
            row, column = divmod(index, columns)
            self.album_grid.addWidget(card, row, column, Qt.AlignTop)

        self.album_container.adjustSize()

    def _rebuild_artists(self) -> None:
        grouped: dict[str, dict[str, Any]] = defaultdict(
            lambda: {"albums": set(), "tracks": 0, "display": ""}
        )
        for track in self.catalog:
            artist = str(track.get("album_artist") or track.get("artist") or "Unknown artist")
            key = _norm(artist)
            grouped[key]["display"] = artist
            grouped[key]["tracks"] += 1
            album = str(track.get("album") or "").strip()
            if album:
                grouped[key]["albums"].add(album)

        self.artist_list.clear()
        rows = sorted(
            grouped.values(),
            key=lambda row: _norm(row.get("display")),
        )
        for row in rows:
            albums = len(row["albums"])
            tracks = int(row["tracks"])
            item = QListWidgetItem(
                f"{row['display']}\n"
                f"{albums} album{'s' if albums != 1 else ''} · "
                f"{tracks} track{'s' if tracks != 1 else ''}"
            )
            item.setData(Qt.UserRole, str(row["display"]))
            self.artist_list.addItem(item)

    def _rebuild_tracks(self) -> None:
        self.track_list.clear()
        for track in sorted(
            self.catalog,
            key=lambda item: (
                _norm(item.get("artist")),
                _norm(item.get("album")),
                int(item.get("disc_number") or 0),
                int(item.get("track_number") or 0),
                _norm(item.get("title")),
            ),
        ):
            title = str(track.get("title") or "Unknown track")
            artist = str(track.get("artist") or "Unknown artist")
            album = str(track.get("album") or "")
            subtitle = artist + (f"  ·  {album}" if album else "")
            item = QListWidgetItem(f"{title}\n{subtitle}")
            item.setData(Qt.UserRole, dict(track))
            self.track_list.addItem(item)

    def _artist_activated(self, item: QListWidgetItem) -> None:
        artist = str(item.data(Qt.UserRole) or "")
        if not artist:
            return
        self.search.setText(artist)
        self.set_view("albums")

    def _track_activated(self, item: QListWidgetItem) -> None:
        track = item.data(Qt.UserRole)
        if isinstance(track, dict):
            self.playTrackRequested.emit(dict(track))

    def _request_artwork(self) -> None:
        batch = []
        for album in self.albums[:240]:
            key = str(album.get("key") or "")
            if not key or key in self._art_requested:
                continue
            track = dict(album.get("representative_track") or {})
            if not track:
                continue
            self._art_requested.add(key)
            batch.append({"key": key, "track": track})
        if batch:
            self.artworkRequested.emit(batch)

    def set_artwork(self, mapping: dict[str, str]) -> None:
        for key, path in dict(mapping or {}).items():
            card = self.cards.get(str(key))
            if card is not None and path:
                card.set_cover(str(path))


__all__ = ["AlbumCard", "LibraryBrowser"]
