#!/usr/bin/env python3
"""R1-3E: injected network-error recovery while real Navidrome is briefly paused.

Runs only against an explicitly specified disposable Docker container.
Exercises production FlowPlayer + BackgroundScheduler + ExternalProvider +
PlaybackGateway + QMediaPlayer + QAudioOutput. This does NOT demonstrate
that all natural network outages trigger Qt NetworkError; injection is explicit.
No server URL, token, account, track title, or exception is printed.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtWidgets import QApplication

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from melodex.background_scheduler import BackgroundScheduler  # noqa: E402
from melodex.player import FlowPlayer  # noqa: E402
from melodex.provider import ExternalProvider  # noqa: E402

PROVIDER_ROOT = ROOT / "bundled_provider_sources" / "opensubsonic_personal"


def _until(app, condition, timeout_seconds):
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        app.processEvents()
        if condition():
            return True
        time.sleep(0.018)
    return False


def _docker(action, container):
    if action not in {"pause", "unpause"}:
        raise ValueError("Only pause/unpause supported")
    subprocess.run(
        ["docker", action, container], check=True,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=20,
    )


def qualify(server, username, password, container, *, query, allow_http, diagnostics):
    steps = {
        "authenticated_track": False,
        "initial_qt_playing": False,
        "initial_qt_position": False,
        "server_pause_applied": False,
        "injected_network_error": False,
        "scheduler_refresh_dispatched": False,
        "recovery_commit": False,
        "same_track_retained": False,
        "position_resumed": False,
        "playing_after_recovery": False,
    }
    app = QApplication.instance() or QApplication([])
    provider = ExternalProvider(
        PROVIDER_ROOT,
        json.loads((PROVIDER_ROOT / "manifest.json").read_text("utf-8")),
    )
    scheduler = BackgroundScheduler(max_workers=2)
    player = None
    release_thread = None
    server_paused = False
    try:
        provider.configure({
            "server_url": server, "username": username,
            "password": password, "allow_insecure_http": bool(allow_http),
        })
        if provider.health_check(timeout=10).get("status") != "ready":
            return steps
        songs = provider.search(query, limit=1)
        if not songs:
            return steps
        steps["authenticated_track"] = True
        track_identity = songs[0].get("track_id")
        player = FlowPlayer(
            provider.resolve, playback_refresher=provider.refresh,
            playback_refresh_scheduler=scheduler,
        )
        player._playback_recovery_delays_ms = (850, 1800)
        player.set_queue(songs[:1], autoplay=True, intent="provider")
        deck = player.players[player.active]
        steps["initial_qt_playing"] = _until(
            app, lambda: deck.playbackState() == QMediaPlayer.PlayingState, 9,
        )
        steps["initial_qt_position"] = _until(
            app, lambda: deck.position() >= 1100, 9,
        )
        if not all((steps["initial_qt_playing"], steps["initial_qt_position"])):
            return steps
        before = int(deck.position())

        _docker("pause", container)
        server_paused = True
        steps["server_pause_applied"] = True

        # Server stays unavailable while the error handler schedules recovery.
        # It is deliberately an injected error: Qt may have buffered the media.
        def release_server():
            time.sleep(1.3)
            _docker("unpause", container)

        release_thread = threading.Thread(target=release_server, daemon=True)
        release_thread.start()
        scope = getattr(QMediaPlayer, "Error", QMediaPlayer)
        player._on_player_error(
            player.active, scope.NetworkError,
            "Synthetic network interruption in controlled CI",
        )
        steps["injected_network_error"] = True
        steps["scheduler_refresh_dispatched"] = _until(
            app, lambda: player.diagnostics_snapshot()["recovery_attempts"] >= 1, 8,
        )
        steps["recovery_commit"] = _until(
            app, lambda: player.diagnostics_snapshot()["recovery_successes"] >= 1, 16,
        )
        steps["same_track_retained"] = (
            player.current_track() is not None
            and player.current_track().get("track_id") == track_identity
        )
        steps["playing_after_recovery"] = _until(
            app, lambda: deck.playbackState() == QMediaPlayer.PlayingState, 8,
        )
        steps["position_resumed"] = _until(
            app, lambda: deck.position() >= before + 350, 8,
        )
        return steps
    finally:
        if player is not None:
            snapshot = player.diagnostics_snapshot()
            safe_metrics = (
                "recovery_attempts", "recovery_successes", "recovery_refresh_failures",
                "recovery_source_rejections", "recovery_submit_rejected",
                "recovery_stale_results", "recovery_exhausted", "recovery_unavailable",
                "playback_errors", "transient_source_errors", "permanent_source_errors",
                "buffer_stall_events", "seek_requests", "natural_ends",
            )
            diagnostics["metrics"] = {
                key: int(snapshot.get(key, 0)) for key in safe_metrics
            }
            live_deck = player.players[player.active]
            diagnostics["media_status"] = str(live_deck.mediaStatus().name)
            diagnostics["playback_state"] = str(live_deck.playbackState().name)
            diagnostics["position_ms"] = int(live_deck.position())
            diagnostics["duration_ms"] = int(live_deck.duration())
            diagnostics["candidate_pending"] = bool(player._playback_recovery_candidate)
            diagnostics["request_pending"] = bool(player._playback_recovery_pending)
        if release_thread is not None:
            release_thread.join(timeout=18)
        # Always unfreeze the disposable server, including failed tests.
        if server_paused:
            try:
                _docker("unpause", container)
            except Exception:
                pass
        if player is not None:
            player.close()
            player.deleteLater()
        scheduler.shutdown(wait=True)
        provider.close()
        app.processEvents()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        app.processEvents()


def main():
    env = os.environ
    kwargs = {
        "server": env.get("MELODEX_SUBSONIC_URL", "").strip(),
        "username": env.get("MELODEX_SUBSONIC_USERNAME", "").strip(),
        "password": env.get("MELODEX_SUBSONIC_PASSWORD", ""),
        "container": env.get("MELODEX_SUBSONIC_CONTAINER", "").strip(),
        "query": env.get("MELODEX_SUBSONIC_QUERY", "a"),
        "allow_http": env.get("MELODEX_SUBSONIC_ALLOW_HTTP", "") == "1",
    }
    complete = False
    diagnostics = {}
    steps = {"disposable_configuration": all(kwargs[x] for x in (
        "server", "username", "password", "container",
    ))}
    if steps["disposable_configuration"]:
        try:
            steps = qualify(**kwargs, diagnostics=diagnostics)
            complete = all(steps.values())
        except Exception:
            # Exceptions from playback backends may embed token-bearing URLs.
            steps["controlled_trial_completed"] = False
    print(json.dumps({
        "campaign": "R1-3E",
        "injected_network_error": True,
        "scope": "controlled Docker pause plus explicitly injected Qt NetworkError",
        "checks": steps,
        "diagnostics": diagnostics,
        "passed": complete,
        "note": "Not a natural outage-detection test or physical-speaker qualification.",
    }, indent=2, sort_keys=True), flush=True)
    return 0 if complete else 1


if __name__ == "__main__":
    raise SystemExit(main())
