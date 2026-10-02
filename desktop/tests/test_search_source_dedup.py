from __future__ import annotations

from types import SimpleNamespace

from melodex.provider_manager import ProviderManager


class FakeProvider:
    def __init__(self, name: str, capabilities=None):
        self.info = SimpleNamespace(
            name=name,
            capabilities=list(capabilities or ["search"]),
        )

    def search(self, query: str, limit: int = 50):
        return [{"title": self.info.name, "provider_id": self.info.name}]


def _manager(order):
    manager = ProviderManager.__new__(ProviderManager)
    manager.providers = {
        "local": FakeProvider("This computer"),
        "org.melodex.radiobrowser": FakeProvider("Radio Browser"),
        "org.melodex.example.radio-browser": FakeProvider("Radio Browser Example"),
        "org.melodex.librivox": FakeProvider("LibriVox"),
        "org.melodex.example.librivox": FakeProvider("LibriVox Example"),
        "org.melodex.example.openverse-audio": FakeProvider("Openverse Audio Example"),
    }
    manager.provider_order = lambda: list(order)
    return manager


def test_searchable_provider_ids_hide_shadowed_examples():
    manager = _manager(
        [
            "local",
            "org.melodex.radiobrowser",
            "org.melodex.example.radio-browser",
            "org.melodex.librivox",
            "org.melodex.example.librivox",
            "org.melodex.example.openverse-audio",
        ]
    )

    assert manager.searchable_provider_ids() == [
        "local",
        "org.melodex.radiobrowser",
        "org.melodex.librivox",
        "org.melodex.example.openverse-audio",
    ]


def test_example_is_visible_when_production_equivalent_is_not_installed():
    manager = _manager(["org.melodex.example.radio-browser"])
    manager.providers.pop("org.melodex.radiobrowser")

    assert manager.searchable_provider_ids() == [
        "org.melodex.example.radio-browser"
    ]


def test_all_sources_search_does_not_query_shadowed_example():
    manager = _manager(
        [
            "org.melodex.radiobrowser",
            "org.melodex.example.radio-browser",
        ]
    )

    report = manager.search_report("jazz", "all", 20)

    assert report["provider_ids"] == ["org.melodex.radiobrowser"]
    assert len(report["items"]) == 1
