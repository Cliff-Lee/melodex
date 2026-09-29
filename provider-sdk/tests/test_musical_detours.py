from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "examples" / "ecosystem" / "musical_detours" / "plugin.py"
FIXTURE = ROOT / "examples" / "ecosystem" / "musical_detours" / "fixtures" / "request.json"


def _load():
    spec = importlib.util.spec_from_file_location("musical_detours_example", PLUGIN)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_musical_detours_fixture_finds_real_contrast_and_varied_anchors():
    module = _load()
    params = json.loads(FIXTURE.read_text("utf-8"))
    result = module.suggest(params)
    rows = result["suggestions"]

    assert result["intent"] == "detour"
    assert [row["ref"] for row in rows] == ["t1", "t2"]
    assert rows[0]["reason"] == "Shares the pulse; moves away from energy and tone colour."
    assert rows[0]["badges"] == ["shared pulse", "new energy", "new tone"]
    assert "shared energy" in rows[1]["badges"]
    assert all("score" in row and 0 <= row["score"] <= 1 for row in rows)


def test_musical_detours_is_deterministic_and_rejects_other_intents():
    module = _load()
    params = json.loads(FIXTURE.read_text("utf-8"))

    assert module.suggest(params) == module.suggest(params)
    result = module.suggest({**params, "intent": "similar"})
    assert result["suggestions"] == []


def test_musical_detours_preserves_explicit_zero_adventure():
    module = _load()
    params = json.loads(FIXTURE.read_text("utf-8"))
    result = module.suggest({**params, "adventure": 0.0})
    assert result["suggestions"][0]["ref"] == "t1"
