from __future__ import annotations

"""
Melodex experience redesign.

This module deliberately changes presentation and interaction only. It
monkey-patches the existing v0.2 desktop widgets at application startup, so
provider, playback, resolver, Flow, taste, privacy and bridge logic remain
untouched.

Design principles:
- music first, controls second, machinery third
- recognition over recall
- progressive disclosure for provider/developer controls
- useful empty states rather than blank panes
- one dominant action per screen
- no streaks, fake urgency or other dark-pattern engagement mechanics
"""

from pathlib import Path
from typing import Any
import shutil

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPixmap, QImage
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QStackedWidget,
    QLineEdit,
    QComboBox,
    QSlider,
    QTextEdit,
    QCheckBox,
    QMenu,
    QMessageBox,
    QTabWidget,
    QTextBrowser,
)

from .main_window import MainWindow
from .rich_now_playing import RichNowPlayingWidget


def friendly_source(track: dict[str, Any]) -> str:
    known = {
        "local": "This computer",
        "jamendo": "Jamendo",
        "streams": "User Streams",
        "ccmixter": "ccMixter",
        "radio-browser": "Radio Browser",
        "radio_browser": "Radio Browser",
        "internet-archive": "Internet Archive",
        "internet_archive": "Internet Archive",
        "wikimedia": "Wikimedia Commons",
        "librivox": "LibriVox",
        "somafm": "SomaFM",
        "openverse": "Openverse",
    }

    explicit = str(
        track.get("provider_name")
        or track.get("source_name")
        or track.get("source")
        or ""
    ).strip()
    if explicit:
        low = explicit.casefold()
        for needle, label in known.items():
            if low == needle or needle in low:
                return label
        if not explicit.startswith("org.melodex"):
            return explicit

    pid = str(track.get("provider_id") or "").strip()
    low = pid.casefold()
    for needle, label in known.items():
        if needle in low:
            return label

    if not pid:
        return ""
    tail = pid.rsplit(".", 1)[-1].replace("-", " ").replace("_", " ").strip()
    return tail.title() if tail else pid


def source_examples(provider_id: str, name: str = "") -> str:
    hay = f"{provider_id} {name}".casefold()
    examples = [
        ("ccmixter", "ambient · remix · electronic · acoustic"),
        ("radio browser", "BBC · jazz · Berlin · SomaFM"),
        ("radio-browser", "BBC · jazz · Berlin · SomaFM"),
        ("internet archive", "Grateful Dead · live concert · old time radio"),
        ("internet-archive", "Grateful Dead · live concert · old time radio"),
        ("wikimedia", "classical · field recording · speech"),
        ("librivox", "Sherlock Holmes · poetry · Shakespeare"),
        ("somafm", "Groove Salad · Drone Zone · Space Station Soma"),
        ("openverse", "ambient · birds · drums · Creative Commons"),
        ("jamendo", "ambient · indie · electronic"),
    ]
    for needle, text in examples:
        if needle in hay:
            return text
    return ""


