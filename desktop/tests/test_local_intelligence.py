from __future__ import annotations

import json
from pathlib import Path

from melodex.flow import TrackAnalysis
from melodex.local_intelligence import LocalIntelligenceService
from melodex.user_state import UserState


class FakeFlow:
    def cached_analysis_for(self, path):
        return TrackAnalysis(
            path=str(path),
            duration=240.0,
            bpm=121.5,
            rhythm_confidence=0.8,
            key_pc=2,
            key_mode="minor",
            key_confidence=0.7,
            loudness_db=-11.0,
            energy=0.62,
            energy_start=0.4,
            energy_end=0.7,
            spectral_centroid=1750.0,
            onset_density=0.14,
            intro_mixability=0.66,
            outro_mixability=0.71,
            ending_type="natural",
        )

    def analysis_for(self, path):
        return self.cached_analysis_for(path)


class CaptureBroker:
    def __init__(self):
        self.received = None

    def suggest_library(
        self,
        tracks,
        intent,
        seed_refs=None,
        limit=12,
        adventure=0.35,
    ):
        self.received = {
            "tracks": tracks,
            "intent": intent,
            "seed_refs": list(seed_refs or []),
            "limit": limit,
            "adventure": adventure,
        }
        ref = tracks[1]["ref"] if len(tracks) > 1 else tracks[0]["ref"]
        return {
            "suggestions": [
                {
                    "ref": ref,
                    "score": 0.88,
                    "reason": "local test",
                    "badges": ["private"],
                    "_extension_id": "org.example.local",
                }
            ],
            "errors": [],
        }


def _track(path: str, title: str):
    return {
        "provider_id": "local",
        "track_id": path,
        "rel": "local:" + path,
        "local_path": path,
        "title": title,
        "artist": "Artist",
        "album": "Album",
        "duration": 240.0,
    }


def test_local_intelligence_snapshot_redacts_paths_and_absolute_history(tmp_path: Path):
    state = UserState(tmp_path / "taste.sqlite3")
    broker = CaptureBroker()
    service = LocalIntelligenceService(state, FakeFlow(), broker)
    try:
        first = _track("/private/Music/Secret One.flac", "Secret One")
        second = _track("/private/Music/Secret Two.flac", "Secret Two")
        state.record_play(first)
        state.record_feedback(first, True)
        profiles, seed_refs, ref_map, analysed = service.build_snapshot(
            [first, second], [first]
        )

        assert analysed == 2
        assert seed_refs == ["t0"]
        assert ref_map["t0"]["local_path"] == "/private/Music/Secret One.flac"

        wire = json.dumps(profiles)
        assert "/private/Music" not in wire
        assert "local_path" not in wire
        assert "provider_id" not in wire
        assert "track_id" not in wire
        assert '"rel"' not in wire
        assert "played_at" not in wire

        first_profile = profiles[0]
        assert set(first_profile) == {
            "ref", "title", "artist", "album", "duration_ms", "analysis", "taste"
        }
        assert "path" not in (first_profile["analysis"] or {})
        assert "last_played" not in first_profile["taste"]
        assert "days_since_last_played" in first_profile["taste"]
    finally:
        state.close()


def test_local_intelligence_maps_ephemeral_refs_back_inside_core(tmp_path: Path):
    state = UserState(tmp_path / "taste.sqlite3")
    broker = CaptureBroker()
    service = LocalIntelligenceService(state, FakeFlow(), broker)
    try:
        first = _track("/music/one.flac", "One")
        second = _track("/music/two.flac", "Two")
        result = service.suggest("similar", [first, second], [first], limit=5)

        assert broker.received is not None
        assert broker.received["seed_refs"] == ["t0"]
        assert result["tracks"][0]["title"] == "Two"
        assert result["tracks"][0]["local_path"] == "/music/two.flac"
        assert result["tracks"][0]["_intelligence_reason"] == "local test"
        assert result["tracks"][0]["_intelligence_extension_id"] == "org.example.local"

        wire = json.dumps(broker.received["tracks"])
        assert "/music/" not in wire
    finally:
        state.close()
