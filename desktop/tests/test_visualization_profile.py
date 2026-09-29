from __future__ import annotations

import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "melodex"))

from visualization_profile import build_visual_profile, energy_at


def test_visual_fingerprint_is_stable_and_does_not_depend_on_file_path():
    first = {"artist": "Demo Artist", "title": "Blue Room", "duration": 240.0, "local_path": "/one/a.flac"}
    second = {"artist": " demo artist ", "title": "BLUE ROOM", "duration": 241.2, "local_path": "/two/b.flac"}
    assert build_visual_profile(first).fingerprint == build_visual_profile(second).fingerprint


def test_cached_flow_shapes_profile_and_journey_contour():
    track = {"artist": "Demo Artist", "title": "Blue Room", "duration": 240}
    analysis = {
        "bpm": 120,
        "energy": 0.65,
        "spectral_centroid": 1850,
        "onset_density": 0.12,
        "energy_curve": [0.0, 0.4, 0.8, 1.0],
    }
    profile = build_visual_profile(track, analysis)
    assert profile.flow_available
    assert profile.energy_curve == (0.0, 0.4, 0.8, 1.0)
    assert profile.bpm == 120
    assert profile.energy == 0.65
    assert energy_at(profile, 0) == 0.0
    assert math.isclose(energy_at(profile, 0.5), 0.6)
    assert energy_at(profile, 1) == 1.0


def test_missing_or_malformed_analysis_falls_back_safely():
    track = {"artist": "Demo Artist", "title": "Blue Room"}
    profile = build_visual_profile(track, {"bpm": float("nan"), "energy_curve": [0.2, "bad", float("inf")]})
    assert not profile.flow_available
    assert profile.energy_curve == ()
    assert 40 <= profile.bpm <= 220
    assert 0 <= profile.energy <= 1
    assert 0 <= energy_at(profile, 0.7) <= 1


def test_distinct_tracks_get_distinct_repeatable_worlds():
    first = build_visual_profile({"artist": "A", "title": "One", "duration": 180})
    second = build_visual_profile({"artist": "B", "title": "Two", "duration": 180})
    assert first.fingerprint != second.fingerprint
    assert first.seed != second.seed
