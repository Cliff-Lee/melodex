#!/usr/bin/env python3
"""R1-3D: exercise Melodex's real Qt player with an authorized OpenSubsonic server.

Expected to run with an isolated PulseAudio sink and a disposable account.
This script checks Qt decode/play/seek/pause/resume; the CI caller must
independently verify non-silent PCM was emitted at the sink monitor.
Never print URLs, credentials, track metadata, or untrusted exception text.
"""
from __future__ import annotations

import getpass
import json
import os
import sys
import time
from pathlib import Path

from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtWidgets import QApplication

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from melodex.player import FlowPlayer  # noqa: E402
from melodex.provider import ExternalProvider  # noqa: E402

PROVIDER_ROOT = ROOT / "bundled_provider_sources" / "opensubsonic_personal"


def _until(app: QApplication, predicate, timeout_seconds: float) -> bool:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        app.processEvents()
        if predicate():
            return True
        time.sleep(0.015)
    return False


def qualify(server: str, username: str, password: str, *,
            allow_http: bool, query: str) -> dict[str, bool]:
    steps = {
        "provider_authenticated": False,
        "qt_playback_started": False,
        "qt_position_advanced": False,
        "qt_seekable": False,
        "qt_seek_advanced": False,
        "qt_pause": False,
        "qt_resume": False,
        "qt_gateway_source": False,
    }
    app = QApplication.instance() or QApplication([])
    manifest = json.loads((PROVIDER_ROOT / "manifest.json").read_text("utf-8"))
    provider = ExternalProvider(PROVIDER_ROOT, manifest)
    player = None
    try:
        provider.configure({
            "server_url": server,
            "username": username,
            "password": password,
            "allow_insecure_http": bool(allow_http),
        })
        health = provider.health_check(timeout=10)
        if health.get("status") != "ready":
            return steps
        songs = provider.search(query, limit=4)
        if not songs:
            return steps
        steps["provider_authenticated"] = True

        # The same two-deck QMediaPlayer/QAudioOutput engine as production.
        player = FlowPlayer(
            provider.resolve,
            playback_refresher=provider.refresh,
        )
        player._playback_recovery_delays_ms = (250, 450)
        player.set_queue(songs[:1], 0, autoplay=True, intent="provider")
        deck = player.players[player.active]
        steps["qt_gateway_source"] = _until(
            app, lambda: deck.source().scheme() == "http"
            and deck.source().host() in {"127.0.0.1", "localhost"}, 8.0,
        )

        steps["qt_playback_started"] = _until(
            app, lambda: deck.playbackState() == QMediaPlayer.PlayingState, 12.0,
        )
        steps["qt_position_advanced"] = _until(
            app, lambda: deck.position() >= 650, 12.0,
        )
        steps["qt_seekable"] = _until(
            app, lambda: deck.isSeekable() and deck.duration() >= 6000, 6.0,
        )

        if steps["qt_seekable"]:
            player.seek(3500)
            steps["qt_seek_advanced"] = _until(
                app, lambda: deck.position() >= 3900, 8.0,
            )
        if deck.playbackState() == QMediaPlayer.PlayingState:
            before_pause = int(deck.position())
            player.play_pause()
            steps["qt_pause"] = _until(
                app, lambda: deck.playbackState() == QMediaPlayer.PausedState,
                4.0,
            )
            if steps["qt_pause"]:
                player.play_pause()
                steps["qt_resume"] = _until(
                    app,
                    lambda: (deck.playbackState() == QMediaPlayer.PlayingState
                             and deck.position() >= before_pause + 300),
                    7.0,
                )
        return steps
    finally:
        if player is not None:
            player.close()
            player.deleteLater()
        provider.close()
        app.processEvents()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        app.processEvents()


def main() -> int:
    server = os.environ.get("MELODEX_SUBSONIC_URL", "").strip()
    username = os.environ.get("MELODEX_SUBSONIC_USERNAME", "").strip()
    password = os.environ.get("MELODEX_SUBSONIC_PASSWORD", "")
    query = os.environ.get("MELODEX_SUBSONIC_QUERY", "a")
    allow_http = os.environ.get("MELODEX_SUBSONIC_ALLOW_HTTP", "") == "1"
    if server and username and not password and sys.stdin.isatty():
        password = getpass.getpass("Subsonic account password (hidden input): ")
    passed = False
    steps = {"required_configuration": bool(server and username and password)}
    if steps["required_configuration"]:
        try:
            steps = qualify(server, username, password, allow_http=allow_http,
                            query=query)
            passed = all(steps.values())
        except Exception:
            # Provider and Qt backend errors can include auth-token URLs.
            steps["safe_qt_probe_completed"] = False
    print(json.dumps({
        "campaign": "R1-3D",
        "scope": "real FlowPlayer/QMediaPlayer output to host's audio sink",
        "checks": steps,
        "passed": passed,
        "note": "PCM energy must be independently verified at the audio sink; physical speakers untested.",
    }, indent=2, sort_keys=True), flush=True)
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
