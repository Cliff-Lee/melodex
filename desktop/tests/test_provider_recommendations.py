from __future__ import annotations

from dataclasses import dataclass

from melodex.provider_manager import ProviderManager


@dataclass
class Info:
    id: str
    capabilities: list[str]


class FakeProvider:
    def __init__(self, pid: str, capabilities: list[str]):
        self.info = Info(pid, capabilities)
        self.search_calls = 0
        self.recommend_calls = 0

    def search(self, query: str, limit: int = 50):
        self.search_calls += 1
        return [
            {
                "provider_id": self.info.id,
                "track_id": "search-1",
                "artist": "Search Artist",
                "title": query,
            }
        ]

    def recommend(self, seed, limit: int = 25):
        self.recommend_calls += 1
        return [
            {
                "provider_id": self.info.id,
                "track_id": "rec-1",
                "artist": "Recommended Artist",
                "title": "Recommended Song",
                "metadata": {"playable": False},
            }
        ]


def _manager():
    manager = ProviderManager.__new__(ProviderManager)
    manager.providers = {
        "search": FakeProvider("search", ["search"]),
        "recommend": FakeProvider("recommend", ["recommendations"]),
    }
    manager.provider_order = lambda: ["search", "recommend"]
    return manager


def test_global_search_skips_recommendation_only_provider():
    manager = _manager()
    rows = manager.search("Needle", "all", 20)
    assert rows[0]["provider_id"] == "search"
    assert manager.providers["search"].search_calls == 1
    assert manager.providers["recommend"].search_calls == 0


def test_recommendations_only_call_declared_providers():
    manager = _manager()
    rows = manager.recommend(
        {"artist": "Massive Attack", "title": "Teardrop"},
        "all",
        20,
    )
    assert rows[0]["provider_id"] == "recommend"
    assert manager.providers["recommend"].recommend_calls == 1
    assert manager.providers["search"].recommend_calls == 0


def test_specific_provider_without_capability_returns_empty():
    manager = _manager()
    assert manager.recommend(
        {"artist": "A", "title": "B"},
        "search",
        10,
    ) == []
