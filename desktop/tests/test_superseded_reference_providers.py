from __future__ import annotations

import json
from pathlib import Path

from melodex.provider_manager import ProviderManager


def _write_reference_provider(data_dir: Path, plugin_id: str, name: str) -> None:
    folder = data_dir / "providers" / plugin_id
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "manifest.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "id": plugin_id,
                "name": name,
                "version": "0.1.1",
                "protocol_version": "1.0",
                "capabilities": ["search", "track", "playback"],
                "permissions": {"network_hosts": []},
                "entrypoints": {"python": "provider.py"},
            }
        ),
        "utf-8",
    )
    (folder / "provider.py").write_text(
        "raise RuntimeError('superseded reference provider should never start')\n",
        "utf-8",
    )


def test_bundled_sources_hide_superseded_reference_duplicates(tmp_path: Path):
    data_dir = tmp_path / "data"
    _write_reference_provider(
        data_dir,
        "org.melodex.example.radio-browser",
        "Radio Browser Example",
    )
    _write_reference_provider(
        data_dir,
        "org.melodex.example.librivox",
        "LibriVox Example",
    )
    (data_dir / "sources.json").write_text(
        json.dumps(
            {
                "provider_priority": [
                    "org.melodex.example.radio-browser",
                    "org.melodex.radiobrowser",
                    "org.melodex.example.librivox",
                    "org.melodex.librivox",
                ]
            }
        ),
        "utf-8",
    )

    manager = ProviderManager(data_dir)
    try:
        assert "org.melodex.radiobrowser" in manager.providers
        assert "org.melodex.librivox" in manager.providers
        assert "org.melodex.example.radio-browser" not in manager.providers
        assert "org.melodex.example.librivox" not in manager.providers

        hidden = {
            row["id"]: row["replacement_id"]
            for row in manager.quarantined_superseded_providers()
        }
        assert hidden == {
            "org.melodex.example.radio-browser": "org.melodex.radiobrowser",
            "org.melodex.example.librivox": "org.melodex.librivox",
        }

        assert "org.melodex.example.radio-browser" not in manager.provider_order()
        assert "org.melodex.example.librivox" not in manager.provider_order()
        assert "org.melodex.example.radio-browser" not in manager.settings.get(
            "provider_priority", []
        )
        assert "org.melodex.example.librivox" not in manager.settings.get(
            "provider_priority", []
        )
    finally:
        manager.close()
