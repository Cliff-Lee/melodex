from __future__ import annotations

import math
import os
import threading
import time
from collections import OrderedDict
from typing import Any

def _qt_image_api():
    """Import QtGui only when image work is actually requested.

    Metadata-only and provider tests run on Linux runners without libEGL. Keeping
    QtGui out of module import lets those non-visual paths use RichMetadataService
    without pulling a graphical runtime into process startup.
    """
    from PySide6.QtCore import QSize, Qt
    from PySide6.QtGui import QImage, QImageReader

    return QSize, Qt, QImage, QImageReader


class ArtworkImageCache:
    """Thread-safe decoded artwork cache for UI-sized square images.

    The cache deliberately stores QImage rather than QPixmap so decode/resize/crop
    can happen on background workers. UI code only converts the prepared image to
    QPixmap on the Qt thread.
    """

    def __init__(
        self,
        *,
        budget_bytes: int = 64 * 1024 * 1024,
        negative_ttl_seconds: float = 30.0,
        wait_timeout_seconds: float = 5.0,
    ) -> None:
        self.budget_bytes = max(64 * 1024, int(budget_bytes))
        self.negative_ttl_seconds = max(1.0, float(negative_ttl_seconds))
        self.wait_timeout_seconds = max(0.25, float(wait_timeout_seconds))
        self._lock = threading.RLock()
        self._cache: OrderedDict[tuple[str, int, int, int], tuple[Any, int]] = (
            OrderedDict()
        )
        self._latest: dict[tuple[str, int], tuple[str, int, int, int]] = {}
        self._negative: dict[tuple[str, int], float] = {}
        self._inflight: dict[tuple[str, int, int, int], threading.Event] = {}
        self._bytes = 0
        self._metrics = {
            "requests": 0,
            "hits": 0,
            "peek_hits": 0,
            "misses": 0,
            "negative_hits": 0,
            "decode_failures": 0,
            "deduplicated_waits": 0,
            "deduplicated_timeouts": 0,
            "evictions": 0,
            "decoded_images": 0,
        }

    @staticmethod
    def _base_key(path: str, size: int) -> tuple[str, int]:
        expanded = os.path.expanduser(str(path or "").strip())
        return os.path.abspath(expanded), max(1, int(size))

    def peek(self, path: str, size: int):
        """Return a prepared image already in memory without touching storage."""
        _, _, QImage, _ = _qt_image_api()
        base = self._base_key(path, size)
        with self._lock:
            key = self._latest.get(base)
            cached = self._cache.get(key) if key is not None else None
            if cached is None:
                return QImage()
            self._cache.move_to_end(key)
            self._metrics["peek_hits"] += 1
            return QImage(cached[0])

    def prepare(self, path: str, size: int):
        """Return a square prepared QImage, or a null image on failure."""
        _, _, QImage, _ = _qt_image_api()
        base = self._base_key(path, size)
        with self._lock:
            self._metrics["requests"] += 1
            expiry = self._negative.get(base)
            if expiry is not None:
                if expiry > time.monotonic():
                    self._metrics["negative_hits"] += 1
                    return QImage()
                self._negative.pop(base, None)

        try:
            stat = os.stat(base[0])
        except OSError:
            with self._lock:
                self._remember_negative_locked(base)
                self._metrics["misses"] += 1
                self._metrics["decode_failures"] += 1
            return QImage()

        key = (base[0], base[1], int(stat.st_mtime_ns), int(stat.st_size))
        with self._lock:
            cached = self._cache.get(key)
            if cached is not None:
                self._cache.move_to_end(key)
                self._metrics["hits"] += 1
                return QImage(cached[0])

            event = self._inflight.get(key)
            if event is not None:
                self._metrics["deduplicated_waits"] += 1
                waiter = True
            else:
                event = threading.Event()
                self._inflight[key] = event
                self._metrics["misses"] += 1
                waiter = False

        if waiter:
            if not event.wait(self.wait_timeout_seconds):
                with self._lock:
                    self._metrics["deduplicated_timeouts"] += 1
                return QImage()
            with self._lock:
                cached = self._cache.get(key)
                if cached is not None:
                    self._cache.move_to_end(key)
                    self._metrics["hits"] += 1
                    return QImage(cached[0])
                if self._negative.get(base, 0.0) > time.monotonic():
                    self._metrics["negative_hits"] += 1
                return QImage()

        image = self._decode_square(base[0], base[1])
        with self._lock:
            try:
                if image.isNull():
                    self._remember_negative_locked(base)
                    self._metrics["decode_failures"] += 1
                else:
                    self._insert_locked(base, key, image)
                    self._metrics["decoded_images"] += 1
            finally:
                done = self._inflight.pop(key, None)
                if done is not None:
                    done.set()
        return QImage(image)

    def _decode_square(self, path: str, size: int):
        QSize, Qt, QImage, QImageReader = _qt_image_api()
        reader = QImageReader(path)
        reader.setAutoTransform(True)
        source_size = reader.size()
        if source_size.isValid() and source_size.width() > 0 and source_size.height() > 0:
            scale = max(
                float(size) / float(source_size.width()),
                float(size) / float(source_size.height()),
            )
            reader.setScaledSize(
                QSize(
                    max(size, int(math.ceil(source_size.width() * scale))),
                    max(size, int(math.ceil(source_size.height() * scale))),
                )
            )
        image = reader.read()
        if image.isNull():
            return QImage()
        if image.width() < size or image.height() < size:
            image = image.scaled(
                size,
                size,
                Qt.KeepAspectRatioByExpanding,
                Qt.SmoothTransformation,
            )
        left = max(0, (image.width() - size) // 2)
        top = max(0, (image.height() - size) // 2)
        return image.copy(left, top, size, size)

    def _remember_negative_locked(self, base: tuple[str, int]) -> None:
        self._negative[base] = time.monotonic() + self.negative_ttl_seconds

    def _insert_locked(
        self,
        base: tuple[str, int],
        key: tuple[str, int, int, int],
        image: Any,
    ) -> None:
        _, _, QImage, _ = _qt_image_api()
        previous_key = self._latest.get(base)
        if previous_key is not None and previous_key != key:
            previous = self._cache.pop(previous_key, None)
            if previous is not None:
                self._bytes -= previous[1]
        size_bytes = max(0, int(image.sizeInBytes()))
        self._cache[key] = (QImage(image), size_bytes)
        self._cache.move_to_end(key)
        self._latest[base] = key
        self._negative.pop(base, None)
        self._bytes += size_bytes
        self._evict_locked()

    def _evict_locked(self) -> None:
        while self._bytes > self.budget_bytes and len(self._cache) > 1:
            key, (_image, size_bytes) = self._cache.popitem(last=False)
            self._bytes -= size_bytes
            base = (key[0], key[1])
            if self._latest.get(base) == key:
                self._latest.pop(base, None)
            self._metrics["evictions"] += 1

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()
            self._latest.clear()
            self._negative.clear()
            self._bytes = 0

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                **dict(self._metrics),
                "entries": len(self._cache),
                "negative_entries": len(self._negative),
                "inflight": len(self._inflight),
                "bytes": int(self._bytes),
                "budget_bytes": int(self.budget_bytes),
            }


_SHARED_ARTWORK_IMAGE_CACHE = ArtworkImageCache()


def shared_artwork_image_cache() -> ArtworkImageCache:
    return _SHARED_ARTWORK_IMAGE_CACHE


__all__ = ["ArtworkImageCache", "shared_artwork_image_cache"]
