from __future__ import annotations

from types import SimpleNamespace

from melodex.provider_manager import ProviderManager


class FakeProvider:
    def __init__(self, name: str, rows=None, error: Exception | None = None):
        self.info = SimpleNamespace(name=name, capabilities=["search"])
        self._rows = list(rows or [])
        self._error = error

    def search(self, query: str, limit: int = 50):
        if self._error is not None:
            raise self._error
        return list(self._rows)[:limit]


def _manager(providers: dict[str, FakeProvider]) -> ProviderManager:
    manager = ProviderManager.__new__(ProviderManager)
    manager.providers = dict(providers)
    manager.provider_order = lambda: list(providers)
    return manager


def test_search_report_returns_partial_results_when_one_source_fails():
    manager = _manager(
        {
            "good": FakeProvider(
                "Good Source",
                [{"title": "Monkey", "artist": "Example", "provider_id": "good"}],
            ),
            "bad": FakeProvider(
                "Broken Source",
                error=RuntimeError(
                    "<urlopen error [SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed>"
                ),
            ),
        }
    )

    report = manager.search_report("monkey", "all", 50)

    assert [item["title"] for item in report["items"]] == ["Monkey"]
    assert report["searched"] == 2
    assert report["available"] == 1
    assert report["failures"][0]["name"] == "Broken Source"
    assert report["failures"][0]["reason"] == "Secure connection failed"


def test_selected_source_failure_is_reported_instead_of_raised():
    manager = _manager(
        {
            "archive": FakeProvider(
                "Internet Archive Audio",
                error=RuntimeError("Provider Internet Archive Audio timed out"),
            )
        }
    )

    report = manager.search_report("jazz", "archive", 25)

    assert report["items"] == []
    assert report["searched"] == 1
    assert report["available"] == 0
    assert report["failures"][0]["reason"] == "Timed out"


def test_search_compatibility_method_still_returns_track_list():
    manager = _manager(
        {
            "one": FakeProvider(
                "One",
                [{"title": "A", "artist": "Artist"}],
            ),
            "two": FakeProvider(
                "Two",
                [{"title": "B", "artist": "Artist"}],
            ),
        }
    )

    assert [row["title"] for row in manager.search("x", "all", 10)] == ["A", "B"]
