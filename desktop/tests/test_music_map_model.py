from __future__ import annotations

from melodex.music_map_model import build_music_map


def _profile(
    ref,
    *,
    bpm,
    energy,
    centroid,
    onset,
    key_pc=0,
    key_mode="minor",
    key_conf=0.8,
    plays=0,
    loves=0,
    keeps=0,
    completion=0.0,
    skip=0.0,
    days=None,
):
    return {
        "ref": ref,
        "title": ref,
        "artist": "Artist",
        "album": "Album",
        "duration_ms": 240000,
        "analysis": {
            "bpm": bpm,
            "rhythm_confidence": 0.8,
            "key_pc": key_pc,
            "key_mode": key_mode,
            "key_confidence": key_conf,
            "loudness_db": -11.0,
            "energy": energy,
            "energy_start": max(0.0, energy - 0.1),
            "energy_end": min(1.0, energy + 0.05),
            "spectral_centroid": centroid,
            "onset_density": onset,
            "intro_mixability": 0.65,
            "outro_mixability": 0.7,
            "ending_type": "natural",
        },
        "taste": {
            "plays": plays,
            "completes": round(plays * completion),
            "skips": round(plays * skip),
            "loves": loves,
            "dislikes": 0,
            "keeps": keeps,
            "completion_rate": completion,
            "skip_rate": skip,
            "days_since_last_played": days,
        },
    }


def test_music_map_is_deterministic_and_bounded():
    profiles = [
        _profile("t0", bpm=118, energy=0.62, centroid=1700, onset=0.12, key_pc=0),
        _profile("t1", bpm=121, energy=0.65, centroid=1760, onset=0.13, key_pc=0),
        _profile("t2", bpm=82, energy=0.20, centroid=620, onset=0.03, key_pc=6, key_mode="major"),
        {
            "ref": "t3",
            "title": "Unanalysed",
            "artist": "Artist",
            "album": "",
            "duration_ms": 200000,
            "analysis": None,
            "taste": {},
        },
    ]
    first = build_music_map(profiles, max_nodes=20, neighbours=2)
    second = build_music_map(profiles, max_nodes=20, neighbours=2)

    assert first == second
    assert first["analysed"] == 3
    assert first["input_profiles"] == 4
    assert all(-1.0 <= node["x"] <= 1.0 for node in first["nodes"])
    assert all(-1.0 <= node["y"] <= 1.0 for node in first["nodes"])


def test_music_map_links_close_sonic_neighbours():
    profiles = [
        _profile("t0", bpm=120, energy=0.70, centroid=1800, onset=0.15, key_pc=2),
        _profile("t1", bpm=122, energy=0.68, centroid=1770, onset=0.14, key_pc=2),
        _profile("t2", bpm=78, energy=0.14, centroid=450, onset=0.01, key_pc=8, key_mode="major"),
        _profile("t3", bpm=155, energy=0.90, centroid=3600, onset=0.28, key_pc=5),
    ]
    result = build_music_map(profiles, neighbours=1)
    pairs = {frozenset((edge["a"], edge["b"])) for edge in result["edges"]}
    assert frozenset(("t0", "t1")) in pairs


def test_music_map_surfaces_rediscovery_strength():
    profiles = [
        _profile(
            "loved-old",
            bpm=110,
            energy=0.55,
            centroid=1400,
            onset=0.10,
            plays=10,
            loves=1,
            keeps=2,
            completion=0.9,
            days=75,
        ),
        _profile(
            "recent",
            bpm=111,
            energy=0.56,
            centroid=1420,
            onset=0.10,
            plays=10,
            loves=1,
            keeps=2,
            completion=0.9,
            days=1,
        ),
    ]
    result = build_music_map(profiles)
    nodes = {node["ref"]: node for node in result["nodes"]}
    assert nodes["loved-old"]["taste"] > 0.5
    assert nodes["loved-old"]["rediscovery"] > nodes["recent"]["rediscovery"]
    assert nodes["recent"]["rediscovery"] == 0.0


def test_music_map_large_library_selection_is_deterministic():
    profiles = [
        _profile(
            f"t{i}",
            bpm=80 + (i % 90),
            energy=(i % 20) / 20,
            centroid=600 + (i % 50) * 60,
            onset=(i % 15) / 60,
            key_pc=i % 12,
            plays=i % 7,
            loves=1 if i % 31 == 0 else 0,
            keeps=1 if i % 19 == 0 else 0,
            completion=0.8 if i % 5 else 0.4,
            days=10 + (i % 180),
        )
        for i in range(120)
    ]
    first = build_music_map(profiles, max_nodes=40)
    second = build_music_map(profiles, max_nodes=40)
    assert len(first["nodes"]) == 40
    assert [node["ref"] for node in first["nodes"]] == [
        node["ref"] for node in second["nodes"]
    ]
