from __future__ import annotations

from collections import defaultdict
from typing import Any

from PySide6.QtCore import QEvent, QSize, Qt, Signal
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


def _track_key(track: dict[str, Any]) -> str:
    local_path = str(track.get("local_path") or "").strip()
    if local_path:
        return "local:" + local_path
    return (
        str(track.get("provider_id") or "")
        + ":"
        + str(track.get("track_id") or "")
    )


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
        self.setFixedSize(176, 286)
        self.setMouseTracking(True)
        self.has_real_cover = False

        outer = QVBoxLayout(self)
        outer.setContentsMargins(7, 7, 7, 9)
        outer.setSpacing(5)

        self.cover = CoverLabel(160)
        self.cover.set_cover("", title=str(album.get("title") or ""), key=self.key)
        outer.addWidget(self.cover, 0, Qt.AlignHCenter)

        title = QLabel(str(album.get("title") or "Unknown album"))
        title.setObjectName("albumCardTitle")
        title.setWordWrap(True)
        title.setFixedHeight(34)
        title.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        title.setToolTip(str(album.get("title") or "Unknown album"))
        outer.addWidget(title)

        meta = str(album.get("artist") or "Unknown artist")
        year = int(album.get("year") or 0)
        if year:
            meta += f"  ·  {year}"
        artist = QLabel(meta)
        artist.setObjectName("albumCardMeta")
        artist.setFixedHeight(18)
        artist.setToolTip(meta)
        outer.addWidget(artist)

        self.actions = QWidget()
        self.actions.setFixedHeight(36)
        actions = QHBoxLayout(self.actions)
        actions.setContentsMargins(0, 3, 0, 0)
        actions.setSpacing(5)
        self.play_button = QPushButton("▶ Play")
        self.play_button.setObjectName("miniButton")
        self.queue_button = QPushButton("+ Queue")
        self.queue_button.setObjectName("miniButton")
        set_help(
            self.play_button,
            "Play album",
            "Starts this album from track one and keeps its disc and track order.",
        )
        set_help(
            self.queue_button,
            "Queue album",
            "Adds the whole album after the music already in your queue.",
        )
        self.play_button.clicked.connect(lambda: self.playRequested.emit(dict(self.album)))
        self.queue_button.clicked.connect(lambda: self.queueRequested.emit(dict(self.album)))
        actions.addWidget(self.play_button)
        actions.addWidget(self.queue_button)
        self.play_button.hide()
        self.queue_button.hide()
        outer.addWidget(self.actions)

        self.setToolTip(
            f"<b>{album.get('title') or 'Unknown album'}</b><br>"
            f"{album.get('artist') or 'Unknown artist'}<br>"
            f"{int(album.get('track_count') or 0)} tracks"
        )

    def set_cover(self, path: str) -> None:
        self.has_real_cover = bool(str(path or "").strip())
        self.cover.set_cover(
            path,
            title=str(self.album.get("title") or ""),
            key=self.key,
        )

    def enterEvent(self, event):
        self.play_button.show()
        self.queue_button.show()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.play_button.hide()
        self.queue_button.hide()
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


