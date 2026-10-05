from __future__ import annotations

import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

try:
    from PySide6.QtGui import QColor, QImage
except ImportError as exc:  # pragma: no cover - runner capability guard
    pytest.skip(f"Qt desktop runtime is unavailable: {exc}", allow_module_level=True)

from melodex.artwork_image_cache import ArtworkImageCache, shared_artwork_image_cache


def _write_image(path, width=640, height=360, colour="#225588"):
    image = QImage(width, height, QImage.Format_ARGB32)
    image.fill(QColor(colour))
    assert image.save(str(path))
    return path


def test_prepared_artwork_is_square_cached_and_reused(tmp_path):
    path = _write_image(tmp_path / "wide.png")
    cache = ArtworkImageCache(budget_bytes=2 * 1024 * 1024)

    first = cache.prepare(str(path), 160)
    second = cache.prepare(str(path), 160)

    assert not first.isNull()
    assert first.width() == first.height() == 160
    assert not second.isNull()
    snapshot = cache.snapshot()
    assert snapshot["decoded_images"] == 1
    assert snapshot["misses"] == 1
    assert snapshot["hits"] == 1
    assert snapshot["entries"] == 1


def test_nonblocking_peek_reuses_prepared_image_without_storage_access(tmp_path):
    path = _write_image(tmp_path / "peek.png")
    cache = ArtworkImageCache()
    assert cache.peek(str(path), 160).isNull()

    prepared = cache.prepare(str(path), 160)
    assert not prepared.isNull()

    path.unlink()
    cached = cache.peek(str(path), 160)
    assert not cached.isNull()
    assert cached.width() == cached.height() == 160
    assert cache.snapshot()["peek_hits"] == 1


def test_concurrent_requests_decode_once(tmp_path):
    path = _write_image(tmp_path / "dedupe.png")
    cache = ArtworkImageCache(wait_timeout_seconds=2.0)
    original = cache._decode_square
    entered = threading.Event()
    release = threading.Event()
    calls = []

    def slow_decode(source, size):
        calls.append((source, size))
        entered.set()
        assert release.wait(1.5)
        return original(source, size)

    cache._decode_square = slow_decode

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(cache.prepare, str(path), 164)
        assert entered.wait(1.0)
        second = pool.submit(cache.prepare, str(path), 164)
        deadline = time.monotonic() + 1.0
        while (
            cache.snapshot()["deduplicated_waits"] < 1
            and time.monotonic() < deadline
        ):
            time.sleep(0.01)
        release.set()
        one = first.result(timeout=2)
        two = second.result(timeout=2)

    assert not one.isNull()
    assert not two.isNull()
    assert len(calls) == 1
    snapshot = cache.snapshot()
    assert snapshot["decoded_images"] == 1
    assert snapshot["deduplicated_waits"] == 1


def test_missing_artwork_uses_negative_cache(tmp_path):
    path = tmp_path / "missing.png"
    cache = ArtworkImageCache(negative_ttl_seconds=60)

    assert cache.prepare(str(path), 160).isNull()
    assert cache.prepare(str(path), 160).isNull()

    snapshot = cache.snapshot()
    assert snapshot["misses"] == 1
    assert snapshot["decode_failures"] == 1
    assert snapshot["negative_hits"] == 1
    assert snapshot["negative_entries"] == 1


def test_lru_budget_evicts_old_prepared_images(tmp_path):
    cache = ArtworkImageCache(budget_bytes=150_000)
    paths = [
        _write_image(tmp_path / f"{index}.png", colour=f"#{index+2:02x}5588")
        for index in range(3)
    ]

    for path in paths:
        image = cache.prepare(str(path), 160)
        assert not image.isNull()

    snapshot = cache.snapshot()
    assert snapshot["evictions"] >= 1
    assert snapshot["entries"] <= 2
    assert snapshot["bytes"] <= snapshot["budget_bytes"]


def test_cover_label_uses_shared_prepared_image_before_legacy_decode(tmp_path):
    try:
        from PySide6.QtWidgets import QApplication
        from melodex.ux_components import CoverLabel
    except ImportError as exc:
        pytest.skip(f"Qt widgets runtime is unavailable: {exc}")

    app = QApplication.instance() or QApplication([])
    path = _write_image(tmp_path / "label.png")
    cache = shared_artwork_image_cache()
    cache.prepare(str(path), 160)
    before = cache.snapshot()["peek_hits"]

    label = CoverLabel(160)
    label.set_cover(str(path), title="Album", key="album")
    app.processEvents()

    assert label.pixmap() is not None
    assert not label.pixmap().isNull()
    assert cache.snapshot()["peek_hits"] == before + 1

    label.deleteLater()
    app.processEvents()
