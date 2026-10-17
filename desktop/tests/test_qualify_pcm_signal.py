"""Audio null-sink energy validator and failure contracts."""
from __future__ import annotations

import importlib.util
from pathlib import Path
from array import array


def _module():
    path = Path(__file__).resolve().parents[1] / "tools" / "qualify_pcm_signal.py"
    spec = importlib.util.spec_from_file_location("qualify_pcm_signal", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_reject_empty_and_silent_pcm(tmp_path):
    module = _module()
    empty = tmp_path / "empty.pcm"
    empty.write_bytes(b"")
    assert module.inspect(empty)["passed"] is False
    silent = tmp_path / "silent.pcm"
    silent.write_bytes(b"\0" * (44100 * 2 * 2))
    assert module.inspect(silent)["passed"] is False


def test_accept_non_silent_pcm_without_using_song_metadata(tmp_path):
    module = _module()
    pcm = tmp_path / "signal.pcm"
    wave = array("h", [1000, -1000] * 44100)
    pcm.write_bytes(wave.tobytes())
    report = module.inspect(pcm)
    assert report["passed"] is True
    assert report["peak_pcm16"] == 1000
    assert report["rms_pcm16"] >= 999
    assert not any(x in report for x in ("track_title", "stream_url", "token"))
