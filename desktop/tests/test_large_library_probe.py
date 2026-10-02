from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from large_library_probe import (  # noqa: E402
    DEFAULT_PROFILES,
    expected_shape,
    profile_model,
    synthetic_catalog,
)


def test_large_library_profiles_cover_real_and_stress_scales():
    assert DEFAULT_PROFILES == (1_000, 12_700, 50_000, 100_000)


def test_synthetic_12700_track_catalog_has_predictable_shape():
    shape = expected_shape(12_700, tracks_per_album=10, albums_per_artist=4)
    assert shape == {
        "tracks": 12_700,
        "albums": 1_270,
        "artists": 318,
    }

    catalog = synthetic_catalog(
        12_700,
        tracks_per_album=10,
        albums_per_artist=4,
    )
    assert len(catalog) == 12_700
    assert catalog[0]["album"] == "Album 000000"
    assert catalog[-1]["album"] == "Album 001269"


def test_12700_track_album_model_retains_entire_realistic_library():
    metrics, _catalog = profile_model(
        12_700,
        tracks_per_album=10,
        albums_per_artist=4,
        model_limit=4_000,
    )

    assert metrics["expected_album_count"] == 1_270
    assert metrics["input_album_count"] == 1_270
    assert metrics["modeled_album_count"] == 1_270
    assert metrics["albums_truncated"] == 0
    assert metrics["tracks_truncated"] == 0
    assert metrics["retained_track_count"] == 12_700
    assert metrics["retained_track_ratio"] == 1.0


def test_probe_exposes_album_model_truncation_instead_of_hiding_it():
    # Use one track per album to cross the current 4,000-album My Music limit
    # without constructing a needlessly huge test fixture.
    metrics, _catalog = profile_model(
        5_001,
        tracks_per_album=1,
        albums_per_artist=4,
        model_limit=4_000,
    )

    assert metrics["input_album_count"] == 5_001
    assert metrics["modeled_album_count"] == 4_000
    assert metrics["albums_truncated"] == 1_001
    assert metrics["tracks_truncated"] == 1_001
    assert metrics["retained_track_ratio"] < 1.0


def test_100k_shape_is_available_without_real_files():
    shape = expected_shape(
        100_000,
        tracks_per_album=10,
        albums_per_artist=4,
    )
    assert shape["albums"] == 10_000
    assert shape["artists"] == 2_500
