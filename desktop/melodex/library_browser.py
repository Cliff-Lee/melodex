from __future__ import annotations

from collections import defaultdict
import threading
import time
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
    QProgressBar,
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
    photoRequested = Signal(object)

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
        self.play_button = QPushButton("▶")
        self.play_button.setObjectName("miniButton")
        self.photo_button = QPushButton("Photo…")
        self.photo_button.setObjectName("miniButton")
        self.open_button.setMaximumWidth(48)
        self.play_button.setMaximumWidth(42)
        self.photo_button.setMaximumWidth(58)
        self.open_button.clicked.connect(lambda: self.openRequested.emit(dict(self.artist)))
        self.play_button.clicked.connect(lambda: self.playRequested.emit(dict(self.artist)))
        self.photo_button.clicked.connect(lambda: self.photoRequested.emit(dict(self.artist)))
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
        set_help(
            self.photo_button,
            "Choose artist photo",
            "Use a local image when automatic artist-photo lookup cannot find a suitable portrait. Melodex copies it into its own artwork cache.",
        )
        row.addWidget(self.open_button)
        row.addWidget(self.play_button)
        row.addWidget(self.photo_button)
        self.open_button.hide()
        self.play_button.hide()
        self.photo_button.hide()
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
        self.photo_button.show()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.open_button.hide()
        self.play_button.hide()
        self.photo_button.hide()
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
    artistPhotoFileRequested = Signal(object)
    scanPauseRequested = Signal()
    scanCancelRequested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.catalog: list[dict[str, Any]] = []
        self._catalog_revision: int | None = None
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
        self._visible_tracks: list[dict[str, Any]] = []
        self._album_batch_size = 120
        self._artist_batch_size = 120
        self._track_batch_size = 300
        self._album_render_limit = self._album_batch_size
        self._artist_render_limit = self._artist_batch_size
        self._track_render_limit = self._track_batch_size
        self._track_more_item: QListWidgetItem | None = None
        self._art_requested: set[str] = set()
        self._artist_art_requested: set[str] = set()
        self._artwork_batch_size = 4
        self._last_artwork_kind = ""
        self._artist_lookup_queue: list[dict[str, Any]] = []
        self._artist_lookup_inflight = 0
        self._artist_lookup_inflight_rows: list[dict[str, Any]] = []
        self._artist_lookup_active = False
        self._artist_lookup_paused = False
        self._artist_lookup_cancel_requested = False
        self._artist_lookup_current = ""
        self._artist_lookup_failures: list[dict[str, Any]] = []
        self._artist_lookup_stats = self._new_lookup_stats()
        self._album_lookup_queue: list[dict[str, Any]] = []
        self._album_lookup_inflight = 0
        self._album_lookup_inflight_rows: list[dict[str, Any]] = []
        self._album_lookup_active = False
        self._album_lookup_paused = False
        self._album_lookup_cancel_requested = False
        self._album_lookup_current = ""
        self._album_lookup_failures: list[dict[str, Any]] = []
        self._album_lookup_stats = self._new_lookup_stats()
        self._tracks_built = False
        self.last_catalog_metrics: dict[str, object] = {}
        self.last_filter_metrics: dict[str, object] = {}
        self.last_view_metrics: dict[str, object] = {}
        self._scan_active = False
        self._scan_paused = False

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(12)

        top = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search your music…")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._search_changed)
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

        self.scan_progress_panel=QFrame()
        self.scan_progress_panel.setObjectName("artworkProgressPanel")
        scan_l=QVBoxLayout(self.scan_progress_panel)
        scan_l.setContentsMargins(12,10,12,10)
        scan_l.setSpacing(7)

        scan_top=QHBoxLayout()
        self.scan_progress_title=QLabel("Indexing your music")
        self.scan_progress_title.setObjectName("artworkProgressTitle")
        self.scan_progress_summary=QLabel("")
        self.scan_progress_summary.setObjectName("artworkProgressSummary")
        scan_top.addWidget(self.scan_progress_title)
        scan_top.addStretch(1)
        scan_top.addWidget(self.scan_progress_summary)
        scan_l.addLayout(scan_top)

        self.scan_progress=QProgressBar()
        self.scan_progress.setRange(0,0)
        self.scan_progress.setTextVisible(True)
        scan_l.addWidget(self.scan_progress)

        scan_detail_row=QHBoxLayout()
        scan_text=QVBoxLayout()
        scan_text.setSpacing(2)
        self.scan_progress_detail=QLabel("")
        self.scan_progress_detail.setObjectName("artworkProgressDetail")
        self.scan_progress_detail.setWordWrap(True)
        self.scan_safety_note=QLabel(
            "Melodex indexes music where it already lives. Audio files are never copied. "
            "Scanning runs separately so you can keep using Melodex."
        )
        self.scan_safety_note.setObjectName("artworkProgressDetail")
        self.scan_safety_note.setWordWrap(True)
        scan_text.addWidget(self.scan_progress_detail)
        scan_text.addWidget(self.scan_safety_note)
        scan_detail_row.addLayout(scan_text,1)

        self.scan_pause_button=QPushButton("Pause")
        self.scan_pause_button.setObjectName("quietButton")
        self.scan_pause_button.clicked.connect(
            lambda _checked=False: self.scanPauseRequested.emit()
        )
        scan_detail_row.addWidget(self.scan_pause_button)

        self.scan_cancel_button=QPushButton("Cancel")
        self.scan_cancel_button.setObjectName("quietButton")
        self.scan_cancel_button.clicked.connect(
            lambda _checked=False: self.scanCancelRequested.emit()
        )
        scan_detail_row.addWidget(self.scan_cancel_button)

        scan_l.addLayout(scan_detail_row)
        self.scan_progress_panel.hide()
        outer.addWidget(self.scan_progress_panel)

        self.artwork_progress_panel=QFrame()
        self.artwork_progress_panel.setObjectName("artworkProgressPanel")
        progress_l=QVBoxLayout(self.artwork_progress_panel)
        progress_l.setContentsMargins(12,10,12,10)
        progress_l.setSpacing(7)

        progress_top=QHBoxLayout()
        self.artwork_progress_title=QLabel("Artwork recovery")
        self.artwork_progress_title.setObjectName("artworkProgressTitle")
        self.artwork_progress_summary=QLabel("")
        self.artwork_progress_summary.setObjectName("artworkProgressSummary")
        progress_top.addWidget(self.artwork_progress_title)
        progress_top.addStretch(1)
        progress_top.addWidget(self.artwork_progress_summary)
        progress_l.addLayout(progress_top)

        self.artwork_progress=QProgressBar()
        self.artwork_progress.setRange(0,1)
        self.artwork_progress.setValue(0)
        self.artwork_progress.setTextVisible(True)
        self.artwork_progress.setFormat("%v / %m")
        progress_l.addWidget(self.artwork_progress)

        progress_actions=QHBoxLayout()
        self.artwork_progress_detail=QLabel("")
        self.artwork_progress_detail.setObjectName("artworkProgressDetail")
        self.artwork_progress_detail.setWordWrap(True)
        progress_actions.addWidget(self.artwork_progress_detail,1)

        self.artwork_pause_button=QPushButton("Pause")
        self.artwork_pause_button.setObjectName("quietButton")
        self.artwork_pause_button.clicked.connect(self._toggle_artwork_lookup_pause)
        progress_actions.addWidget(self.artwork_pause_button)

        self.artwork_cancel_button=QPushButton("Cancel")
        self.artwork_cancel_button.setObjectName("quietButton")
        self.artwork_cancel_button.clicked.connect(self._cancel_artwork_lookup)
        progress_actions.addWidget(self.artwork_cancel_button)

        self.artwork_retry_button=QPushButton("Retry failed")
        self.artwork_retry_button.setObjectName("quietButton")
        self.artwork_retry_button.clicked.connect(self._retry_failed_artwork)
        self.artwork_retry_button.hide()
        progress_actions.addWidget(self.artwork_retry_button)

        progress_l.addLayout(progress_actions)
        self.artwork_progress_panel.hide()
        outer.addWidget(self.artwork_progress_panel)

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
        self.album_more_button = QPushButton("Show more albums")
        self.album_more_button.setObjectName("quietButton")
        self.album_more_button.clicked.connect(self._show_more_albums)
        self.album_more_button.hide()
        album_page_layout.addWidget(self.album_more_button, 0, Qt.AlignHCenter)
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
        self.artist_more_button = QPushButton("Show more artists")
        self.artist_more_button.setObjectName("quietButton")
        self.artist_more_button.clicked.connect(self._show_more_artists)
        self.artist_more_button.hide()
        artist_page_layout.addWidget(self.artist_more_button, 0, Qt.AlignHCenter)
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

    def set_catalog(
        self,
        catalog: list[dict[str, Any]],
        *,
        revision: int | None = None,
    ) -> None:
        if (
            revision is not None
            and self._catalog_revision is not None
            and int(revision) == self._catalog_revision
        ):
            return

        started = time.perf_counter()
        current_thread = threading.current_thread()
        metrics: dict[str, object] = {
            "thread_name": current_thread.name,
            "main_thread": current_thread is threading.main_thread(),
            "track_count": 0,
            "album_count": 0,
            "input_album_count": 0,
            "albums_truncated": 0,
            "tracks_truncated": 0,
            "artist_count": 0,
            "rendered_album_count": 0,
            "rendered_artist_count": 0,
            "rendered_track_count": 0,
            "reset_seconds": 0.0,
            "copy_catalog_seconds": 0.0,
            "album_model_seconds": 0.0,
            "album_index_seconds": 0.0,
            "artist_model_seconds": 0.0,
            "initial_layout_seconds": 0.0,
            "artwork_request_seconds": 0.0,
            "total_seconds": 0.0,
        }

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
        self._track_more_item = None
        self._tracks_built = False
        self._album_render_limit = self._album_batch_size
        self._artist_render_limit = self._artist_batch_size
        self._track_render_limit = self._track_batch_size
        metrics["reset_seconds"] = round(time.perf_counter() - started, 6)

        copy_started = time.perf_counter()
        self.catalog = [dict(item) for item in catalog if isinstance(item, dict)]
        self._catalog_revision = int(revision) if revision is not None else None
        metrics["copy_catalog_seconds"] = round(
            time.perf_counter() - copy_started,
            6,
        )
        metrics["track_count"] = len(self.catalog)
        self._art_requested.clear()
        self._artist_art_requested.clear()
        self._last_artwork_kind = ""
        self._artist_lookup_queue.clear()
        self._artist_lookup_inflight = 0
        self._artist_lookup_inflight_rows = []
        self._artist_lookup_active = False
        self._artist_lookup_paused = False
        self._artist_lookup_cancel_requested = False
        self._artist_lookup_current = ""
        self._artist_lookup_failures = []
        self._artist_lookup_stats = self._new_lookup_stats()
        self._album_lookup_queue.clear()
        self._album_lookup_inflight = 0
        self._album_lookup_inflight_rows = []
        self._album_lookup_active = False
        self._album_lookup_paused = False
        self._album_lookup_cancel_requested = False
        self._album_lookup_current = ""
        self._album_lookup_failures = []
        self._album_lookup_stats = self._new_lookup_stats()
        self.artwork_progress_panel.hide()
        if not self.catalog:
            self.albums = []
            self.artist_rows = []
            self.stack.setCurrentWidget(self.empty)
            metrics["total_seconds"] = round(time.perf_counter() - started, 6)
            self.last_catalog_metrics = metrics
            return

        album_started = time.perf_counter()
        wall = build_album_wall(self.catalog, max_albums=4000)
        self.albums = [
            dict(album)
            for album in list(wall.get("albums") or [])
            if isinstance(album, dict)
        ]
        metrics["album_model_seconds"] = round(
            time.perf_counter() - album_started,
            6,
        )
        metrics["album_count"] = len(self.albums)
        metrics["input_album_count"] = int(
            wall.get("input_album_count") or len(self.albums)
        )
        metrics["albums_truncated"] = int(wall.get("albums_truncated") or 0)
        metrics["tracks_truncated"] = int(wall.get("tracks_truncated") or 0)
        metrics["album_limit"] = int(wall.get("album_limit") or 4000)

        album_index_started = time.perf_counter()
        self.track_album_key = {}
        for album in self.albums:
            album_key = str(album.get("key") or "")
            for track in list(album.get("tracks") or []):
                if isinstance(track, dict):
                    self.track_album_key[_track_key(track)] = album_key
        metrics["album_index_seconds"] = round(
            time.perf_counter() - album_index_started,
            6,
        )

        artist_started = time.perf_counter()
        self._rebuild_artists()
        metrics["artist_model_seconds"] = round(
            time.perf_counter() - artist_started,
            6,
        )
        metrics["artist_count"] = len(self.artist_rows)

        layout_started = time.perf_counter()
        self._apply_filter()
        self.set_view(self.current_view())
        metrics["initial_layout_seconds"] = round(
            time.perf_counter() - layout_started,
            6,
        )
        metrics["rendered_album_count"] = len(self.cards)
        metrics["rendered_artist_count"] = len(self.artist_cards)
        metrics["rendered_track_count"] = len(self.track_rows)

        artwork_started = time.perf_counter()
        self._request_artwork()
        self._request_cached_artist_images()
        metrics["artwork_request_seconds"] = round(
            time.perf_counter() - artwork_started,
            6,
        )
        metrics["total_seconds"] = round(time.perf_counter() - started, 6)
        self.last_catalog_metrics = metrics

    def begin_scan(self, reason: str = "") -> None:
        self._scan_active = True
        self._scan_paused = False
        self.scan_progress_title.setText("Indexing your music")
        self.scan_progress_summary.setText("Discovering files…")
        self.scan_progress_detail.setText(
            "Checking your selected music folders."
        )
        self.scan_progress.setRange(0,0)
        self.scan_progress.setFormat("")
        self.scan_pause_button.setText("Pause")
        self.scan_pause_button.setEnabled(True)
        self.scan_cancel_button.setText("Cancel")
        self.scan_cancel_button.setEnabled(True)
        self.scan_progress_panel.show()

    def set_scan_progress(self, payload: object) -> None:
        if not isinstance(payload,dict):
            return
        phase=str(payload.get("phase") or "")
        found=max(0,int(payload.get("audio_files_seen") or 0))
        completed=max(0,int(payload.get("completed") or 0))
        total=max(0,int(payload.get("total") or 0))
        current=str(payload.get("current") or "").strip()

        self._scan_active=phase not in {"complete","cancelled","error"}
        if phase=="discovering":
            self.scan_progress.setRange(0,0)
            self.scan_progress.setFormat("")
            self.scan_progress_summary.setText(
                f"{found:,} track{'s' if found != 1 else ''} found"
            )
            self.scan_progress_detail.setText(
                f"Discovering files · {current}" if current else "Discovering files…"
            )
        elif phase=="metadata":
            unchanged=max(0,int(payload.get("unchanged") or 0))
            added=max(0,int(payload.get("added") or 0))
            changed=max(0,int(payload.get("changed") or 0))
            if total:
                self.scan_progress.setRange(0,total)
                self.scan_progress.setValue(min(completed,total))
                self.scan_progress.setFormat("%v / %m")
                self.scan_progress_summary.setText(
                    f"Reading metadata · {completed:,} / {total:,}"
                )
                detail_parts=[]
                if unchanged:
                    detail_parts.append(f"{unchanged:,} unchanged")
                if added:
                    detail_parts.append(f"{added:,} new")
                if changed:
                    detail_parts.append(f"{changed:,} changed")
                self.scan_progress_detail.setText(
                    (current + (" · " if detail_parts else "") if current else "")
                    + " · ".join(detail_parts)
                    if current or detail_parts
                    else "Reading track information…"
                )
            elif found:
                self.scan_progress.setRange(0,1)
                self.scan_progress.setValue(1)
                self.scan_progress.setFormat("Up to date")
                self.scan_progress_summary.setText("Metadata already up to date")
                self.scan_progress_detail.setText(
                    f"{unchanged or found:,} unchanged · no audio files need reopening"
                )
            else:
                self.scan_progress.setRange(0,1)
                self.scan_progress.setValue(0)
                self.scan_progress.setFormat("No audio files found")
                self.scan_progress_summary.setText("No supported audio files found")
                self.scan_progress_detail.setText(
                    "No supported audio files were discovered."
                )
        elif phase=="saving":
            self.scan_progress.setRange(0,0)
            self.scan_progress.setFormat("")
            self.scan_progress_summary.setText("Saving library index…")
            self.scan_progress_detail.setText(
                "Saving metadata locally so Melodex can reopen this library without rescanning your music."
            )
        elif phase=="cancelled":
            self.scan_progress_summary.setText("Cancelled")
            self.scan_progress_detail.setText(
                "The existing Melodex library was kept unchanged."
            )
        elif phase=="complete":
            if total:
                self.scan_progress.setRange(0,total)
                self.scan_progress.setValue(total)
                self.scan_progress.setFormat("%v / %m")
            else:
                self.scan_progress.setRange(0,1)
                self.scan_progress.setValue(0)
                self.scan_progress.setFormat("No audio files found")
            self.scan_progress_summary.setText(
                f"Complete · {completed:,} track{'s' if completed != 1 else ''}"
            )
            self.scan_progress_detail.setText("Your music index is ready.")

    def set_scan_paused(self, paused: bool) -> None:
        self._scan_paused=bool(paused)
        self.scan_pause_button.setText("Resume" if paused else "Pause")
        if paused:
            self.scan_progress_title.setText("Indexing paused")
        else:
            self.scan_progress_title.setText("Indexing your music")

    def set_scan_cancelling(self) -> None:
        self.scan_progress_title.setText("Stopping indexing…")
        self.scan_progress_summary.setText("Cancelling")
        self.scan_pause_button.setEnabled(False)
        self.scan_cancel_button.setEnabled(False)

    def finish_scan(
        self,
        status: str,
        *,
        count: int = 0,
        error: str = "",
        changes: dict[str, Any] | None = None,
    ) -> None:
        status=str(status or "complete")
        self._scan_active=False
        self._scan_paused=False
        self.scan_pause_button.setEnabled(False)
        self.scan_cancel_button.setEnabled(False)
        if status=="cancelled":
            self.scan_progress_title.setText("Indexing cancelled")
            self.scan_progress_summary.setText("Existing library kept")
            self.scan_progress_detail.setText(
                "No partial scan was applied."
            )
        elif status=="error":
            self.scan_progress_title.setText("Indexing stopped")
            self.scan_progress_summary.setText("Could not finish")
            self.scan_progress_detail.setText(str(error or "Unknown scan error"))
        else:
            self.scan_progress_title.setText("Indexing complete")
            self.scan_progress_summary.setText(
                f"{max(0,int(count)):,} track{'s' if int(count) != 1 else ''}"
            )
            change_data=dict(changes or {})
            parts=[]
            for key,label in (
                ("unchanged","unchanged"),
                ("added","new"),
                ("changed","updated"),
                ("removed","removed"),
            ):
                value=max(0,int(change_data.get(key) or 0))
                if value:
                    parts.append(f"{value:,} {label}")
            incomplete=max(0,int(change_data.get("incomplete_roots") or 0))
            if incomplete:
                parts.append(
                    f"{incomplete} root{'s' if incomplete != 1 else ''} incomplete · cached copy kept"
                )
            self.scan_progress_detail.setText(
                " · ".join(parts) if parts else "Your music index is ready."
            )

    def clear_scan_status(self) -> None:
        if not self._scan_active:
            self.scan_progress_panel.hide()

    def current_view(self) -> str:
        for key, button in self.view_buttons.items():
            if button.isChecked():
                return key
        return "albums"

    def set_view(self, name: str) -> None:
        started = time.perf_counter()
        if not self.catalog:
            self.stack.setCurrentWidget(self.empty)
            self.last_view_metrics = {
                "view": str(name or "albums"),
                "total_seconds": round(time.perf_counter() - started, 6),
                "empty": True,
            }
            return
        name = str(name or "albums")
        if name not in self.view_buttons:
            name = "albums"
        self.view_buttons[name].setChecked(True)
        target = {
            "albums": self.album_page,
            "artists": self.artist_page,
            "tracks": self.track_list,
        }[name]
        self.stack.setCurrentWidget(target)
        shell_seconds = time.perf_counter() - started
        if name == "artists":
            self.images_button.setObjectName("primaryButton")
        else:
            self.images_button.setObjectName("quietButton")
        self._refresh_images_button_label()
        self.images_button.style().unpolish(self.images_button)
        self.images_button.style().polish(self.images_button)
        self.images_button.update()
        filter_started = time.perf_counter()
        self._apply_filter()
        self.last_view_metrics = {
            "view": name,
            "shell_seconds": round(shell_seconds, 6),
            "filter_seconds": round(time.perf_counter() - filter_started, 6),
            "total_seconds": round(time.perf_counter() - started, 6),
            "rendered_album_count": len(self.cards),
            "rendered_artist_count": len(self.artist_cards),
            "rendered_track_count": len(self.track_rows),
        }

    @staticmethod
    def _new_lookup_stats(total: int = 0) -> dict[str,int]:
        return {
            "total":max(0,int(total)),
            "completed":0,
            "found":0,
            "skipped":0,
            "failed":0,
        }

    def _active_artwork_kind(self) -> str:
        if self._artist_lookup_active:
            return "artists"
        if self._album_lookup_active:
            return "albums"
        return ""

    def artwork_lookup_snapshot(self) -> dict[str,Any]:
        kind=self._active_artwork_kind()
        if not kind:
            kind=self._last_artwork_kind
        if not kind:
            if self._artist_lookup_stats.get("total"):
                kind="artists"
            elif self._album_lookup_stats.get("total"):
                kind="albums"
        stats=dict(
            self._artist_lookup_stats
            if kind=="artists"
            else self._album_lookup_stats
        )
        if kind=="artists":
            stats.update({
                "kind":"artists",
                "remaining":self.artist_image_lookup_remaining(),
                "paused":self._artist_lookup_paused,
                "active":self._artist_lookup_active,
            })
        elif kind=="albums":
            stats.update({
                "kind":"albums",
                "remaining":self.album_artwork_lookup_remaining(),
                "paused":self._album_lookup_paused,
                "active":self._album_lookup_active,
            })
        else:
            stats.update({"kind":"","remaining":0,"paused":False,"active":False})
        return stats

    def _refresh_artwork_progress(self, *, kind: str = "") -> None:
        kind=kind or self._active_artwork_kind() or self._last_artwork_kind
        if not kind:
            if self._artist_lookup_stats.get("total"):
                kind="artists"
            elif self._album_lookup_stats.get("total"):
                kind="albums"
        if not kind:
            self.artwork_progress_panel.hide()
            return

        stats=(
            self._artist_lookup_stats
            if kind=="artists"
            else self._album_lookup_stats
        )
        total=max(0,int(stats.get("total") or 0))
        completed=max(0,min(total,int(stats.get("completed") or 0)))
        active=(
            self._artist_lookup_active
            if kind=="artists"
            else self._album_lookup_active
        )
        paused=(
            self._artist_lookup_paused
            if kind=="artists"
            else self._album_lookup_paused
        )
        canceling=(
            self._artist_lookup_cancel_requested
            if kind=="artists"
            else self._album_lookup_cancel_requested
        )
        failures=(
            self._artist_lookup_failures
            if kind=="artists"
            else self._album_lookup_failures
        )

        self.artwork_progress_panel.show()
        self.artwork_progress_title.setText(
            "Artist photo recovery" if kind=="artists" else "Album artwork recovery"
        )
        self.artwork_progress.setRange(0,max(1,total))
        self.artwork_progress.setValue(completed)
        self.artwork_progress.setFormat(f"{completed} / {total}")

        found=int(stats.get("found") or 0)
        skipped=int(stats.get("skipped") or 0)
        failed=int(stats.get("failed") or 0)
        self.artwork_progress_summary.setText(
            f"Found {found} · No match {skipped} · Failed {failed}"
        )

        if canceling and active:
            state="Canceling after current requests…"
        elif canceling and not active:
            state="Canceled"
        elif paused and active:
            state="Paused"
        elif active:
            state="Searching in the background"
        elif total and completed >= total:
            state="Complete"
        elif total:
            state="Stopped"
        else:
            state=""
        self.artwork_progress_detail.setText(state)

        self.artwork_pause_button.setText("Resume" if paused else "Pause")
        self.artwork_pause_button.setEnabled(bool(active and not canceling))
        self.artwork_cancel_button.setEnabled(bool(active and not canceling))
        self.artwork_retry_button.setVisible(bool(failures) and not active)
        self.artwork_retry_button.setText(
            f"Retry failed ({len(failures)})"
            if failures
            else "Retry failed"
        )

    def _toggle_artwork_lookup_pause(self) -> None:
        kind=self._active_artwork_kind()
        if kind=="artists":
            self._artist_lookup_paused=not self._artist_lookup_paused
            if not self._artist_lookup_paused and not self._artist_lookup_inflight:
                self._emit_next_artist_lookup_batch()
        elif kind=="albums":
            self._album_lookup_paused=not self._album_lookup_paused
            if not self._album_lookup_paused and not self._album_lookup_inflight:
                self._emit_next_album_lookup_batch()
        self._refresh_images_button_label()
        self._refresh_artwork_progress(kind=kind)

    def _cancel_artwork_lookup(self) -> None:
        kind=self._active_artwork_kind()
        if kind=="artists":
            self._artist_lookup_cancel_requested=True
            self._artist_lookup_queue.clear()
            if not self._artist_lookup_inflight:
                self._artist_lookup_active=False
        elif kind=="albums":
            self._album_lookup_cancel_requested=True
            self._album_lookup_queue.clear()
            if not self._album_lookup_inflight:
                self._album_lookup_active=False
        self._refresh_images_button_label()
        self._refresh_artwork_progress(kind=kind)

    def _retry_failed_artwork(self) -> None:
        if self._artist_lookup_active or self._album_lookup_active:
            return
        view=self._last_artwork_kind or self.current_view()
        if view=="artists" and self._artist_lookup_failures:
            self._artist_lookup_queue=[dict(row) for row in self._artist_lookup_failures]
            self._artist_lookup_failures=[]
            self._artist_lookup_stats=self._new_lookup_stats(len(self._artist_lookup_queue))
            self._artist_lookup_active=bool(self._artist_lookup_queue)
            self._last_artwork_kind="artists"
            self._artist_lookup_paused=False
            self._artist_lookup_cancel_requested=False
            self._emit_next_artist_lookup_batch()
        elif view=="albums" and self._album_lookup_failures:
            self._album_lookup_queue=[dict(row) for row in self._album_lookup_failures]
            self._album_lookup_failures=[]
            self._album_lookup_stats=self._new_lookup_stats(len(self._album_lookup_queue))
            self._album_lookup_active=bool(self._album_lookup_queue)
            self._last_artwork_kind="albums"
            self._album_lookup_paused=False
            self._album_lookup_cancel_requested=False
            self._emit_next_album_lookup_batch()
        self._refresh_artwork_progress(kind=view)

    def _finish_lookup_batch(
        self,
        kind: str,
        outcomes: list[dict[str,Any]],
    ) -> bool:
        is_artist=kind=="artists"
        inflight_rows=(
            self._artist_lookup_inflight_rows
            if is_artist
            else self._album_lookup_inflight_rows
        )
        stats=(
            self._artist_lookup_stats
            if is_artist
            else self._album_lookup_stats
        )
        failures=(
            self._artist_lookup_failures
            if is_artist
            else self._album_lookup_failures
        )
        by_key={
            str(row.get("key") or ""):dict(row)
            for row in list(outcomes or [])
            if isinstance(row,dict)
        }
        for original in list(inflight_rows):
            key=str(original.get("key") or "")
            outcome=by_key.get(key,{})
            status=str(outcome.get("status") or "error")
            stats["completed"]+=1
            if status=="found":
                stats["found"]+=1
            elif status=="no_match":
                stats["skipped"]+=1
            else:
                stats["failed"]+=1
                failures.append(dict(original))

        if is_artist:
            self._artist_lookup_inflight=0
            self._artist_lookup_inflight_rows=[]
            self._artist_lookup_current=""
            if self._artist_lookup_cancel_requested:
                self._artist_lookup_active=False
            elif not self._artist_lookup_queue:
                self._artist_lookup_active=False
            elif not self._artist_lookup_paused:
                self._emit_next_artist_lookup_batch()
        else:
            self._album_lookup_inflight=0
            self._album_lookup_inflight_rows=[]
            self._album_lookup_current=""
            if self._album_lookup_cancel_requested:
                self._album_lookup_active=False
            elif not self._album_lookup_queue:
                self._album_lookup_active=False
            elif not self._album_lookup_paused:
                self._emit_next_album_lookup_batch()

        self._refresh_images_button_label()
        self._refresh_artwork_progress(kind=kind)
        return bool(
            self._artist_lookup_active if is_artist else self._album_lookup_active
        )

    def finish_artist_image_lookup_batch(
        self,
        outcomes: list[dict[str,Any]],
    ) -> bool:
        return self._finish_lookup_batch("artists",outcomes)

    def finish_album_artwork_lookup_batch(
        self,
        outcomes: list[dict[str,Any]],
    ) -> bool:
        return self._finish_lookup_batch("albums",outcomes)

    @staticmethod
    def _progress_item_label(value: str, limit: int = 22) -> str:
        value=" ".join(str(value or "").split())
        if len(value) <= limit:
            return value
        return value[: max(1, limit - 1)].rstrip() + "…"

    def _refresh_images_button_label(self) -> None:
        view=self.current_view()
        if view == "artists":
            if self._album_lookup_active:
                self.images_button.setText(
                    f"Artwork search running… {self.album_artwork_lookup_remaining()} left"
                )
                self.images_button.setEnabled(False)
            elif self._artist_lookup_active:
                remaining=self.artist_image_lookup_remaining()
                current=self._progress_item_label(self._artist_lookup_current)
                self.images_button.setText(
                    f"Finding {current}… {remaining} left"
                    if current and remaining
                    else f"Finding photos… {remaining} left"
                    if remaining
                    else "Finding photos…"
                )
                self.images_button.setEnabled(False)
            else:
                self.images_button.setText("Get artist photos")
                self.images_button.setEnabled(True)
            return

        if view == "albums":
            if self._artist_lookup_active:
                self.images_button.setText(
                    f"Artist search running… {self.artist_image_lookup_remaining()} left"
                )
                self.images_button.setEnabled(False)
            elif self._album_lookup_active:
                remaining=self.album_artwork_lookup_remaining()
                current=self._progress_item_label(self._album_lookup_current)
                self.images_button.setText(
                    f"Finding {current}… {remaining} left"
                    if current and remaining
                    else f"Finding artwork… {remaining} left"
                    if remaining
                    else "Finding artwork…"
                )
                self.images_button.setEnabled(False)
            else:
                self.images_button.setText("Find missing artwork")
                self.images_button.setEnabled(True)
            return

        self.images_button.setText("Find missing artwork")
        self.images_button.setEnabled(False)

    def _search_changed(self, _text: str = "") -> None:
        """Reset progressive windows so a new search starts small and fast."""
        self._album_render_limit = self._album_batch_size
        self._artist_render_limit = self._artist_batch_size
        self._track_render_limit = self._track_batch_size
        self._tracks_built = False
        self._apply_filter()

    def _apply_filter(self) -> None:
        if not self.catalog:
            self.last_filter_metrics = {}
            return

        started = time.perf_counter()
        query = _norm(self.search.text())

        album_started = time.perf_counter()
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
        album_filter_seconds = time.perf_counter() - album_started

        artist_started = time.perf_counter()
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
        artist_filter_seconds = time.perf_counter() - artist_started

        track_started = time.perf_counter()
        self._visible_tracks = sorted(
            [
                track
                for track in self.catalog
                if not query
                or query
                in _norm(
                    f"{track.get('artist','')} {track.get('title','')} "
                    f"{track.get('album','')} {track.get('genre','')}"
                )
            ],
            key=lambda item: (
                _norm(item.get("artist")),
                _norm(item.get("album")),
                int(item.get("disc_number") or 0),
                int(item.get("track_number") or 0),
                _norm(item.get("title")),
            ),
        )
        track_filter_sort_seconds = time.perf_counter() - track_started

        layout_started = time.perf_counter()
        self._layout_album_cards()
        if self.current_view() == "artists" or self.artist_cards:
            self._layout_artist_cards()
        if self.current_view() == "tracks":
            self._rebuild_tracks()
            self._tracks_built = True
        layout_seconds = time.perf_counter() - layout_started

        self.last_filter_metrics = {
            "query_length": len(query),
            "view": self.current_view(),
            "visible_album_count": len(self._visible_albums),
            "visible_artist_count": len(self._visible_artists),
            "visible_track_count": len(self._visible_tracks),
            "album_filter_seconds": round(album_filter_seconds, 6),
            "artist_filter_seconds": round(artist_filter_seconds, 6),
            "track_filter_sort_seconds": round(track_filter_sort_seconds, 6),
            "layout_seconds": round(layout_seconds, 6),
            "total_seconds": round(time.perf_counter() - started, 6),
        }

    def _layout_album_cards(self) -> None:
        self._clear_grid(self.album_grid)
        width = max(400, self.album_scroll.viewport().width())
        columns = max(2, min(8, width // 190))
        rendered = self._visible_albums[: self._album_render_limit]
        rendered_keys = {str(album.get("key") or "") for album in rendered}
        for key in list(self.cards):
            if key in rendered_keys:
                continue
            card = self.cards.pop(key)
            card.setParent(None)
            card.deleteLater()
        for index, album in enumerate(rendered):
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
        if self.last_catalog_metrics:
            self.last_catalog_metrics["rendered_album_count"] = len(self.cards)

        remaining = max(0, len(self._visible_albums) - len(rendered))
        self.album_more_button.setVisible(bool(remaining))
        if remaining:
            step = min(self._album_batch_size, remaining)
            self.album_more_button.setText(
                f"Showing {len(rendered):,} of {len(self._visible_albums):,} albums · "
                f"Show {step:,} more"
            )

    def _layout_artist_cards(self) -> None:
        self._clear_grid(self.artist_grid)
        width = max(400, self.artist_scroll.viewport().width())
        columns = max(2, min(8, width // 190))
        rendered = self._visible_artists[: self._artist_render_limit]
        rendered_keys = {str(artist.get("key") or "") for artist in rendered}
        for key in list(self.artist_cards):
            if key in rendered_keys:
                continue
            card = self.artist_cards.pop(key)
            card.setParent(None)
            card.deleteLater()
        for index, artist in enumerate(rendered):
            key = str(artist.get("key") or "")
            card = self.artist_cards.get(key)
            if card is None:
                card = ArtistCard(artist)
                card.openRequested.connect(self._artist_opened)
                card.playRequested.connect(self.playArtistRequested)
                card.photoRequested.connect(self.artistPhotoFileRequested)
                self.artist_cards[key] = card
                artist_path=self.artist_image_paths.get(key,"")
                if artist_path:
                    card.set_image(artist_path,artist_photo=True)
            row, column = divmod(index, columns)
            self.artist_grid.addWidget(card, row, column, Qt.AlignTop)
        self.artist_container.adjustSize()
        if self.last_catalog_metrics:
            self.last_catalog_metrics["rendered_artist_count"] = len(self.artist_cards)

        remaining = max(0, len(self._visible_artists) - len(rendered))
        self.artist_more_button.setVisible(bool(remaining))
        if remaining:
            step = min(self._artist_batch_size, remaining)
            self.artist_more_button.setText(
                f"Showing {len(rendered):,} of {len(self._visible_artists):,} artists · "
                f"Show {step:,} more"
            )

    def _show_more_albums(self) -> None:
        self._album_render_limit += self._album_batch_size
        self._layout_album_cards()
        self._request_artwork()

    def _show_more_artists(self) -> None:
        self._artist_render_limit += self._artist_batch_size
        self._layout_artist_cards()
        self._request_cached_artist_images()

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

    def _append_track_rows(self, tracks: list[dict[str, Any]]) -> None:
        for track in tracks:
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

    def _remove_track_more_footer(self) -> None:
        item = self._track_more_item
        if item is None:
            return
        row_index = self.track_list.row(item)
        if row_index >= 0:
            widget = self.track_list.itemWidget(item)
            if widget is not None:
                self.track_list.removeItemWidget(item)
                widget.deleteLater()
            self.track_list.takeItem(row_index)
        self._track_more_item = None

    def _update_track_more_footer(self) -> None:
        self._remove_track_more_footer()
        total = len(self._visible_tracks)
        shown = min(self._track_render_limit, total)
        remaining = max(0, total - shown)
        if not remaining:
            return

        item = QListWidgetItem()
        item.setData(Qt.UserRole, {"__melodex_load_more__": True})
        item.setSizeHint(QSize(100, 58))

        footer = QFrame()
        row = QHBoxLayout(footer)
        row.setContentsMargins(10, 8, 10, 8)
        summary = QLabel(f"Showing {shown:,} of {total:,} tracks")
        summary.setObjectName("trackMeta")
        row.addWidget(summary)
        row.addStretch(1)
        step = min(self._track_batch_size, remaining)
        button = QPushButton(f"Show {step:,} more")
        button.setObjectName("quietButton")
        button.clicked.connect(self._show_more_tracks)
        row.addWidget(button)

        self.track_list.addItem(item)
        self.track_list.setItemWidget(item, footer)
        self._track_more_item = item

    def _rebuild_tracks(self) -> None:
        self.track_list.clear()
        self._track_more_item = None
        self.track_rows.clear()
        self.track_items.clear()
        shown = self._visible_tracks[: self._track_render_limit]
        self._append_track_rows(shown)
        self._update_track_more_footer()
        self._tracks_built = True
        if self.last_catalog_metrics:
            self.last_catalog_metrics["rendered_track_count"] = len(self.track_rows)

    def _show_more_tracks(self) -> None:
        total = len(self._visible_tracks)
        previous = min(self._track_render_limit, total)
        if previous >= total:
            return
        self._track_render_limit += self._track_batch_size
        current = min(self._track_render_limit, total)
        self._remove_track_more_footer()
        self._append_track_rows(self._visible_tracks[previous:current])
        self._update_track_more_footer()
        if self.last_catalog_metrics:
            self.last_catalog_metrics["rendered_track_count"] = len(self.track_rows)

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
        if isinstance(track, dict) and track.get("__melodex_load_more__"):
            self._show_more_tracks()
            return
        if isinstance(track, dict):
            self.playTrackRequested.emit(dict(track))

    def _request_artwork(self) -> None:
        batch = []
        for album in self._visible_albums[: self._album_render_limit]:
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
        for artist in self._visible_artists[: self._artist_render_limit]:
            key=str(artist.get("key") or "")
            track=dict(artist.get("representative_track") or {})
            name=str(artist.get("name") or "")
            if key and track and name and _norm(name)!="unknown artist":
                batch.append({"key":key,"artist":name,"track":track})
        if batch:
            self.artistImageCacheRequested.emit(batch)

    def _request_online_artwork(self) -> None:
        # Keep one artwork job active at a time. Each job uses a small bounded
        # batch; MusicBrainz itself remains rate-limited by the metadata service.
        if self._artist_lookup_active or self._album_lookup_active:
            self._refresh_images_button_label()
            return

        if self.current_view() == "artists":
            artists = self._visible_artists if self._visible_artists else self.artist_rows
            self._artist_lookup_queue = []
            self._artist_lookup_inflight = 0
            self._artist_lookup_inflight_rows = []
            self._artist_lookup_failures = []
            self._artist_lookup_paused = False
            self._artist_lookup_cancel_requested = False
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
            self._last_artwork_kind = "artists"
            self._artist_lookup_stats = self._new_lookup_stats(len(self._artist_lookup_queue))
            self._refresh_images_button_label()
            self._refresh_artwork_progress(kind="artists")
            self._emit_next_artist_lookup_batch()
            return

        if self.current_view() == "albums":
            albums = self._visible_albums if self._visible_albums else self.albums
            self._album_lookup_queue = []
            self._album_lookup_inflight = 0
            self._album_lookup_inflight_rows = []
            self._album_lookup_failures = []
            self._album_lookup_paused = False
            self._album_lookup_cancel_requested = False
            for album in albums:
                key = str(album.get("key") or "")
                card = self.cards.get(key)
                if not key or card is None or card.has_real_cover:
                    continue
                track = dict(album.get("representative_track") or {})
                if track:
                    self._album_lookup_queue.append({
                        "key": key,
                        "track": track,
                        "tracks": [
                            dict(x)
                            for x in list(album.get("tracks") or [])
                            if isinstance(x,dict)
                        ],
                    })
            self._album_lookup_active = bool(self._album_lookup_queue)
            self._last_artwork_kind = "albums"
            self._album_lookup_stats = self._new_lookup_stats(len(self._album_lookup_queue))
            self._refresh_images_button_label()
            self._refresh_artwork_progress(kind="albums")
            self._emit_next_album_lookup_batch()

    def _emit_next_artist_lookup_batch(self) -> bool:
        if not self._artist_lookup_active or not self._artist_lookup_queue:
            self._artist_lookup_active = False
            self._artist_lookup_inflight = 0
            self._artist_lookup_current = ""
            self._refresh_images_button_label()
            return False
        if self._artist_lookup_paused or self._artist_lookup_cancel_requested:
            self._refresh_artwork_progress(kind="artists")
            return False
        batch=self._artist_lookup_queue[:self._artwork_batch_size]
        self._artist_lookup_queue=self._artist_lookup_queue[len(batch):]
        self._artist_lookup_inflight=len(batch)
        self._artist_lookup_inflight_rows=[dict(row) for row in batch]
        self._artist_lookup_current=str(batch[0].get("artist") or "artist") if batch else ""
        for row in batch:
            key=str(row.get("key") or "")
            if key:
                self._artist_art_requested.add(key)
        self._refresh_images_button_label()
        self._refresh_artwork_progress(kind="artists")
        self.artistImageRequested.emit(batch)
        return True

    def continue_artist_image_lookup(self) -> bool:
        """Compatibility helper: mark the in-flight batch as no-match and continue."""
        outcomes=[
            {"key":str(row.get("key") or ""),"status":"no_match"}
            for row in self._artist_lookup_inflight_rows
        ]
        return self.finish_artist_image_lookup_batch(outcomes)

    def artist_image_lookup_remaining(self) -> int:
        return len(self._artist_lookup_queue) + int(self._artist_lookup_inflight or 0)

    def _emit_next_album_lookup_batch(self) -> bool:
        if not self._album_lookup_active or not self._album_lookup_queue:
            self._album_lookup_active = False
            self._album_lookup_inflight = 0
            self._album_lookup_current = ""
            self._refresh_images_button_label()
            return False
        if self._album_lookup_paused or self._album_lookup_cancel_requested:
            self._refresh_artwork_progress(kind="albums")
            return False
        batch=self._album_lookup_queue[:self._artwork_batch_size]
        self._album_lookup_queue=self._album_lookup_queue[len(batch):]
        self._album_lookup_inflight=len(batch)
        self._album_lookup_inflight_rows=[dict(row) for row in batch]
        if batch:
            track=dict(batch[0].get("track") or {})
            self._album_lookup_current=str(
                track.get("album") or track.get("title") or "artwork"
            ).strip()
        self._refresh_images_button_label()
        self._refresh_artwork_progress(kind="albums")
        self.onlineArtworkRequested.emit(batch)
        return True

    def continue_album_artwork_lookup(self) -> bool:
        """Compatibility helper: mark the in-flight batch as no-match and continue."""
        outcomes=[
            {"key":str(row.get("key") or ""),"status":"no_match"}
            for row in self._album_lookup_inflight_rows
        ]
        return self.finish_album_artwork_lookup_batch(outcomes)

    def album_artwork_lookup_remaining(self) -> int:
        return len(self._album_lookup_queue) + int(self._album_lookup_inflight or 0)

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

            for track_key, row in list(self.track_rows.items()):
                if str(self.track_album_key.get(track_key) or "") == key:
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
