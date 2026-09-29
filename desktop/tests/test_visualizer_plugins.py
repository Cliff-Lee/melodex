import json
from pathlib import Path

import pytest

from melodex.visualizer_plugins import (
    MAX_PLUGIN_BYTES,
    installed_visualizers,
    install_visualizer_file,
    load_visualizer,
    parse_visualizer,
)


def _recipe(**changes):
    payload = {
        "format": "mdxviz",
        "api_version": 1,
        "manifest": {
            "id": "org.example.orbit-garden",
            "name": "Orbit Garden",
            "author": "Example",
            "description": "A small palette-driven world.",
        },
        "scene": {"layers": [
            {"type": "rings", "count": 3, "gain": 0.18, "feature": "energy", "palette": 0, "speed": 0.05},
            {"type": "orbit", "count": 12, "gain": 0.3, "feature": "rhythm", "palette": 1, "speed": 0.08},
        ]},
    }
    payload.update(changes)
    return payload


def test_parse_visualizer_validates_and_normalizes_recipe():
    result = parse_visualizer(json.dumps(_recipe()))

    assert result.id == "org.example.orbit-garden"
    assert result.name == "Orbit Garden"
    assert result.layers[0] == {
        "type": "rings", "count": 3, "gain": 0.18,
        "feature": "energy", "palette": 0, "speed": 0.05,
    }


def test_documented_example_is_a_valid_installable_recipe():
    path = Path(__file__).resolve().parents[2] / "docs" / "visualizers" / "examples" / "orbit-garden.mdxviz"
    recipe = load_visualizer(path)
    assert recipe.id == "org.melodex.example.orbit-garden"
    assert len(recipe.layers) == 4


@pytest.mark.parametrize("change", [
    {"format": "executable"},
    {"script": "print('hello')"},
    {"manifest": {"id": "../../oops", "name": "Bad", "author": "", "description": ""}},
    {"scene": {"layers": [{"type": "web", "url": "https://example.com"}]}},
    {"scene": {"layers": [{"type": ["rings"]}]}},
    {"scene": {"layers": [{"type": "rings", "feature": []}]}},
    {"scene": {"layers": [{"type": "rings", "count": 999}]}},
    {"scene": {"layers": [{"type": "rings", "gain": 0.9}]}},
])
def test_parse_visualizer_rejects_unknown_code_and_unbounded_fields(change):
    with pytest.raises(ValueError):
        parse_visualizer(json.dumps(_recipe(**change)))


def test_parse_visualizer_rejects_oversized_and_non_utf8_files():
    with pytest.raises(ValueError, match="64 KiB"):
        parse_visualizer(b" " * (MAX_PLUGIN_BYTES + 1))
    with pytest.raises(ValueError, match="UTF-8"):
        parse_visualizer(b"\xff")


def test_install_and_discover_visualizer_are_atomic_and_conflict_safe(tmp_path):
    source = tmp_path / "orbit.mdxviz"
    source.write_text(json.dumps(_recipe()), encoding="utf-8")
    destination = tmp_path / "installed"

    recipe, installed = install_visualizer_file(source, destination)
    assert installed.name == "org.example.orbit-garden.mdxviz"
    assert recipe.name == "Orbit Garden"
    assert installed_visualizers(destination) == ((recipe, installed),)
    with pytest.raises(FileExistsError):
        install_visualizer_file(source, destination)


def test_installed_visualizer_scan_ignores_invalid_files(tmp_path):
    (tmp_path / "broken.mdxviz").write_text("{}", encoding="utf-8")
    assert installed_visualizers(tmp_path) == ()