class ArtistCard(QFrame):
    openRequested = Signal(object)
    playRequested = Signal(object)

    def __init__(self, artist: dict[str, Any], parent=None):
        super().__init__(parent)
        self.artist = dict(artist)
        self.key = str(artist.get("key") or "")
        self.has_artist_photo = False
        self.setObjectName("albumCard")
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(176, 272)
        self.setMouseTracking(True)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(7, 7, 7, 9)
        outer.setSpacing(5)

        self.image = CoverLabel(160)
        self.image.set_cover(
            "",
            title=str(artist.get("name") or "Artist"),
            key="artist:" + self.key,
        )
        outer.addWidget(self.image, 0, Qt.AlignHCenter)

        title = QLabel(str(artist.get("name") or "Unknown artist"))
        title.setObjectName("albumCardTitle")
        title.setWordWrap(True)
        title.setFixedHeight(34)
        outer.addWidget(title)

        albums = int(artist.get("album_count") or 0)
        tracks = int(artist.get("track_count") or 0)
        meta = QLabel(
            f"{albums} album{'s' if albums != 1 else ''}  ·  "
            f"{tracks} track{'s' if tracks != 1 else ''}"
        )
        meta.setObjectName("albumCardMeta")
        meta.setFixedHeight(18)
        outer.addWidget(meta)

        self.actions = QWidget()
        self.actions.setFixedHeight(36)
        row = QHBoxLayout(self.actions)
        row.setContentsMargins(0, 3, 0, 0)
        row.setSpacing(5)
        self.open_button = QPushButton("View")
        self.open_button.setObjectName("miniButton")
        self.play_button = QPushButton("▶ Play")
        self.play_button.setObjectName("miniButton")
        self.open_button.clicked.connect(lambda: self.openRequested.emit(dict(self.artist)))
        self.play_button.clicked.connect(lambda: self.playRequested.emit(dict(self.artist)))
        set_help(
            self.open_button,
            "View artist albums",
            "Switch to Albums and show records associated with this artist.",
        )
        set_help(
            self.play_button,
            "Play artist",
            "Starts the local tracks Melodex currently has for this artist.",
        )
        row.addWidget(self.open_button)
        row.addWidget(self.play_button)
        self.open_button.hide()
        self.play_button.hide()
        outer.addWidget(self.actions)

    def set_image(self, path: str, *, artist_photo: bool = False) -> None:
        if artist_photo and path:
            self.has_artist_photo = True
        self.image.set_cover(
            path,
            title=str(self.artist.get("name") or ""),
            key="artist:" + self.key,
        )

    def enterEvent(self, event):
        self.open_button.show()
        self.play_button.show()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.open_button.hide()
        self.play_button.hide()
        super().leaveEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.openRequested.emit(dict(self.artist))
            event.accept()
            return
        super().mouseDoubleClickEvent(event)


class TrackRow(QFrame):
    playRequested = Signal(object)
    queueRequested = Signal(object)
    editRequested = Signal(object)

    def __init__(self, track: dict[str, Any], parent=None):
        super().__init__(parent)
        self.track = dict(track)
        self.setObjectName("trackRow")
        self.setMinimumHeight(76)

        outer = QHBoxLayout(self)
        outer.setContentsMargins(8, 7, 10, 7)
        outer.setSpacing(12)

        self.cover = CoverLabel(58)
        self.cover.set_cover(
            "",
            title=str(track.get("album") or track.get("title") or ""),
            key=_track_key(track),
        )
        outer.addWidget(self.cover)

        text = QVBoxLayout()
        text.setSpacing(3)
        title = QLabel(str(track.get("title") or "Unknown track"))
        title.setObjectName("trackTitle")
        title.setWordWrap(False)
        text.addWidget(title)
        artist = str(track.get("artist") or "Unknown artist")
        album = str(track.get("album") or "")
        meta_text = artist + (f"  ·  {album}" if album else "")
        meta = QLabel(meta_text)
        meta.setObjectName("trackMeta")
        meta.setToolTip(meta_text)
        text.addWidget(meta)
        outer.addLayout(text, 1)

        if _norm(artist) == "unknown artist":
            badge = QLabel("Needs artist")
            badge.setObjectName("warningPill")
            outer.addWidget(badge)

        play = QPushButton("▶")
        play.setObjectName("miniButton")
        queue = QPushButton("+ Queue")
        queue.setObjectName("miniButton")
        edit = QPushButton("Edit")
        edit.setObjectName("miniButton")
        play.clicked.connect(lambda: self.playRequested.emit(dict(self.track)))
        queue.clicked.connect(lambda: self.queueRequested.emit(dict(self.track)))
        edit.clicked.connect(lambda: self.editRequested.emit(dict(self.track)))
        set_help(play, "Play track", "Play this track now.")
        set_help(queue, "Queue track", "Add this track after the music already queued.")
        set_help(
            edit,
            "Correct details",
            "Correct artist, title, album or year inside Melodex. Your audio file is not rewritten.",
        )
        outer.addWidget(play)
        outer.addWidget(queue)
        outer.addWidget(edit)

    def set_cover(self, path: str) -> None:
        self.cover.set_cover(
            path,
            title=str(self.track.get("album") or self.track.get("title") or ""),
            key=_track_key(self.track),
        )