class EmptyStateListWidget(QListWidget):
    """Normal QListWidget with an instructional empty state."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._empty_title = "Nothing here yet"
        self._empty_body = ""
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setUniformItemSizes(False)

    def set_empty_state(self, title: str, body: str = "") -> None:
        self._empty_title = str(title or "")
        self._empty_body = str(body or "")
        self.viewport().update()

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        if self.count():
            return

        painter = QPainter(self.viewport())
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.viewport().rect().adjusted(48, 48, -48, -48)

        title_font = QFont(self.font())
        title_font.setPointSizeF(max(15.0, title_font.pointSizeF() + 3.0))
        title_font.setWeight(QFont.DemiBold)
        painter.setFont(title_font)
        painter.setPen(QColor("#D9DEE8"))
        title_rect = rect.adjusted(0, max(20, rect.height() // 2 - 72), 0, 0)
        painter.drawText(
            title_rect,
            Qt.AlignHCenter | Qt.AlignTop | Qt.TextWordWrap,
            self._empty_title,
        )

        if self._empty_body:
            body_font = QFont(self.font())
            body_font.setPointSizeF(max(11.0, body_font.pointSizeF()))
            painter.setFont(body_font)
            painter.setPen(QColor("#8994A5"))
            body_rect = title_rect.adjusted(0, 42, 0, 0)
            painter.drawText(
                body_rect,
                Qt.AlignHCenter | Qt.AlignTop | Qt.TextWordWrap,
                self._empty_body,
            )


def app_stylesheet() -> str:
    return r"""
    QMainWindow, QDialog {
        background-color: #0A0D12;
        color: #F6F7FB;
    }

    QWidget {
        background-color: transparent;
        color: #F6F7FB;
        font-family: "Inter", "SF Pro Display", "Segoe UI", Arial, sans-serif;
        font-size: 13px;
    }

    QLabel, QCheckBox {
        background-color: rgba(0, 0, 0, 0);
        border: none;
    }

    QStackedWidget#contentStack {
        background-color: #0A0D12;
    }

    QWidget#sidebar {
        background: #080B10;
        border-right: 1px solid #1C2330;
    }

    QLabel#brandTagline {
        color: #7F8A9A;
        font-size: 10px;
    }

    QLabel#navSection {
        color: #657185;
        font-size: 10px;
        font-weight: 700;
        letter-spacing: 1px;
        padding: 13px 10px 5px 10px;
    }

    QPushButton#navButton {
        background: transparent;
        color: #CFD5DF;
        border: 0;
        border-radius: 9px;
        padding: 9px 11px;
        text-align: left;
    }

    QPushButton#navButton:hover {
        background: #111722;
        color: #FFFFFF;
    }

    QPushButton#navButton[active="true"] {
        background: #172236;
        color: #FFFFFF;
        border-left: 3px solid #4A8CFF;
        padding-left: 9px;
        font-weight: 650;
    }

    QLabel#pageTitle {
        font-size: 30px;
        font-weight: 760;
        color: #F7F8FB;
    }

    QLabel#pageSubtitle, QLabel#secondaryText {
        color: #9AA4B3;
    }

    QLabel#sectionTitle {
        color: #F0F3F8;
        font-size: 16px;
        font-weight: 700;
    }

    QLabel#heroTitle {
        color: #FFFFFF;
        font-size: 25px;
        font-weight: 760;
    }

    QWidget#heroCard {
        background: qlineargradient(
            x1:0, y1:0, x2:1, y2:1,
            stop:0 #13223B,
            stop:0.55 #151A2C,
            stop:1 #261831
        );
        border: 1px solid #29354A;
        border-radius: 18px;
    }

    QWidget#softCard {
        background: #111720;
        border: 1px solid #242D3B;
        border-radius: 14px;
    }

    QWidget#queuePanel {
        background: #0D1118;
        border-left: 1px solid #202938;
    }

    QWidget#playerBar {
        background: #0C1016;
        border-top: 1px solid #202938;
    }

    QLabel#playerArt {
        background: qlineargradient(
            x1:0, y1:0, x2:1, y2:1,
            stop:0 #12233D,
            stop:0.5 #161B2C,
            stop:1 #2D1733
        );
        border: 1px solid #2B3546;
        border-radius: 10px;
        color: #7E8AA0;
        font-size: 22px;
    }

    QLabel#playerTitle {
        color: #F7F8FB;
        font-size: 15px;
        font-weight: 700;
    }

    QPushButton {
        background: #151B25;
        color: #EDF1F7;
        border: 1px solid #2A3443;
        border-radius: 9px;
        padding: 9px 12px;
        text-align: left;
    }

    QPushButton:hover {
        background: #1D2633;
        border-color: #3A4A61;
    }

    QPushButton:pressed {
        background: #111721;
    }

    QPushButton#primaryButton {
        background: qlineargradient(
            x1:0, y1:0, x2:1, y2:0,
            stop:0 #176CF1,
            stop:0.55 #4B62F4,
            stop:1 #A23FDF
        );
        color: white;
        border: 0;
        border-radius: 11px;
        padding: 12px 16px;
        font-weight: 750;
        text-align: left;
    }

    QPushButton#primaryButton:hover {
        background: qlineargradient(
            x1:0, y1:0, x2:1, y2:0,
            stop:0 #2B7AF4,
            stop:0.55 #5B70F6,
            stop:1 #B052E8
        );
    }

    QPushButton#choiceButton {
        background: #111720;
        color: #AEB7C6;
        border: 1px solid #252F3E;
        border-radius: 12px;
        padding: 12px 13px;
        text-align: left;
    }

    QPushButton#choiceButton:checked {
        background: #17233A;
        color: #FFFFFF;
        border: 1px solid #4A7ED4;
    }

    QPushButton#transportButton {
        min-width: 38px;
        min-height: 38px;
        max-width: 42px;
        max-height: 42px;
        padding: 0;
        text-align: center;
        border-radius: 21px;
    }

    QPushButton#transportMain {
        min-width: 48px;
        min-height: 48px;
        max-width: 48px;
        max-height: 48px;
        padding: 0;
        text-align: center;
        border: 0;
        border-radius: 24px;
        background: #F4F6FB;
        color: #0B0E13;
        font-weight: 800;
    }

    QLineEdit, QComboBox, QTextEdit, QListWidget, QTextBrowser, QTabWidget::pane {
        background: #10151D;
        color: #F2F4F8;
        border: 1px solid #253040;
        border-radius: 11px;
    }

    QLineEdit, QComboBox {
        min-height: 24px;
        padding: 7px 10px;
    }

    QLineEdit:focus, QComboBox:focus {
        border: 1px solid #477BD0;
    }

    QListWidget {
        padding: 6px;
        outline: none;
    }

    QListWidget::item {
        padding: 12px 12px;
        margin: 2px 0;
        border: 0;
        border-radius: 8px;
    }

    QListWidget::item:hover {
        background: #151D28;
    }

    QListWidget::item:selected {
        background: #1B2B43;
        color: #FFFFFF;
    }

    QListWidget#sourcesList::item {
        padding: 15px 14px;
    }

    QSlider::groove:horizontal {
        height: 4px;
        background: #252D3A;
        border-radius: 2px;
    }

    QSlider::sub-page:horizontal {
        background: #3383F4;
        border-radius: 2px;
    }

    QSlider::handle:horizontal {
        width: 14px;
        margin: -5px 0;
        border-radius: 7px;
        background: #F8FAFD;
    }

    QTabBar::tab {
        background: transparent;
        color: #98A3B3;
        padding: 9px 13px;
        border: 0;
    }

    QTabBar::tab:selected {
        color: #FFFFFF;
        background: #17233A;
        border-radius: 8px;
    }

    QStatusBar {
        background: #0A0D12;
        color: #8390A2;
        border-top: 1px solid #151C27;
    }

    QCheckBox {
        color: #A6AFBD;
        spacing: 8px;
        padding: 8px 10px;
    }

    QMenu {
        background: #111720;
        color: #F2F4F8;
        border: 1px solid #2A3443;
        padding: 5px;
    }

    QMenu::item {
        padding: 8px 22px 8px 10px;
        border-radius: 6px;
    }

    QMenu::item:selected {
        background: #1B2B43;
    }

    QScrollBar:vertical {
        background: transparent;
        width: 10px;
        margin: 3px;
    }

    QScrollBar::handle:vertical {
        background: #344052;
        min-height: 30px;
        border-radius: 5px;
    }

    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
        background: transparent;
        height: 0;
    }

    QScrollBar:horizontal {
        height: 0;
    }
    """


def _add_nav_group(self, layout, label, items):
    section = QLabel(label)
    section.setObjectName("navSection")
    layout.addWidget(section)
    for text, page in items:
        button = QPushButton(text)
        button.setObjectName("navButton")
        button.setCursor(Qt.PointingHandCursor)
        button.setProperty("active", "false")
        button.clicked.connect(lambda _=False, p=page: self.open_page(p))
        layout.addWidget(button)
        self.nav_buttons[page] = button


def _set_active_nav(self, page):
    for name, button in self.nav_buttons.items():
        button.setProperty("active", "true" if name == page else "false")
        button.style().unpolish(button)
        button.style().polish(button)
        button.update()


def _player_more_menu(self, button):
    menu = QMenu(self)
    now_action = menu.addAction("Now playing")
    now_action.triggered.connect(lambda: self.open_page("now_playing"))

    menu.addSeparator()
    love_action = menu.addAction("Love this track")
    love_action.triggered.connect(lambda: self._feedback(True))
    dislike_action = menu.addAction("Not for me")
    dislike_action.triggered.connect(lambda: self._feedback(False))

    if self.power_toggle.isChecked():
        menu.addSeparator()
        match_action = menu.addAction("Inspect source match")
        match_action.triggered.connect(self._inspect_current_match)

    menu.exec(button.mapToGlobal(button.rect().bottomLeft()))


def _set_player_art(self, track):
    candidate = ""
    for key in (
        "artwork_path",
        "art_path",
        "cover_path",
        "image_path",
        "thumbnail_path",
    ):
        value = str(track.get(key) or "").strip()
        if value and Path(value).exists():
            candidate = value
            break

    pixmap = QPixmap(candidate) if candidate else QPixmap()
    if pixmap.isNull():
        mark = Path(__file__).resolve().parent / "assets" / "melodex-mark.png"
        pixmap = QPixmap(str(mark))

    if not pixmap.isNull():
        self.player_art.setText("")
        self.player_art.setPixmap(
            pixmap.scaled(
                self.player_art.size(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
        )
    else:
        self.player_art.setPixmap(QPixmap())
        self.player_art.setText("♫")


def _set_journey_mode(self, mode):
    self.journey_mode = str(mode or "balanced")
    for name, button in self.mode_buttons.items():
        button.setChecked(name == self.journey_mode)


def _build_ui(self):
    root = QWidget()
    self.setCentralWidget(root)
    outer = QVBoxLayout(root)
    outer.setContentsMargins(0, 0, 0, 0)
    outer.setSpacing(0)

    body = QWidget()
    body_l = QHBoxLayout(body)
    body_l.setContentsMargins(0, 0, 0, 0)
    body_l.setSpacing(0)
    outer.addWidget(body, 1)

    self.sidebar = QWidget()
    self.sidebar.setObjectName("sidebar")
    self.sidebar.setFixedWidth(236)
    side = QVBoxLayout(self.sidebar)
    side.setContentsMargins(16, 18, 16, 14)
    side.setSpacing(2)

    brand = QHBoxLayout()
    brand.setSpacing(11)
    mark = QLabel()
    mark_path = Path(__file__).resolve().parent / "assets" / "melodex-mark.png"
    pixmap = QPixmap(str(mark_path))
    if not pixmap.isNull():
        mark.setPixmap(
            pixmap.scaled(48, 48, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        )
    mark.setFixedSize(50, 50)

    titles = QVBoxLayout()
    titles.setSpacing(0)
    logo = QLabel("MELODEX")
    logo.setStyleSheet("font-size:20px;font-weight:780;letter-spacing:2px")
    tagline = QLabel("Don't shuffle. Flow.")
    tagline.setObjectName("brandTagline")
    titles.addWidget(logo)
    titles.addWidget(tagline)
    brand.addWidget(mark)
    brand.addLayout(titles, 1)
    side.addLayout(brand)
    side.addSpacing(8)

    self.nav_buttons = {}
    self._add_nav_group(
        side,
        "LISTEN",
        [
            ("Home", "home"),
            ("Now playing", "now_playing"),
            ("Play for me", "for_you"),
            ("Discover", "discover"),
        ],
    )
    self._add_nav_group(
        side,
        "YOUR MUSIC",
        [
            ("My music", "library"),
            ("Playlists", "playlists"),
            ("Moments", "moments"),
        ],
    )
    self._add_nav_group(
        side,
        "TOOLS",
        [
            ("Ask Melodex", "ask"),
            ("Sources", "sources"),
        ],
    )

    side.addStretch(1)
    self.power_toggle = QCheckBox("Advanced tools")
    self.power_toggle.stateChanged.connect(self._power_changed)
    side.addWidget(self.power_toggle)
    body_l.addWidget(self.sidebar)

    self.stack = QStackedWidget()
    self.stack.setObjectName("contentStack")
    body_l.addWidget(self.stack, 1)
    self.pages = {}
    for name in [
        "home",
        "now_playing",
        "for_you",
        "discover",
        "library",
        "playlists",
        "moments",
        "ask",
        "sources",
    ]:
        w = QWidget()
        self.pages[name] = w
        self.stack.addWidget(w)

    self._build_home()
    self._build_now_playing()
    self._build_for_you()
    self._build_discover()
    self._build_library()
    self._build_playlists()
    self._build_moments()
    self._build_ask()
    self._build_sources()

    self.queue_panel = QWidget()
    self.queue_panel.setObjectName("queuePanel")
    self.queue_panel.setFixedWidth(340)
    ql = QVBoxLayout(self.queue_panel)
    ql.setContentsMargins(16, 18, 16, 16)
    ql.setSpacing(10)

    qhead = QHBoxLayout()
    qtitle = QLabel("Up next")
    qtitle.setObjectName("sectionTitle")
    qhead.addWidget(qtitle)
    qhead.addStretch(1)
    flow_btn = QPushButton("Flow")
    flow_btn.setToolTip("Re-sequence the queue for smoother musical transitions")
    flow_btn.clicked.connect(self._flow_queue)
    qhead.addWidget(flow_btn)
    ql.addLayout(qhead)

    self.queue_list = EmptyStateListWidget()
    self.queue_list.set_empty_state(
        "Your queue is empty",
        "Play a track or build a journey and the next songs will appear here.",
    )
    self.queue_list.itemDoubleClicked.connect(self._queue_jump)
    ql.addWidget(self.queue_list, 1)
    self.queue_panel.hide()
    body_l.addWidget(self.queue_panel)

    bar = QWidget()
    bar.setObjectName("playerBar")
    bar.setFixedHeight(104)
    bl = QHBoxLayout(bar)
    bl.setContentsMargins(18, 10, 18, 10)
    bl.setSpacing(12)

    self.player_art = QLabel("♫")
    self.player_art.setObjectName("playerArt")
    self.player_art.setAlignment(Qt.AlignCenter)
    self.player_art.setFixedSize(62, 62)
    bl.addWidget(self.player_art)

    text_col = QVBoxLayout()
    text_col.setSpacing(4)
    self.now_title = QLabel("Nothing playing")
    self.now_title.setObjectName("playerTitle")
    self.now_title.setWordWrap(False)
    self.now_meta = QLabel("Choose something you love, or let Melodex choose for you.")
    self.now_meta.setObjectName("secondaryText")
    self.now_meta.setOpenExternalLinks(True)
    self.now_meta.setWordWrap(False)
    text_col.addWidget(self.now_title)
    text_col.addWidget(self.now_meta)

    self.seek = QSlider(Qt.Horizontal)
    self.seek.setRange(0, 1000)
    self.seek.sliderReleased.connect(self._seek_released)
    text_col.addWidget(self.seek)
    bl.addLayout(text_col, 1)

    prev = QPushButton("◀")
    prev.setObjectName("transportButton")
    prev.setToolTip("Previous")
    prev.clicked.connect(self.player.previous)

    play = QPushButton("▶")
    play.setObjectName("transportMain")
    play.setToolTip("Play / pause")
    play.clicked.connect(self.player.play_pause)

    nxt = QPushButton("▶")
    nxt.setObjectName("transportButton")
    nxt.setToolTip("Next")
    nxt.clicked.connect(self.player.next)

    bl.addWidget(prev)
    bl.addWidget(play)
    bl.addWidget(nxt)
    bl.addSpacing(8)

    keep = QPushButton("Keep")
    keep.setToolTip("Keep this track in your taste memory")
    keep.clicked.connect(self._keep)
    bl.addWidget(keep)

    moment = QPushButton("Moment")
    moment.setToolTip("Bookmark this exact point in the track")
    moment.clicked.connect(self._more_actions)
    bl.addWidget(moment)

    more = QPushButton("•••")
    more.setToolTip("More actions")
    more.clicked.connect(lambda: self._player_more_menu(more))
    bl.addWidget(more)

    queue = QPushButton("Queue")
    queue.clicked.connect(
        lambda: self.queue_panel.setVisible(not self.queue_panel.isVisible())
    )
    bl.addWidget(queue)

    outer.addWidget(bar)

    self.setStyleSheet(app_stylesheet())
    self.statusBar().setSizeGripEnabled(False)
    self._set_active_nav("home")


def _page_layout(self, page: str, title: str, subtitle: str = ""):
    lay = QVBoxLayout(self.pages[page])
    lay.setContentsMargins(36, 28, 36, 26)
    lay.setSpacing(10)

    t = QLabel(title)
    t.setObjectName("pageTitle")
    t.setWordWrap(True)
    lay.addWidget(t)

    if subtitle:
        s = QLabel(subtitle)
        s.setObjectName("pageSubtitle")
        s.setWordWrap(True)
        s.setMaximumWidth(980)
        lay.addWidget(s)

    lay.addSpacing(5)
    return lay


def _build_home(self):
    l = self._page_layout(
        "home",
        "Your music, without the work.",
        "One click when you want ease. Fine control when you want it.",
    )

    hero = QWidget()
    hero.setObjectName("heroCard")
    hero_l = QHBoxLayout(hero)
    hero_l.setContentsMargins(24, 22, 24, 22)
    hero_l.setSpacing(20)

    copy = QVBoxLayout()
    copy.setSpacing(7)
    hero_title = QLabel("Press play. Melodex will take it from here.")
    hero_title.setObjectName("heroTitle")
    hero_title.setStyleSheet("background-color: rgba(0,0,0,0);")
    hero_title.setWordWrap(True)
    hero_text = QLabel(
        "A continuous journey shaped by your library, your taste and the sources you connect."
    )
    hero_text.setObjectName("secondaryText")
    hero_text.setStyleSheet("background-color: rgba(0,0,0,0); color:#9AA4B3;")
    hero_text.setWordWrap(True)
    copy.addWidget(hero_title)
    copy.addWidget(hero_text)
    copy.addStretch(1)
    hero_l.addLayout(copy, 1)

    hero_button = QPushButton("▶  Play for me")
    hero_button.setObjectName("primaryButton")
    hero_button.setMinimumWidth(220)
    hero_button.setMinimumHeight(58)
    hero_button.clicked.connect(lambda: self._play_for_me("balanced", 60, 0.35))
    hero_l.addWidget(hero_button, 0, Qt.AlignVCenter)
    l.addWidget(hero)

    quick_title = QLabel("Choose a direction")
    quick_title.setObjectName("sectionTitle")
    l.addWidget(quick_title)

    quick = QHBoxLayout()
    quick.setSpacing(10)
    choices = [
        ("Comfort\nMostly familiar", lambda: self._play_for_me("comfort", 60, 0.15)),
        ("Balanced\nA little discovery", lambda: self._play_for_me("balanced", 60, 0.35)),
        ("Explore\nPush further out", lambda: self._play_for_me("explore", 60, 0.82)),
        ("Add music\nMake Melodex yours", self._choose_music_folder),
    ]
    for text, action in choices:
        button = QPushButton(text)
        button.setObjectName("choiceButton")
        button.setMinimumHeight(60)
        button.clicked.connect(action)
        quick.addWidget(button)
    l.addLayout(quick)

    cards = QHBoxLayout()
    cards.setSpacing(10)

    state_card = QWidget()
    state_card.setObjectName("softCard")
    state_l = QVBoxLayout(state_card)
    state_l.setContentsMargins(16, 14, 16, 14)
    state_l.setSpacing(5)
    state_title = QLabel("Your Melodex")
    state_title.setObjectName("sectionTitle")
    state_title.setStyleSheet("background-color: rgba(0,0,0,0);")
    self.home_status = QLabel()
    self.home_status.setObjectName("secondaryText")
    self.home_status.setStyleSheet("background-color: rgba(0,0,0,0); color:#9AA4B3;")
    self.home_status.setWordWrap(True)
    state_l.addWidget(state_title)
    state_l.addWidget(self.home_status)
    state_l.addStretch(1)
    cards.addWidget(state_card, 1)

    resume_card = QWidget()
    resume_card.setObjectName("softCard")
    resume_l = QVBoxLayout(resume_card)
    resume_l.setContentsMargins(16, 14, 16, 14)
    resume_l.setSpacing(5)
    resume_title = QLabel("Right now")
    resume_title.setObjectName("sectionTitle")
    resume_title.setStyleSheet("background-color: rgba(0,0,0,0);")
    self.home_resume = QLabel()
    self.home_resume.setWordWrap(True)
    self.home_resume.setObjectName("secondaryText")
    self.home_resume.setStyleSheet("background-color: rgba(0,0,0,0); color:#9AA4B3;")
    resume_l.addWidget(resume_title)
    resume_l.addWidget(self.home_resume)
    resume_l.addStretch(1)
    cards.addWidget(resume_card, 1)

    moments_card = QWidget()
    moments_card.setObjectName("softCard")
    moments_l = QVBoxLayout(moments_card)
    moments_l.setContentsMargins(16, 14, 16, 14)
    moments_l.setSpacing(5)
    moments_title = QLabel("Recent moments")
    moments_title.setObjectName("sectionTitle")
    moments_title.setStyleSheet("background-color: rgba(0,0,0,0);")
    self.home_moments = QLabel()
    self.home_moments.setWordWrap(True)
    self.home_moments.setObjectName("secondaryText")
    self.home_moments.setStyleSheet("background-color: rgba(0,0,0,0); color:#9AA4B3;")
    moments_l.addWidget(moments_title)
    moments_l.addWidget(self.home_moments)
    moments_l.addStretch(1)
    cards.addWidget(moments_card, 1)

    l.addLayout(cards)
    l.addStretch(1)


def _build_now_playing(self):
    l = self._page_layout(
        "now_playing",
        "Now playing",
        "The track stays central. Artwork, lyrics and credits arrive quietly in the background.",
    )
    self.rich_now = RichNowPlayingWidget(self.metadata, self)
    l.addWidget(self.rich_now, 1)


def _build_for_you(self):
    l = self._page_layout(
        "for_you",
        "Play for me",
        "Tell Melodex how far to wander, then let Flow build the journey.",
    )

    mode_title = QLabel("What kind of journey?")
    mode_title.setObjectName("sectionTitle")
    l.addWidget(mode_title)

    self.journey_mode = "balanced"
    self.mode_buttons = {}
    mode_row = QHBoxLayout()
    mode_row.setSpacing(10)

    modes = [
        ("Comfort\nStay close to home", "comfort"),
        ("Balanced\nFamiliar + discovery", "balanced"),
        ("Rediscover\nBring back forgotten tracks", "rediscover"),
        ("Explore\nTake a bigger leap", "explore"),
    ]
    for text, mode in modes:
        button = QPushButton(text)
        button.setObjectName("choiceButton")
        button.setCheckable(True)
        button.setMinimumHeight(64)
        button.clicked.connect(lambda _=False, m=mode: self._set_journey_mode(m))
        self.mode_buttons[mode] = button
        mode_row.addWidget(button)
    l.addLayout(mode_row)
    self._set_journey_mode("balanced")

    controls = QWidget()
    controls.setObjectName("softCard")
    controls_l = QVBoxLayout(controls)
    controls_l.setContentsMargins(18, 15, 18, 15)
    controls_l.setSpacing(9)

    top = QHBoxLayout()
    top.addWidget(QLabel("Length"))
    self.minutes = QComboBox()
    self.minutes.addItems(["30", "60", "90", "120"])
    self.minutes.setCurrentText("60")
    top.addWidget(self.minutes)
    top.addWidget(QLabel("minutes"))
    top.addStretch(1)
    controls_l.addLayout(top)

    adventure_labels = QHBoxLayout()
    familiar = QLabel("Familiar")
    familiar.setObjectName("secondaryText")
    self.adventure_readout = QLabel("35% discovery")
    self.adventure_readout.setObjectName("secondaryText")
    surprising = QLabel("Surprising")
    surprising.setObjectName("secondaryText")
    adventure_labels.addWidget(familiar)
    adventure_labels.addStretch(1)
    adventure_labels.addWidget(self.adventure_readout)
    adventure_labels.addStretch(1)
    adventure_labels.addWidget(surprising)
    controls_l.addLayout(adventure_labels)

    self.adventure = QSlider(Qt.Horizontal)
    self.adventure.setRange(0, 100)
    self.adventure.setValue(35)
    self.adventure.valueChanged.connect(
        lambda value: self.adventure_readout.setText(f"{int(value)}% discovery")
    )
    controls_l.addWidget(self.adventure)
    l.addWidget(controls)

    go = QPushButton("▶  Build my journey")
    go.setObjectName("primaryButton")
    go.setMinimumHeight(54)
    go.clicked.connect(
        lambda: self._play_for_me(
            self.journey_mode,
            int(self.minutes.currentText()),
            self.adventure.value() / 100,
        )
    )
    l.addWidget(go)

    taste = QWidget()
    taste.setObjectName("softCard")
    taste_l = QVBoxLayout(taste)
    taste_l.setContentsMargins(16, 14, 16, 14)
    taste_title = QLabel("Melodex is learning your taste")
    taste_title.setObjectName("sectionTitle")
    self.taste_label = QLabel()
    self.taste_label.setObjectName("secondaryText")
    self.taste_label.setWordWrap(True)
    taste_l.addWidget(taste_title)
    taste_l.addWidget(self.taste_label)
    l.addWidget(taste)
    l.addStretch(1)


def _build_discover(self):
    l = self._page_layout(
        "discover",
        "Discover",
        "Search across everything you have connected. Source details stay secondary to the music.",
    )

    row = QHBoxLayout()
    row.setSpacing(9)
    self.search_box = QLineEdit()
    self.search_box.setPlaceholderText("Search artist, track, album or station…")
    self.search_box.setMinimumHeight(38)
    self.search_box.returnPressed.connect(self._search)

    self.search_source = QComboBox()
    self.search_source.setMinimumWidth(190)

    search = QPushButton("Search")
    search.setObjectName("primaryButton")
    search.clicked.connect(self._search)

    row.addWidget(self.search_box, 1)
    row.addWidget(self.search_source)
    row.addWidget(search)
    l.addLayout(row)

    self.results = EmptyStateListWidget()
    self.results.set_empty_state(
        "Search your music universe",
        "Try an artist, a mood, a radio station or a track name. Double-click a result to play it.",
    )
    self.results.itemDoubleClicked.connect(self._play_result)
    l.addWidget(self.results, 1)

    row2 = QHBoxLayout()
    addq = QPushButton("Add to queue")
    addq.clicked.connect(self._add_selected_to_queue)
    source_btn = QPushButton("Open source")
    source_btn.clicked.connect(self._open_selected_source)
    row2.addWidget(addq)
    row2.addWidget(source_btn)
    row2.addStretch(1)
    l.addLayout(row2)


def _build_library(self):
    l = self._page_layout(
        "library",
        "My music",
        "Your local collection stays on this device and becomes the strongest signal for Flow.",
    )

    row = QHBoxLayout()
    add = QPushButton("Add music folder…")
    add.setObjectName("primaryButton")
    add.clicked.connect(self._choose_music_folder)
    scan = QPushButton("Rescan")
    scan.clicked.connect(self._rescan)
    row.addWidget(add)
    row.addWidget(scan)
    row.addStretch(1)
    l.addLayout(row)

    self.library_list = EmptyStateListWidget()
    self.library_list.set_empty_state(
        "Make Melodex yours",
        "Add a music folder. Melodex will index it locally and use it for journeys, rediscovery and Flow.",
    )
    self.library_list.itemDoubleClicked.connect(self._play_library)
    l.addWidget(self.library_list, 1)


def _build_playlists(self):
    l = self._page_layout(
        "playlists",
        "Playlists",
        "Saved journeys and imported playlists live locally and stay portable.",
    )

    row = QHBoxLayout()
    imp = QPushButton("Import playlist…")
    imp.setObjectName("primaryButton")
    imp.clicked.connect(self._import_playlist_file)
    exp = QPushButton("Export selected…")
    exp.clicked.connect(self._export_selected_playlist)
    expq = QPushButton("Export queue…")
    expq.clicked.connect(self._export_queue)
    row.addWidget(imp)
    row.addWidget(exp)
    row.addWidget(expq)
    row.addStretch(1)
    l.addLayout(row)

    self.playlists_list = EmptyStateListWidget()
    self.playlists_list.set_empty_state(
        "Your journeys will live here",
        "Import XSPF, M3U or M3U8, or let Ask Melodex create something and save it.",
    )
    self.playlists_list.itemDoubleClicked.connect(self._play_saved_playlist)
    l.addWidget(self.playlists_list, 1)


def _build_moments(self):
    l = self._page_layout(
        "moments",
        "Moments",
        "Bookmark the exact few seconds you never want to lose.",
    )
    self.moments_list = EmptyStateListWidget()
    self.moments_list.set_empty_state(
        "Save the parts that matter",
        "While a track is playing, press Moment in the player bar. Melodex saves the exact position for later.",
    )
    l.addWidget(self.moments_list, 1)


def _build_ask(self):
    l = self._page_layout(
        "ask",
        "Ask Melodex",
        "Optional. Connect OpenWebUI, Ollama or another compatible model when you want conversational control.",
    )

    self.chat = QTextEdit()
    self.chat.setReadOnly(True)
    self.chat.setHtml(
        """
        <div style="margin:28px;color:#9aa4b3">
          <div style="font-size:22px;font-weight:700;color:#eef2f8">Ask in plain language</div>
          <p style="font-size:14px;line-height:1.55">
            Shape a journey, change direction, rediscover old favourites, or describe a mood.
            Melodex still works normally when no LLM is connected.
          </p>
          <p style="color:#6f7d91">Try one of the prompts below, or write your own.</p>
        </div>
        """
    )
    l.addWidget(self.chat, 1)

    suggestions = QHBoxLayout()
    prompts = [
        "Keep this mood, but make the next hour stranger",
        "Build me a 45 minute focus journey",
        "Rediscover something I have forgotten",
    ]
    for prompt in prompts:
        button = QPushButton(prompt)
        button.setObjectName("choiceButton")
        button.clicked.connect(lambda _=False, p=prompt: self.ask_box.setText(p))
        suggestions.addWidget(button)
    l.addLayout(suggestions)

    row = QHBoxLayout()
    self.ask_box = QLineEdit()
    self.ask_box.setPlaceholderText("Tell Melodex what you want to hear…")
    self.ask_box.returnPressed.connect(self._ask)
    ask = QPushButton("Ask")
    ask.setObjectName("primaryButton")
    ask.clicked.connect(self._ask)
    cfg = QPushButton("Connect LLM…")
    cfg.clicked.connect(self._llm_settings_dialog)
    row.addWidget(self.ask_box, 1)
    row.addWidget(ask)
    row.addWidget(cfg)
    l.addLayout(row)


def _build_sources(self):
    l = self._page_layout(
        "sources",
        "Music sources",
        "Connect places to listen. The technical provider machinery stays out of the way until you ask for it.",
    )

    self.sources_list = EmptyStateListWidget()
    self.sources_list.setObjectName("sourcesList")
    self.sources_list.set_empty_state(
        "No music sources yet",
        "Add a local folder, a personal stream or a Melodex provider.",
    )
    l.addWidget(self.sources_list, 1)

    row = QHBoxLayout()
    local = QPushButton("Add local folder…")
    local.setObjectName("primaryButton")
    local.clicked.connect(self._choose_music_folder)

    streams = QPushButton("User Streams…")
    streams.clicked.connect(self._user_streams_dialog)

    jam = QPushButton("Jamendo settings…")
    jam.clicked.connect(self._jamendo_settings)

    remove = QPushButton("Remove / disconnect…")
    remove.setToolTip("Remove the selected external provider, or disconnect a built-in source")
    remove.clicked.connect(self._remove_selected_source)

    row.addWidget(local)
    row.addWidget(streams)
    row.addWidget(jam)
    row.addStretch(1)
    row.addWidget(remove)
    l.addLayout(row)

    self.source_power_panel = QWidget()
    self.source_power_panel.setObjectName("softCard")
    power = QVBoxLayout(self.source_power_panel)
    power.setContentsMargins(14, 12, 14, 12)
    power.setSpacing(8)

    advanced_title = QLabel("Advanced provider tools")
    advanced_title.setObjectName("sectionTitle")
    power.addWidget(advanced_title)

    provider_row = QHBoxLayout()
    inst = QPushButton("Install .mdxprovider…")
    inst.clicked.connect(self._install_provider)
    bridge = QPushButton("Provider Bridge…")
    bridge.clicked.connect(self._bridge_dialog)
    restore_defaults = QPushButton("Restore bundled sources")
    restore_defaults.setToolTip(
        "Restore any bundled no-key providers you previously removed"
    )
    restore_defaults.clicked.connect(self._restore_bundled_sources)

    provider_row.addWidget(inst)
    provider_row.addWidget(bridge)
    provider_row.addWidget(restore_defaults)
    provider_row.addStretch(1)
    power.addLayout(provider_row)

    priority = QHBoxLayout()
    up = QPushButton("Prefer source ↑")
    down = QPushButton("Prefer source ↓")
    up.clicked.connect(lambda: self._move_source(-1))
    down.clicked.connect(lambda: self._move_source(1))
    priority.addWidget(up)
    priority.addWidget(down)
    priority.addStretch(1)
    power.addLayout(priority)

    self.source_power_panel.setVisible(self.power_toggle.isChecked())
    l.addWidget(self.source_power_panel)


def _open_page(self, name: str):
    self.current_page = name
    self.stack.setCurrentWidget(self.pages[name])
    self._set_active_nav(name)

    if name == "home":
        self._show_home()
    elif name == "library":
        self._refresh_library()
    elif name == "sources":
        self._refresh_sources()
    elif name == "moments":
        self._refresh_moments()
    elif name == "playlists":
        self._refresh_playlists()
    elif name == "for_you":
        self._refresh_taste()
    elif name == "discover":
        self._refresh_source_combo()


def _show_home(self):
    self._refresh_library()
    self._refresh_sources()
    self._refresh_taste()

    count = len(self.providers.local_catalog())
    src = len(self.providers.providers)
    flow = (
        "Deep Flow analysis ready"
        if self.flow.analysis_available
        else "Flow works from metadata; ffmpeg adds deeper local analysis"
    )
    self.home_status.setText(
        f"<b>{count:,}</b> local tracks &nbsp; • &nbsp; "
        f"<b>{src}</b> connected sources<br>{flow}"
    )

    if self.current_track:
        artist = str(self.current_track.get("artist") or "Unknown artist")
        title = str(self.current_track.get("title") or "Unknown track")
        self.home_resume.setText(
            f"<b>{artist}</b><br>{title}<br>"
            "<span style='color:#6F7D91'>Your current journey is ready when you are.</span>"
        )
    else:
        self.home_resume.setText(
            "Nothing playing yet.<br>"
            "<span style='color:#6F7D91'>Start with Play for me and Melodex will build from there.</span>"
        )

    moments = list(self.state.moments() or [])[:3]
    if not moments:
        self.home_moments.setText(
            "No saved moments yet.<br>"
            "<span style='color:#6F7D91'>Press Moment during a track to bookmark the exact second.</span>"
        )
    else:
        rows = []
        for m in moments:
            track = m.get("track") if isinstance(m.get("track"), dict) else {}
            sec = int(m.get("position_ms", 0)) // 1000
            rows.append(
                f"{sec // 60}:{sec % 60:02d} &nbsp; "
                f"{track.get('artist', 'Unknown artist')} — "
                f"{track.get('title', 'Unknown track')}"
            )
        self.home_moments.setText("<br>".join(rows))


def _power_changed(self, _):
    enabled = self.power_toggle.isChecked()
    if hasattr(self, "source_power_panel"):
        self.source_power_panel.setVisible(enabled)
    if hasattr(self, "sources_list"):
        self._refresh_sources()
    self.statusBar().showMessage(
        "Advanced tools shown" if enabled else "Advanced tools hidden",
        2500,
    )



def _remove_selected_source(self):
    item = self.sources_list.currentItem()
    if item is None:
        self.statusBar().showMessage("Select a source first", 3000)
        return

    pid = str(item.data(Qt.UserRole) or "").strip()
    provider = self.providers.providers.get(pid)
    name = (
        provider.info.name.replace(" (reference provider)", "")
        if provider is not None
        else pid
    )

    # Built-in source adapters remain part of Melodex; "remove" means
    # disconnecting their user data/configuration rather than deleting code.
    if pid == "local":
        roots = list(self.providers.settings.get("local_roots", []) or [])
        if not roots:
            QMessageBox.information(
                self,
                "This computer",
                "The local-music source is built in and currently has no folders connected.",
            )
            return

        answer = QMessageBox.question(
            self,
            "Disconnect local music?",
            "Remove all connected local music folders from Melodex?\n\n"
            "Your audio files will not be deleted from disk.",
            QMessageBox.Yes | QMessageBox.Cancel,
            QMessageBox.Cancel,
        )
        if answer != QMessageBox.Yes:
            return

        self.providers.set_local_roots([])
        self._refresh_sources()
        self._refresh_library()
        self.statusBar().showMessage("Local music folders disconnected", 3500)
        return

    if pid == "jamendo":
        configured = bool(
            str(self.providers.settings.get("jamendo_client_id", "")).strip()
        )
        if not configured:
            QMessageBox.information(
                self,
                "Jamendo",
                "Jamendo is built in and is already disconnected.",
            )
            return

        answer = QMessageBox.question(
            self,
            "Disconnect Jamendo?",
            "Remove the saved Jamendo client ID from Melodex?",
            QMessageBox.Yes | QMessageBox.Cancel,
            QMessageBox.Cancel,
        )
        if answer != QMessageBox.Yes:
            return

        self.providers.set_jamendo_client_id("")
        self._refresh_sources()
        self.statusBar().showMessage("Jamendo disconnected", 3500)
        return

    if pid == "streams":
        # User Streams is a built-in adapter. Individual streams are already
        # removable in its management dialog.
        if not self.providers.user_streams():
            QMessageBox.information(
                self,
                "User Streams",
                "User Streams is built in and currently contains no streams.",
            )
            return
        self._user_streams_dialog()
        self._refresh_sources()
        return

    # Installed .mdxprovider packages can be removed completely. Bundled
    # providers are also marked disabled so they stay removed after restart.
    if provider is None:
        self.statusBar().showMessage("That source is no longer installed", 3000)
        self._refresh_sources()
        return

    answer = QMessageBox.question(
        self,
        f"Remove {name}?",
        f"Remove “{name}” from Melodex?\n\n"
        "This deletes the installed provider package from Melodex. "
        "It does not delete music from the provider's website or service.",
        QMessageBox.Yes | QMessageBox.Cancel,
        QMessageBox.Cancel,
    )
    if answer != QMessageBox.Yes:
        return

    try:
        removed = self.providers.remove_provider(pid)
    except Exception as exc:
        QMessageBox.critical(
            self,
            "Could not remove source",
            f"Melodex could not remove the provider:\n{exc}",
        )
        return

    if removed:
        self._refresh_sources()
        self.statusBar().showMessage(f"{name} removed", 4000)


def _restore_bundled_sources(self):
    try:
        restored = self.providers.restore_bundled_providers()
    except Exception as exc:
        QMessageBox.critical(
            self,
            "Could not restore bundled sources",
            str(exc),
        )
        return

    self._refresh_sources()
    if restored:
        names = [
            self.providers.providers[pid].info.name
            for pid in restored
            if pid in self.providers.providers
        ]
        self.statusBar().showMessage(
            "Restored bundled sources: " + ", ".join(names),
            5000,
        )
    else:
        self.statusBar().showMessage(
            "All bundled sources are already available",
            3500,
        )


def _refresh_sources(self):
    self.sources_list.clear()
    advanced = self.power_toggle.isChecked()

    for pid in self.providers.provider_order():
        p = self.providers.providers[pid]
        name = p.info.name.replace(" (reference provider)", "")

        if pid == "local":
            count = len(self.providers.local_catalog())
            status = f"{count:,} tracks" if count else "Add music"
        elif pid == "jamendo":
            configured = bool(
                str(self.providers.settings.get("jamendo_client_id", "")).strip()
            )
            status = "Connected" if configured else "Needs setup"
        elif pid == "streams":
            count = len(self.providers.user_streams())
            status = f"{count} stream" if count == 1 else f"{count} streams"
        else:
            status = "Connected"

        description = str(p.info.description or "").strip()
        examples = source_examples(pid, name)
        lines = [f"{name}    ·    {status}"]
        if description:
            lines.append(description)
        if examples:
            lines.append(f"Try: {examples}")
        if advanced:
            lines.append(f"Provider ID: {pid}")

        item = QListWidgetItem("\n".join(lines))
        item.setData(Qt.UserRole, pid)
        self.sources_list.addItem(item)

    self._refresh_source_combo()


def _refresh_library(self):
    self.library_list.clear()
    for track in self.providers.local_catalog():
        artist = str(track.get("artist") or "Unknown artist")
        title = str(track.get("title") or "Unknown track")
        album = str(track.get("album") or "").strip()
        text = f"{artist} — {title}"
        if album:
            text += f"\n{album}"
        item = QListWidgetItem(text)
        item.setData(Qt.UserRole, track)
        self.library_list.addItem(item)


def _refresh_playlists(self):
    self.playlists_list.clear()
    for playlist in self.state.playlists():
        tracks = self._playlist_tracks(playlist)
        count = len(tracks)
        desc = str(playlist.get("description") or "").strip()
        second = f"{count} track" if count == 1 else f"{count} tracks"
        if desc:
            second += f"  ·  {desc}"
        item = QListWidgetItem(f"{playlist.get('name')}\n{second}")
        item.setData(Qt.UserRole, playlist)
        self.playlists_list.addItem(item)


def _refresh_moments(self):
    self.moments_list.clear()
    for moment in self.state.moments():
        track = moment.get("track") if isinstance(moment.get("track"), dict) else {}
        sec = int(moment.get("position_ms", 0)) // 1000
        label = str(moment.get("label") or "").strip()

        text = (
            f"{sec // 60}:{sec % 60:02d}    "
            f"{track.get('artist', 'Unknown artist')} — "
            f"{track.get('title', 'Unknown track')}"
        )
        if label:
            text += f"\n{label}"
        self.moments_list.addItem(text)


def _refresh_taste(self):
    summary = self.state.taste_summary()
    tracks = int(summary.get("tracks", 0) or 0)
    artists = int(summary.get("artists", 0) or 0)

    if tracks == 0:
        text = (
            "Start listening, keeping and skipping. "
            "Melodex will learn locally from those signals."
        )
    else:
        text = (
            f"<b>{tracks:,}</b> tracks understood &nbsp; • &nbsp; "
            f"<b>{artists:,}</b> artists recognised<br>"
            "Every Keep, skip and completed listen gives the next journey a little more context."
        )
    self.taste_label.setText(text)


def _search(self):
    query = self.search_box.text().strip()
    pid = str(self.search_source.currentData() or "all")
    if not query:
        return

    self.results.clear()
    self.results.set_empty_state("Searching…", f'Looking for “{query}”')
    self._run_async(
        lambda: self.providers.search(query, pid, 100),
        self._show_results,
    )


def _show_results(self, tracks):
    self.results.clear()
    if not tracks:
        self.results.set_empty_state(
            "No matches yet",
            "Try a broader search, choose All sources, or connect another source.",
        )
        return

    for track in tracks:
        artist = str(track.get("artist") or "Unknown artist")
        title = str(track.get("title") or "Unknown track")
        album = str(track.get("album") or "").strip()
        source = friendly_source(track)
        details = "  ·  ".join(x for x in (album, source) if x)
        text = f"{artist} — {title}" + (f"\n{details}" if details else "")

        item = QListWidgetItem(text)
        item.setData(Qt.UserRole, track)
        self.results.addItem(item)


def _on_track_changed(self, track):
    import time

    if self._closing:
        return

    if (
        self.current_track
        and self.current_track_started
        and time.time() - self.current_track_started < 30
    ):
        self.state.record_skip(self.current_track)

    self.current_track = dict(track)
    self.current_track_started = time.time()
    self.current_history_id = self.state.record_play(track)

    title = str(track.get("title") or "Unknown track")
    artist = str(track.get("artist") or "Unknown artist")
    album = str(track.get("album") or "").strip()
    source = friendly_source(track)

    bits = [artist]
    if album:
        bits.append(album)
    if source:
        bits.append(source)

    src = str(track.get("source_page") or "")
    attr = str(track.get("attribution") or "")
    meta = "   ·   ".join(bits)
    if src:
        meta += f'   ·   <a href="{src}">{attr or "Source"}</a>'

    self.now_title.setText(title)
    self.now_meta.setText(meta)
    self._set_player_art(dict(track))

    if hasattr(self, "home_resume"):
        self.home_resume.setText(
            f"<b>{artist}</b><br>{title}<br>"
            "<span style='color:#6F7D91'>Playing now</span>"
        )

    if hasattr(self, "rich_now"):
        self.rich_now.set_track(dict(track))


def _rich_build(self):
    outer = QVBoxLayout(self)
    outer.setContentsMargins(0, 6, 0, 0)
    outer.setSpacing(16)

    hero = QHBoxLayout()
    hero.setSpacing(28)
    outer.addLayout(hero)

    self.art = QLabel("♫")
    self.art.setAlignment(Qt.AlignCenter)
    self.art.setFixedSize(330, 330)
    self.art.setStyleSheet(
        "background:qlineargradient(x1:0,y1:0,x2:1,y2:1,"
        "stop:0 #14243d,stop:0.52 #171b2a,stop:1 #2b1832);"
        "border:1px solid #303b4c;border-radius:20px;"
        "font-size:82px;color:#718096"
    )
    hero.addWidget(self.art, 0, Qt.AlignTop)

    right = QVBoxLayout()
    right.setSpacing(8)
    hero.addLayout(right, 1)

    eyebrow = QLabel("NOW PLAYING")
    eyebrow.setStyleSheet(
        "font-size:10px;font-weight:700;letter-spacing:1.6px;color:#6f7d91"
    )

    self.title = QLabel("Nothing playing")
    self.title.setWordWrap(True)
    self.title.setStyleSheet("font-size:34px;font-weight:760;color:#f7f8fb")

    self.artist = QLabel("")
    self.artist.setWordWrap(True)
    self.artist.setStyleSheet("font-size:21px;color:#c8ccd2")

    self.album = QLabel("")
    self.album.setWordWrap(True)
    self.album.setStyleSheet("font-size:15px;color:#aab0ba")

    self.facts = QLabel("")
    self.facts.setWordWrap(True)
    self.facts.setStyleSheet("color:#8f96a1")

    self.progress = QLabel("")
    self.progress.setWordWrap(True)
    self.progress.setStyleSheet("color:#7eb4ff;font-size:12px")

    self.links = QLabel("")
    self.links.setOpenExternalLinks(True)
    self.links.setWordWrap(True)

    right.addWidget(eyebrow)
    right.addWidget(self.title)
    right.addWidget(self.artist)
    right.addWidget(self.album)
    right.addWidget(self.facts)
    right.addSpacing(4)
    right.addWidget(self.progress)
    right.addWidget(self.links)
    right.addStretch(1)

    self.art_source = QLabel("")
    self.art_source.setWordWrap(True)
    self.art_source.setStyleSheet("color:#777f8a;font-size:11px")
    right.addWidget(self.art_source)

    # Artist imagery still appears inside the Artist tab. The hero no longer
    # shows a blank photo placeholder when no image is available.
    self.artist_photo_thumb = QLabel("")
    self.artist_photo_thumb.setFixedSize(1, 1)
    self.artist_photo_thumb.hide()

    self.artist_photo_credit = QLabel("")
    self.artist_photo_credit.setOpenExternalLinks(True)
    self.artist_photo_credit.hide()

    self.tabs = QTabWidget()
    outer.addWidget(self.tabs, 1)

    self.lyrics = QTextBrowser()
    self.artist_info = QTextBrowser()
    self.releases = QTextBrowser()
    self.credits = QTextBrowser()
    self.info = QTextBrowser()

    for browser in (
        self.lyrics,
        self.artist_info,
        self.releases,
        self.credits,
        self.info,
    ):
        browser.setOpenExternalLinks(True)

    self.tabs.addTab(self.lyrics, "Lyrics")
    self.tabs.addTab(self.artist_info, "Artist")
    self.tabs.addTab(self.releases, "Releases")
    self.tabs.addTab(self.credits, "Credits")
    self.tabs.addTab(self.info, "Info")
    self._empty_tabs()


def _rich_set_art(self, path: str):
    if path and Path(path).exists():
        pix = QPixmap(path)
        if not pix.isNull():
            self.art.setText("")
            self.art.setPixmap(
                pix.scaled(
                    self.art.size(),
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation,
                )
            )
            self._apply_accent(QImage(path))
            return

    mark_path = Path(__file__).resolve().parent / "assets" / "melodex-mark.png"
    mark = QPixmap(str(mark_path))

    self.art.setPixmap(QPixmap())
    if not mark.isNull():
        self.art.setText("")
        self.art.setPixmap(
            mark.scaled(132, 132, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        )
    else:
        self.art.setText("♫")

    self.title.setStyleSheet("font-size:34px;font-weight:760;color:#f7f8fb")
    self.art.setStyleSheet(
        "background:qlineargradient(x1:0,y1:0,x2:1,y2:1,"
        "stop:0 #14243d,stop:0.52 #171b2a,stop:1 #2b1832);"
        "border:1px solid #303b4c;border-radius:20px"
    )
    self.setStyleSheet("")



def _rich_apply_accent(self, image: QImage):
    if image.isNull():
        return

    small = image.scaled(24, 24, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
    r = g = b = count = 0
    for y in range(small.height()):
        for x in range(small.width()):
            colour = QColor(small.pixel(x, y))
            mx = max(colour.red(), colour.green(), colour.blue())
            mn = min(colour.red(), colour.green(), colour.blue())
            if mx < 28 or (mx - mn < 8 and mx > 220):
                continue
            r += colour.red()
            g += colour.green()
            b += colour.blue()
            count += 1

    if not count:
        return

    accent = QColor(r // count, g // count, b // count)
    if accent.lightness() < 95:
        accent = accent.lighter(170)
    if accent.lightness() > 205:
        accent = accent.darker(120)

    dark = QColor(accent).darker(520)
    self.title.setStyleSheet("font-size:34px;font-weight:760;color:#f7f8fb")
    self.progress.setStyleSheet(
        f"color:{accent.name()};font-size:12px"
    )
    self.art.setStyleSheet(
        f"background:#181b20;border:2px solid {accent.name()};border-radius:20px"
    )
    self.setStyleSheet(
        "RichNowPlayingWidget{"
        f"background:qlineargradient(x1:0,y1:0,x2:1,y2:1,"
        f"stop:0 {dark.name()},stop:0.44 #0A0D12,stop:1 #0A0D12);"
        "border-radius:14px}"
    )


def _rich_apply_artwork(self, artwork: dict[str, Any]):
    path = str(artwork.get("path") or "")
    self._set_art(path)
    source = str(artwork.get("source") or "")
    self.art_source.setText(("Artwork: " + source) if source else "")

    # Keep the compact player visually synchronized with the enriched artwork.
    window = self.window()
    if path and Path(path).exists() and hasattr(window, "player_art"):
        pix = QPixmap(path)
        if not pix.isNull():
            window.player_art.setText("")
            window.player_art.setPixmap(
                pix.scaled(
                    window.player_art.size(),
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation,
                )
            )

def apply_redesign() -> None:
    """Install the redesigned UI methods before MainWindow is instantiated."""

    # Main window helpers.
    MainWindow._add_nav_group = _add_nav_group
    MainWindow._set_active_nav = _set_active_nav
    MainWindow._player_more_menu = _player_more_menu
    MainWindow._set_player_art = _set_player_art
    MainWindow._set_journey_mode = _set_journey_mode

    # Main window surfaces.
    MainWindow._build_ui = _build_ui
    MainWindow._page_layout = _page_layout
    MainWindow._build_home = _build_home
    MainWindow._build_now_playing = _build_now_playing
    MainWindow._build_for_you = _build_for_you
    MainWindow._build_discover = _build_discover
    MainWindow._build_library = _build_library
    MainWindow._build_playlists = _build_playlists
    MainWindow._build_moments = _build_moments
    MainWindow._build_ask = _build_ask
    MainWindow._build_sources = _build_sources

    # Navigation/data presentation.
    MainWindow.open_page = _open_page
    MainWindow._show_home = _show_home
    MainWindow._power_changed = _power_changed
    MainWindow._remove_selected_source = _remove_selected_source
    MainWindow._restore_bundled_sources = _restore_bundled_sources
    MainWindow._refresh_sources = _refresh_sources
    MainWindow._refresh_library = _refresh_library
    MainWindow._refresh_playlists = _refresh_playlists
    MainWindow._refresh_moments = _refresh_moments
    MainWindow._refresh_taste = _refresh_taste
    MainWindow._search = _search
    MainWindow._show_results = _show_results
    MainWindow._on_track_changed = _on_track_changed

    # Now Playing presentation.
    RichNowPlayingWidget._build = _rich_build
    RichNowPlayingWidget._set_art = _rich_set_art
    RichNowPlayingWidget._apply_accent = _rich_apply_accent
    RichNowPlayingWidget._apply_artwork = _rich_apply_artwork
