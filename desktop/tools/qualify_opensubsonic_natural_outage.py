#!/usr/bin/env python3
"""R1-3F: detect a real stalled stream without injecting a Qt error.

A local throttling reverse proxy ensures the disposable Navidrome stream is
still in flight when the server container is paused. Melodex's real
QMediaPlayer/FlowPlayer signals, no-progress stall timer, scheduler and source
recovery path are exercised. No call to _on_player_error is made by this test.
The proxy does not log paths, headers, credentials, URLs or exception details.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

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
CHUNK_BYTES = 4096
STREAM_CHUNK_DELAY_SECONDS = 0.125  # 32 KiB/s: close to real-time for the fixture.


def _until(app, condition, timeout_seconds):
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        app.processEvents()
        if condition():
            return True
        time.sleep(0.018)
    return bool(condition())


def _docker(action, container):
    if action not in {"pause", "unpause"}:
        raise ValueError("Only pause/unpause supported")
    subprocess.run(
        ["docker", action, container],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=20,
    )


class _ProxyServer(ThreadingHTTPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, address, upstream):
        self.upstream = upstream.rstrip("/")
        self.transport_gate = threading.Event()
        self.transport_gate.set()
        self.metrics_lock = threading.Lock()
        self.metrics = {"stream_gate_waits": 0, "request_gate_waits": 0}
        super().__init__(address, _ProxyHandler)

    def wait_for_transport(self, *, stream: bool, timeout: float = 35.0) -> bool:
        if not self.transport_gate.is_set():
            key = "stream_gate_waits" if stream else "request_gate_waits"
            with self.metrics_lock:
                self.metrics[key] += 1
        return self.transport_gate.wait(timeout=timeout)

    def metrics_snapshot(self):
        with self.metrics_lock:
            return dict(self.metrics)


class _ProxyHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, _format, *_args):
        # BaseHTTPRequestHandler's default log would include token-bearing paths.
        return

    def do_GET(self):
        is_stream = urlsplit(self.path).path.endswith("/stream.view")
        if not self.server.wait_for_transport(stream=is_stream):
            self.send_error(504, "Transport unavailable")
            return
        upstream_url = self.server.upstream + self.path
        headers = {}
        for name in ("Accept", "User-Agent", "Range", "If-Range"):
            value = self.headers.get(name)
            if value:
                headers[name] = value
        request = Request(upstream_url, headers=headers, method="GET")
        response = None
        try:
            try:
                response = urlopen(request, timeout=30)
            except HTTPError as exc:
                response = exc
            status = int(getattr(response, "status", getattr(response, "code", 502)))
            self.send_response(status)
            for name in (
                "Content-Type", "Content-Length", "Content-Range",
                "Accept-Ranges", "ETag", "Last-Modified", "Cache-Control",
            ):
                value = response.headers.get(name)
                if value:
                    self.send_header(name, value)
            self.send_header("Connection", "close")
            self.end_headers()
            self.close_connection = True
            chunk_size = CHUNK_BYTES if is_stream else 65_536
            while True:
                if is_stream and not self.server.wait_for_transport(stream=True):
                    break
                chunk = response.read(chunk_size)
                if not chunk:
                    break
                self.wfile.write(chunk)
                self.wfile.flush()
                if is_stream:
                    time.sleep(STREAM_CHUNK_DELAY_SECONDS)
        except (BrokenPipeError, ConnectionResetError, OSError):
            # The player can close the old stream when recovery switches sources.
            pass
        except Exception:
            # Never expose untrusted exception strings; a failure before headers
            # is returned as a generic gateway error only.
            try:
                if not self.wfile.closed:
                    self.send_error(502, "Upstream unavailable")
            except Exception:
                pass
        finally:
            if response is not None:
                try:
                    response.close()
                except Exception:
                    pass
            self.close_connection = True


def qualify(upstream, username, password, container, *, query, allow_http,
            proxy_port):
    steps = {
        "authenticated_track": False,
        "initial_qt_playing": False,
        "initial_position_advanced": False,
        "server_pause_applied": False,
        "stream_transport_blocked": False,
        "natural_detection_observed": False,
        "natural_qt_error_observed": False,
        "stall_watchdog_triggered": False,
        "recovery_attempt_dispatched": False,
        "recovery_commit": False,
        "same_track_retained": False,
        "playing_after_recovery": False,
        "position_resumed": False,
        "bounded_state_cleared": False,
        "post_recovery_audio_window": False,
    }
    diagnostics = {}
    app = QApplication.instance() or QApplication([])
    proxy = _ProxyServer(("127.0.0.1", int(proxy_port)), upstream)
    proxy_thread = threading.Thread(target=proxy.serve_forever, daemon=True)
    proxy_thread.start()
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
            "server_url": f"http://127.0.0.1:{int(proxy_port)}",
            "username": username,
            "password": password,
            "allow_insecure_http": bool(allow_http),
        })
        if provider.health_check(timeout=10).get("status") != "ready":
            return steps, diagnostics
        songs = provider.search(query, limit=1)
        if not songs:
            return steps, diagnostics
        steps["authenticated_track"] = True
        track_identity = songs[0].get("track_id")
        player = FlowPlayer(
            provider.resolve,
            playback_refresher=provider.refresh,
            playback_refresh_scheduler=scheduler,
        )
        deck = player.players[player.active]
        qt_errors = []
        deck.errorOccurred.connect(
            lambda error, _message: qt_errors.append(
                str(getattr(error, "name", error)).rsplit(".", 1)[-1]
            )
        )
        player.set_queue(songs[:1], autoplay=True, intent="provider")
        steps["initial_qt_playing"] = _until(
            app, lambda: deck.playbackState() == QMediaPlayer.PlayingState, 18,
        )
        steps["initial_position_advanced"] = _until(
            app, lambda: deck.position() >= 4500, 20,
        )
        if not all((steps["initial_qt_playing"], steps["initial_position_advanced"])):
            return steps, diagnostics
        before = int(deck.position())

        proxy.transport_gate.clear()
        _docker("pause", container)
        server_paused = True
        steps["server_pause_applied"] = True

        # No synthetic QMediaPlayer error is injected. Restore the disposable
        # server after a short real transport outage so a retry can succeed.
        def release_server():
            time.sleep(12.0)
            try:
                _docker("unpause", container)
            except Exception:
                pass
            finally:
                proxy.transport_gate.set()

        release_thread = threading.Thread(target=release_server, daemon=True)
        release_thread.start()

        steps["natural_detection_observed"] = _until(
            app,
            lambda: (
                player.diagnostics_snapshot()["transient_source_errors"] >= 1
                or player.diagnostics_snapshot()["recovery_stall_triggers"] >= 1
            ),
            14,
        )
        snapshot = player.diagnostics_snapshot()
        proxy_metrics = proxy.metrics_snapshot()
        diagnostics["proxy_metrics"] = proxy_metrics
        steps["stream_transport_blocked"] = (
            proxy_metrics["stream_gate_waits"] >= 1
        )
        steps["natural_qt_error_observed"] = (
            snapshot["transient_source_errors"] >= 1 and bool(qt_errors)
        )
        steps["stall_watchdog_triggered"] = snapshot["recovery_stall_triggers"] >= 1
        steps["recovery_attempt_dispatched"] = _until(
            app, lambda: player.diagnostics_snapshot()["recovery_attempts"] >= 1, 8,
        )
        steps["recovery_commit"] = _until(
            app, lambda: player.diagnostics_snapshot()["recovery_successes"] >= 1, 30,
        )
        steps["same_track_retained"] = (
            player.current_track() is not None
            and player.current_track().get("track_id") == track_identity
        )
        steps["playing_after_recovery"] = _until(
            app, lambda: deck.playbackState() == QMediaPlayer.PlayingState, 8,
        )
        steps["position_resumed"] = _until(
            app, lambda: deck.position() >= before + 350, 10,
        )
        resumed_position = int(deck.position())
        steps["post_recovery_audio_window"] = _until(
            app,
            lambda: (
                deck.playbackState() == QMediaPlayer.PlayingState
                and deck.position() >= resumed_position + 3000
            ),
            9,
        )
        snapshot = player.diagnostics_snapshot()
        steps["bounded_state_cleared"] = (
            not player._playback_recovery_pending
            and player._playback_recovery_request is None
            and player._playback_recovery_candidate is None
            and snapshot["recovery_exhausted"] == 0
        )
        safe_metrics = (
            "recovery_attempts", "recovery_successes", "recovery_refresh_failures",
            "recovery_source_rejections", "recovery_submit_rejected",
            "recovery_stale_results", "recovery_exhausted", "recovery_unavailable",
            "recovery_stall_triggers", "recovery_request_timeouts",
            "recovery_load_timeouts", "playback_errors", "active_deck_errors",
            "transient_source_errors", "buffer_stall_events",
            "buffer_stall_status_events", "buffer_stall_no_progress_events",
        )
        diagnostics["metrics"] = {
            key: int(snapshot.get(key, 0)) for key in safe_metrics
        }
        diagnostics["natural_qt_error_count"] = len(qt_errors)
        diagnostics["media_status"] = str(deck.mediaStatus().name)
        diagnostics["playback_state"] = str(deck.playbackState().name)
        diagnostics["position_ms"] = int(deck.position())
        diagnostics["resume_baseline_ms"] = before
        passed = (
            steps["authenticated_track"]
            and steps["initial_qt_playing"]
            and steps["initial_position_advanced"]
            and steps["server_pause_applied"]
            and steps["stream_transport_blocked"]
            and steps["natural_detection_observed"]
            and steps["recovery_attempt_dispatched"]
            and steps["recovery_commit"]
            and steps["same_track_retained"]
            and steps["playing_after_recovery"]
            and steps["position_resumed"]
            and steps["bounded_state_cleared"]
            and steps["post_recovery_audio_window"]
        )
        return {**steps, "passed": bool(passed)}, diagnostics
    finally:
        if release_thread is not None:
            release_thread.join(timeout=12)
        if server_paused:
            try:
                _docker("unpause", container)
            except Exception:
                pass
        proxy.transport_gate.set()
        # Let in-flight provider calls finish after the server has been restored.
        scheduler.shutdown(wait=True)
        if player is not None:
            player.close()
            player.deleteLater()
        provider.close()
        proxy.shutdown()
        proxy.server_close()
        proxy_thread.join(timeout=3)
        app.processEvents()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        app.processEvents()


def main():
    env = os.environ
    upstream = env.get("MELODEX_SUBSONIC_URL", "").strip()
    username = env.get("MELODEX_SUBSONIC_USERNAME", "").strip()
    password = env.get("MELODEX_SUBSONIC_PASSWORD", "")
    container = env.get("MELODEX_SUBSONIC_CONTAINER", "").strip()
    query = env.get("MELODEX_SUBSONIC_QUERY", "R1NaturalOutageSignal")
    allow_http = env.get("MELODEX_SUBSONIC_ALLOW_HTTP", "") == "1"
    proxy_port = int(env.get("MELODEX_NATURAL_PROXY_PORT", "4534"))
    passed = False
    checks = {"disposable_configuration": all(
        (upstream, username, password, container)
    )}
    diagnostics = {}
    if checks["disposable_configuration"]:
        try:
            checks, diagnostics = qualify(
                upstream, username, password, container,
                query=query, allow_http=allow_http,
                proxy_port=proxy_port,
            )
            passed = bool(checks.get("passed"))
        except Exception:
            # The provider/media backend may include auth-token URLs in errors.
            checks["safe_probe_completed"] = False
    print(json.dumps({
        "campaign": "R1-3F",
        "scope": "real Navidrome pause through throttled proxy; no injected Qt error",
        "checks": checks,
        "diagnostics": diagnostics,
        "passed": passed,
        "note": (
            "Controlled transport outage; automatic Qt error detection and/or "
            "stall watchdog is measured separately. The workflow checks the "
            "final three seconds of virtual-sink PCM after recovery, not speakers."
        ),
    }, indent=2, sort_keys=True), flush=True)
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