class LibraryBrowser(QWidget):
    playAlbumRequested = Signal(object)
    queueAlbumRequested = Signal(object)
    playArtistRequested = Signal(object)
    playTrackRequested = Signal(object)
    queueTrackRequested = Signal(object)
    editMetadataRequested = Signal(object)
    addFolderRequested = Signal()
    rescanRequested = Signal()
    albumWallRequested = Signal()
    momentsRequested = Signal()
    artworkRequested = Signal(object)
    onlineArtworkRequested = Signal(object)
    artistImageRequested = Signal(object)
    artistImageCacheRequested = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.catalog: list[dict[str, Any]] = []
        self.albums: list[dict[str, Any]] = []
        self.cards: dict[str, AlbumCard] = {}
        self.artist_rows: list[dict[str, Any]] = []
        self.artist_cards: dict[str, ArtistCard] = {}
        self.track_rows: dict[str, TrackRow] = {}
        self.track_items: dict[str, QListWidgetItem] = {}
        self.track_album_key: dict[str, str] = {}
        self.artwork_paths: dict[str, str] = {}
        self.artist_image_paths: dict[str, str] = {}
        self._visible_albums: list[dict[str, Any]] = []
        self._visible_artists: list[dict[str, Any]] = []
        self._art_requested: set[str] = set()
        self._artist_art_requested: set[str] = set()
        self._artist_lookup_queue: list[dict[str, Any]] = []
        self._artist_lookup_inflight = 0
        self._artist_lookup_active = False
        self._tracks_built = False

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
        self.images_button = QPushButton("Find missing artwork")
        self.images_button.setObjectName("quietButton")
        self.images_button.clicked.connect(self._request_online_artwork)
        set_help(
            add,
            "Add music",
            "Choose a folder containing your own music files. Melodex indexes it locally.",
        )
        set_help(
            rescan,
            "Rescan library",
            "Checks your selected folders again for new, removed or retagged music. Your Melodex corrections are kept.",
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
        set_help(
            self.images_button,
            "Find missing images",
            "Looks online for missing cover art or artist photos for the current view. Matches are cached and remembered for later visits.",
        )
        actions.addWidget(add)
        actions.addWidget(rescan)
        actions.addWidget(wall)
        actions.addWidget(moments)
        actions.addWidget(self.images_button)
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
        self.artist_page = QWidget()
        artist_page_layout = QVBoxLayout(self.artist_page)
        artist_page_layout.setContentsMargins(0, 0, 0, 0)
        self.artist_photo_note = QLabel(
            "Artist view uses real artist photos when Melodex can identify them. "
            "Choose Get artist photos to look up missing images; album covers are not used as artist portraits."
        )
        self.artist_photo_note.setWordWrap(True)
        self.artist_photo_note.setStyleSheet("color:#8f9bad")
        artist_page_layout.addWidget(self.artist_photo_note)

        self.artist_scroll = QScrollArea()
        self.artist_scroll.setWidgetResizable(True)
        self.artist_scroll.setFrameShape(QFrame.NoFrame)
        self.artist_scroll.viewport().installEventFilter(self)
        self.artist_container = QWidget()
        self.artist_grid = QGridLayout(self.artist_container)
        self.artist_grid.setContentsMargins(0, 0, 0, 0)
        self.artist_grid.setHorizontalSpacing(14)
        self.artist_grid.setVerticalSpacing(16)
        self.artist_grid.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.artist_scroll.setWidget(self.artist_container)
        artist_page_layout.addWidget(self.artist_scroll, 1)
        self.stack.addWidget(self.artist_page)

        # Tracks
        self.track_list = QListWidget()
        self.track_list.setObjectName("visualTrackList")
        self.track_list.setSpacing(4)
        self.track_list.itemDoubleClicked.connect(self._track_activated)
        self.stack.addWidget(self.track_list)

        self.empty = EmptyState(
            "Your library is waiting",
            "Add a folder of music and Melodex will organise it into albums while keeping everything on this computer.",
            "Add my music",
        )
        self.empty.actionRequested.connect(self.addFolderRequested)
        self.stack.addWidget(self.empty)

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Resize:
            if watched is self.album_scroll.viewport():
                self._layout_album_cards()
            elif watched is self.artist_scroll.viewport():
                self._layout_artist_cards()
        return super().eventFilter(watched, event)

    def _clear_grid(self, grid: QGridLayout) -> None:
        while grid.count():
            item = grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)

    def set_catalog(self, catalog: list[dict[str, Any]]) -> None:
        for card in list(self.cards.values()):
            card.setParent(None)
            card.deleteLater()
        for card in list(self.artist_cards.values()):
            card.setParent(None)
            card.deleteLater()
        self.cards.clear()
        self.artist_cards.clear()
        self.track_rows.clear()
        self.track_items.clear()
        self._clear_grid(self.album_grid)
        self._clear_grid(self.artist_grid)
        self.track_list.clear()
        self._tracks_built = False

        self.catalog = [dict(item) for item in catalog if isinstance(item, dict)]
        self._art_requested.clear()
        self._artist_art_requested.clear()
        if not self.catalog:
            self.albums = []
            self.artist_rows = []
            self.stack.setCurrentWidget(self.empty)
            return

        wall = build_album_wall(self.catalog, max_albums=4000)
        self.albums = [
            dict(album)
            for album in list(wall.get("albums") or [])
            if isinstance(album, dict)
        ]
        self.track_album_key = {}
        for album in self.albums:
            album_key = str(album.get("key") or "")
            for track in list(album.get("tracks") or []):
                if isinstance(track, dict):
                    self.track_album_key[_track_key(track)] = album_key

        self._rebuild_artists()
        self._apply_filter()
        self.set_view(self.current_view())
        self._request_artwork()
        self._request_cached_artist_images()

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
        if name == "tracks" and not self._tracks_built:
            self._rebuild_tracks()
            self._tracks_built = True
        target = {
            "albums": self.album_page,
            "artists": self.artist_page,
            "tracks": self.track_list,
        }[name]
        self.stack.setCurrentWidget(target)
        if name == "artists":
            self.images_button.setText("Get artist photos")
            self.images_button.setObjectName("primaryButton")
        else:
            self.images_button.setText("Find missing artwork")
            self.images_button.setObjectName("quietButton")
        self.images_button.style().unpolish(self.images_button)
        self.images_button.style().polish(self.images_button)
        self.images_button.update()
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
        self._visible_artists = [
            artist
            for artist in self.artist_rows
            if not query
            or query
            in _norm(
                f"{artist.get('name','')} "
                + " ".join(str(x.get('album') or '') for x in artist.get('tracks',[]))
            )
        ]
        self._layout_album_cards()
        if self.current_view() == "artists" or self.artist_cards:
            self._layout_artist_cards()

        for key, item in self.track_items.items():
            row = self.track_rows.get(key)
            haystack = ""
            if row is not None:
                track = row.track
                haystack = _norm(
                    f"{track.get('artist','')} {track.get('title','')} {track.get('album','')}"
                )
            item.setHidden(bool(query) and query not in haystack)

    def _layout_album_cards(self) -> None:
        self._clear_grid(self.album_grid)
        width = max(400, self.album_scroll.viewport().width())
        columns = max(2, min(8, width // 190))
        for index, album in enumerate(self._visible_albums):
            key = str(album.get("key") or "")
            card = self.cards.get(key)
            if card is None:
                card = AlbumCard(album)
                card.playRequested.connect(self.playAlbumRequested)
                card.queueRequested.connect(self.queueAlbumRequested)
                self.cards[key] = card
                path = self.artwork_paths.get(key, "")
                if path:
                    card.set_cover(path)
            row, column = divmod(index, columns)
            self.album_grid.addWidget(card, row, column, Qt.AlignTop)
        self.album_container.adjustSize()

    def _layout_artist_cards(self) -> None:
        self._clear_grid(self.artist_grid)
        width = max(400, self.artist_scroll.viewport().width())
        columns = max(2, min(8, width // 190))
        for index, artist in enumerate(self._visible_artists):
            key = str(artist.get("key") or "")
            card = self.artist_cards.get(key)
            if card is None:
                card = ArtistCard(artist)
                card.openRequested.connect(self._artist_opened)
                card.playRequested.connect(self.playArtistRequested)
                self.artist_cards[key] = card
                artist_path=self.artist_image_paths.get(key,"")
                if artist_path:
                    card.set_image(artist_path,artist_photo=True)
            row, column = divmod(index, columns)
            self.artist_grid.addWidget(card, row, column, Qt.AlignTop)
        self.artist_container.adjustSize()

    def _rebuild_artists(self) -> None:
        grouped: dict[str, dict[str, Any]] = defaultdict(
            lambda: {"albums": set(), "tracks": [], "name": "", "album_keys": []}
        )
        for track in self.catalog:
            artist = str(track.get("artist") or "Unknown artist").strip() or "Unknown artist"
            key = _norm(artist) or "unknown artist"
            row = grouped[key]
            row["name"] = artist
            row["tracks"].append(dict(track))
            album = str(track.get("album") or "").strip()
            if album:
                row["albums"].add(album)
            album_key = self.track_album_key.get(_track_key(track), "")
            if album_key and album_key not in row["album_keys"]:
                row["album_keys"].append(album_key)

        rows: list[dict[str, Any]] = []
        for key, row in grouped.items():
            tracks = sorted(
                [dict(x) for x in row["tracks"]],
                key=lambda item: (
                    int(item.get("year") or 0),
                    _norm(item.get("album")),
                    int(item.get("disc_number") or 0),
                    int(item.get("track_number") or 0),
                    _norm(item.get("title")),
                ),
            )
            rows.append({
                "key": key,
                "name": str(row["name"] or "Unknown artist"),
                "album_count": len(row["albums"]),
                "track_count": len(tracks),
                "tracks": tracks,
                "album_keys": list(row["album_keys"]),
                "representative_track": dict(tracks[0]) if tracks else {},
            })
        self.artist_rows = sorted(rows, key=lambda row: _norm(row.get("name")))

    def _rebuild_tracks(self) -> None:
        self.track_list.clear()
        self.track_rows.clear()
        self.track_items.clear()
        ordered = sorted(
            self.catalog,
            key=lambda item: (
                _norm(item.get("artist")),
                _norm(item.get("album")),
                int(item.get("disc_number") or 0),
                int(item.get("track_number") or 0),
                _norm(item.get("title")),
            ),
        )
        for track in ordered:
            key = _track_key(track)
            item = QListWidgetItem()
            item.setData(Qt.UserRole, dict(track))
            item.setText(
                f"{track.get('title') or 'Unknown track'} "
                f"{track.get('artist') or 'Unknown artist'} "
                f"{track.get('album') or ''}"
            )
            item.setSizeHint(QSize(100, 82))
            row = TrackRow(track)
            row.playRequested.connect(self.playTrackRequested)
            row.queueRequested.connect(self.queueTrackRequested)
            row.editRequested.connect(self.editMetadataRequested)
            album_key = self.track_album_key.get(key, "")
            path = self.artwork_paths.get(album_key, "")
            if path:
                row.set_cover(path)
            self.track_list.addItem(item)
            self.track_list.setItemWidget(item, row)
            self.track_items[key] = item
            self.track_rows[key] = row

    def _artist_opened(self, artist: object) -> None:
        if not isinstance(artist, dict):
            return
        name = str(artist.get("name") or "")
        if not name:
            return
        self.search.setText(name)
        self.set_view("albums")

    def _track_activated(self, item: QListWidgetItem) -> None:
        track = item.data(Qt.UserRole)
        if isinstance(track, dict):
            self.playTrackRequested.emit(dict(track))

    def _request_artwork(self) -> None:
        batch = []
        for album in self.albums[:300]:
            key = str(album.get("key") or "")
            if not key or key in self._art_requested:
                continue
            track = dict(album.get("representative_track") or {})
            if not track:
                continue
            self._art_requested.add(key)
            batch.append({
                "key": key,
                "track": track,
                "tracks": [dict(x) for x in list(album.get("tracks") or []) if isinstance(x,dict)],
            })
        if batch:
            self.artworkRequested.emit(batch)

    def _request_cached_artist_images(self) -> None:
        batch=[]
        for artist in self.artist_rows:
            key=str(artist.get("key") or "")
            track=dict(artist.get("representative_track") or {})
            name=str(artist.get("name") or "")
            if key and track and name and _norm(name)!="unknown artist":
                batch.append({"key":key,"artist":name,"track":track})
        if batch:
            self.artistImageCacheRequested.emit(batch)

    def _request_online_artwork(self) -> None:
        if self.current_view() == "artists":
            artists = self._visible_artists if self._visible_artists else self.artist_rows
            self._artist_lookup_queue = []
            self._artist_lookup_inflight = 0
            for artist in artists:
                key = str(artist.get("key") or "")
                card = self.artist_cards.get(key)
                if (
                    not key
                    or card is None
                    or card.has_artist_photo
                    or _norm(artist.get("name")) == "unknown artist"
                ):
                    continue
                track = dict(artist.get("representative_track") or {})
                if track:
                    self._artist_lookup_queue.append({
                        "key": key,
                        "artist": str(artist.get("name") or ""),
                        "track": track,
                    })
            self._artist_lookup_active = bool(self._artist_lookup_queue)
            self._emit_next_artist_lookup_batch()
            return

        batch = []
        albums = self._visible_albums if self._visible_albums else self.albums
        for album in albums:
            key = str(album.get("key") or "")
            card = self.cards.get(key)
            if not key or card is None or card.has_real_cover:
                continue
            track = dict(album.get("representative_track") or {})
            if track:
                batch.append({
                    "key": key,
                    "track": track,
                    "tracks": [dict(x) for x in list(album.get("tracks") or []) if isinstance(x,dict)],
                })
            if len(batch) >= 12:
                break
        if batch:
            self.onlineArtworkRequested.emit(batch)

    def _emit_next_artist_lookup_batch(self) -> bool:
        if not self._artist_lookup_active or not self._artist_lookup_queue:
            self._artist_lookup_active = False
            self._artist_lookup_inflight = 0
            return False
        batch=self._artist_lookup_queue[:10]
        self._artist_lookup_queue=self._artist_lookup_queue[10:]
        self._artist_lookup_inflight=len(batch)
        for row in batch:
            key=str(row.get("key") or "")
            if key:
                self._artist_art_requested.add(key)
        self.artistImageRequested.emit(batch)
        return True

    def continue_artist_image_lookup(self) -> bool:
        """Continue an explicit whole-library portrait lookup after one batch."""
        self._artist_lookup_inflight = 0
        return self._emit_next_artist_lookup_batch()

    def artist_image_lookup_remaining(self) -> int:
        return len(self._artist_lookup_queue) + int(self._artist_lookup_inflight or 0)

    def set_artwork(self, mapping: dict[str, str]) -> None:
        for key, path in dict(mapping or {}).items():
            key = str(key)
            path = str(path or "")
            if not path:
                continue
            self.artwork_paths[key] = path
            card = self.cards.get(key)
            if card is not None:
                card.set_cover(path)

            for track_key, album_key in self.track_album_key.items():
                if str(album_key) != key:
                    continue
                row = self.track_rows.get(track_key)
                if row is not None:
                    row.set_cover(path)

    def set_artist_images(self, mapping: dict[str, str]) -> None:
        for key, path in dict(mapping or {}).items():
            key=str(key)
            path=str(path or "")
            if path:
                self.artist_image_paths[key]=path
            card = self.artist_cards.get(key)
            if card is not None and path:
                card.set_image(path, artist_photo=True)
            elif not path:
                self._artist_art_requested.discard(key)


__all__ = ["AlbumCard", "ArtistCard", "TrackRow", "LibraryBrowser"]
