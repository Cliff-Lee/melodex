from __future__ import annotations

import time
from pathlib import Path

import melodex.providers.local_files as local_files
from melodex.providers.local_files import LocalFilesProvider
from melodex.storage_concurrency import StorageConcurrencyController


def _track(path: Path) -> dict[str, object]:
    return {
        "provider_id": "local",
        "track_id": str(path),
        "rel": f"local:{path}",
        "title": path.stem,
        "artist": "Adaptive Artist",
        "album": "Adaptive Album",
        "duration": 180.0,
        "local_path": str(path),
        "source": "local",
    }


def test_storage_controller_starts_conservative_and_scales_fast_local():
    controller = StorageConcurrencyController([Path("/music")])

    assert controller.decision().metadata_workers == 2
    assert controller.decision().profile == "warming"

    for _ in range(32):
        controller.observe_stat(0.0005)

    decision = controller.decision()
    assert decision.metadata_workers == 8
    assert decision.profile == "low-latency"
    assert decision.in_flight_limit == 8


def test_storage_controller_keeps_high_latency_storage_conservative():
    controller = StorageConcurrencyController([Path("/music")])

    for _ in range(32):
        controller.observe_stat(0.015)

    decision = controller.decision()
    assert decision.metadata_workers == 2
    assert decision.profile == "high-latency"
    assert decision.in_flight_limit == 4


def test_storage_controller_network_hint_caps_default_concurrency():
    controller = StorageConcurrencyController([Path("/Volumes/NAS/Music")])

    decision = controller.decision()
    assert decision.network_hint is True
    assert decision.metadata_workers == 2
    assert decision.profile == "network-conservative"

    for _ in range(32):
        controller.observe_stat(0.0005)

    fast = controller.decision()
    assert fast.metadata_workers == 4
    assert fast.profile == "network-fast"
    assert fast.in_flight_limit == 8


def test_p10g_parallel_metadata_preserves_discovery_order(
    monkeypatch,
    tmp_path: Path,
):
    root = tmp_path / "music"
    root.mkdir()
    names = ["01.flac", "02.flac", "03.flac", "04.flac"]
    for name in names:
        (root / name).write_bytes(b"x")

    monkeypatch.setattr(
        local_files.os,
        "walk",
        lambda _root, onerror=None: [(str(root), [], names)],
    )

    delays = {
        "01.flac": 0.04,
        "02.flac": 0.001,
        "03.flac": 0.001,
        "04.flac": 0.001,
    }

    def metadata(path: Path):
        time.sleep(delays[path.name])
        return _track(path)

    monkeypatch.setattr(LocalFilesProvider, "_metadata", staticmethod(metadata))

    provider = LocalFilesProvider(scan_on_init=False)
    snapshot = provider.scan_snapshot([root])

    assert [Path(row["local_path"]).name for row in snapshot["tracks"]] == names
    metrics = snapshot["metrics"]
    assert 2 <= int(metrics["metadata_worker_limit"]) <= 4
    assert int(metrics["metadata_max_in_flight"]) >= 2


def test_p10g_unchanged_rescan_does_not_spawn_metadata_work(
    monkeypatch,
    tmp_path: Path,
):
    root = tmp_path / "music"
    root.mkdir()
    paths = [root / f"{index:02d}.flac" for index in range(3)]
    for path in paths:
        path.write_bytes(b"x")

    monkeypatch.setattr(
        LocalFilesProvider,
        "_metadata",
        staticmethod(_track),
    )
    provider = LocalFilesProvider(scan_on_init=False)
    first = provider.scan_snapshot([root])
    cache = {
        provider._override_key(record["track"]["local_path"]): {
            "track": record["track"],
            "size": record["size"],
            "mtime_ns": record["mtime_ns"],
        }
        for record in first["index_records"]
    }

    def must_not_read(path: Path):
        raise AssertionError(f"unchanged metadata reopened: {path}")

    monkeypatch.setattr(
        LocalFilesProvider,
        "_metadata",
        staticmethod(must_not_read),
    )
    second = provider.scan_snapshot([root], cached_entries=cache)

    assert second["changes"]["metadata_reads"] == 0
    assert second["metrics"]["metadata_max_in_flight"] == 0


def test_p14l_fast_local_cold_import_can_use_full_bounded_metadata_budget(
    monkeypatch,
    tmp_path: Path,
):
    root = tmp_path / "music"
    root.mkdir()
    paths = [root / f"{index:02d}.flac" for index in range(32)]
    for path in paths:
        path.write_bytes(b"x")

    active = 0
    peak = 0
    lock = __import__("threading").Lock()

    def metadata(path: Path):
        nonlocal active, peak
        with lock:
            active += 1
            peak = max(peak, active)
        try:
            time.sleep(0.03)
            return _track(path)
        finally:
            with lock:
                active -= 1

    monkeypatch.setattr(LocalFilesProvider, "_metadata", staticmethod(metadata))

    provider = LocalFilesProvider(scan_on_init=False)
    snapshot = provider.scan_snapshot([root])
    metrics = snapshot["metrics"]

    assert int(metrics["metadata_worker_limit"]) == 8
    assert int(metrics["metadata_in_flight_limit"]) == 8
    assert 5 <= int(metrics["metadata_max_in_flight"]) <= 8
    assert 5 <= peak <= 8
