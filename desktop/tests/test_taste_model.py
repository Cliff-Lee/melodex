from __future__ import annotations

import json

from melodex.mind import MindEngine
from melodex.taste_model import build_taste_model, score_taste_match
from melodex.user_state import UserState


def _signal(
    artist: str,
    *,
    genre: str = "",
    plays: int = 0,
    completes: int = 0,
    loves: int = 0,
    keeps: int = 0,
    dislikes: int = 0,
    skips: int = 0,
) -> dict:
    track = {
        "artist": artist,
        "genre": genre,
        "title": "Example",
        "local_path": "/private/music/example.flac",
    }
    return {
        "track_key": "test:" + artist.casefold(),
        "track_json": json.dumps(track),
        "artist": artist,
        "plays": plays,
        "completes": completes,
        "loves": loves,
        "keeps": keeps,
        "dislikes": dislikes,
        "skips": skips,
    }


def test_identity_uses_durable_signals_and_does_not_promote_aggregate_skips():
    favorite = _signal(
        "Northbound", genre="Ambient;Downtempo", plays=8, completes=7, loves=1
    )
    skipped = _signal("Quick Exit", genre="Noise", plays=8, skips=8)

    with_skips = build_taste_model([favorite, skipped])
    without_skips = build_taste_model([favorite, dict(skipped, skips=0)])

    assert with_skips.artists["northbound"]["score"] > with_skips.artists["quick exit"]["score"]
    assert with_skips.artists["quick exit"] == without_skips.artists["quick exit"]
    assert with_skips.genres["ambient"]["confidence"] > 0.0


def test_recent_context_and_requested_exploration_stay_separate_from_identity():
    model = build_taste_model(
        [_signal("Long Term Artist", genre="Jazz", loves=1)],
        [
            {"artist": "Today Artist", "genre": "House", "local_path": "/private/today.flac"},
            {"artist": "Today Artist", "genre": "House"},
        ],
        adventure=1.4,
    )

    profile = model.as_dict()
    assert profile["identity"]["artists"][0]["name"] == "Long Term Artist"
    assert profile["context"]["recent_tracks"] == 2
    assert profile["context"]["artists"] == [{"name": "Today Artist", "tracks": 2}]
    assert profile["exploration"] == {"adventure": 1.0, "label": "adventurous"}
    assert "/private/" not in json.dumps(profile)


def test_candidate_match_uses_artist_or_genre_evidence_and_is_neutral_cold_start():
    model = build_taste_model(
        [_signal("Northbound", genre="Ambient", loves=1)]
    )
    artist_score, artist_reason = score_taste_match(
        {"artist": "Northbound", "genre": "Other"}, model
    )
    genre_score, genre_reason = score_taste_match(
        {"artist": "Unknown", "genre": "Ambient"}, model
    )
    cold_score, cold_reason = score_taste_match(
        {"artist": "Unknown", "genre": "Unknown"}, build_taste_model([])
    )

    assert artist_score > 0.0
    assert "Northbound" in artist_reason
    assert genre_score > 0.0
    assert "Ambient" in genre_reason
    assert cold_score == 0.0
    assert cold_reason == ""


def test_recent_session_reactions_are_separate_and_cautiously_affect_candidates():
    now = 1_800_000_000.0
    session_tracks = [
        {
            "artist": "Northbound",
            "genre": "Ambient",
            "local_path": "/private/music/completed.flac",
            "_played_at": now - 60,
            "_completed": True,
        },
        {
            "artist": "Quick Exit",
            "genre": "Noise",
            "_played_at": now - 29,
            "_completed": False,
        },
        {
            "artist": "Now Playing",
            "genre": "House",
            "_played_at": now,
            "_completed": False,
        },
    ]
    model = build_taste_model([], session_tracks=session_tracks, now=now)

    profile = model.as_dict()
    completed_score, completed_reason = score_taste_match(
        {"artist": "Northbound", "genre": "Ambient"}, model
    )
    skipped_score, skipped_reason = score_taste_match(
        {"artist": "Quick Exit", "genre": "Noise"}, model
    )

    assert profile["identity"]["artists"] == []
    assert profile["session_reactions"]["completed_tracks"] == 1
    assert profile["session_reactions"]["quick_skips"] == 1
    assert completed_score > 0.0 > skipped_score
    assert "recent session with Northbound" in completed_reason
    assert "quick skip near Quick Exit" in skipped_reason
    assert "/private/" not in json.dumps(profile)

    expired = build_taste_model(
        [],
        session_tracks=[
            {"artist": "Old Session", "_played_at": now - 15 * 86400, "_completed": True}
        ],
        now=now,
    )
    assert expired.as_dict()["session_reactions"]["completed_tracks"] == 0
    assert score_taste_match({"artist": "Old Session"}, expired)[0] == 0.0


def test_sparse_metadata_stays_neutral_and_cannot_create_a_broad_correction(tmp_path):
    sparse = _signal("", genre="", plays=4, completes=2)
    model = build_taste_model([sparse])
    state = UserState(tmp_path / "sparse.sqlite3")
    try:
        track = {
            "rel": "local:untagged",
            "title": "Untagged recording",
            "local_path": "/private/music/untagged.flac",
        }

        assert model.as_dict()["identity"] == {"artists": [], "genres": []}
        assert score_taste_match(track, model) == (0.0, "")
        assert state.record_taste_correction(track, "more") is False
        assert state.taste_corrections() == []
    finally:
        state.close()


def test_contradictory_artist_evidence_settles_near_neutral():
    model = build_taste_model(
        [
            _signal("Mixed Signals", genre="Ambient", loves=1),
            _signal("Mixed Signals", genre="Ambient", dislikes=1),
        ],
        corrections=[
            {"direction": "more", "artist": "Mixed Signals", "genres": ["Ambient"]},
            {"direction": "less", "artist": "Mixed Signals", "genres": ["Ambient"]},
        ],
    )

    score, reason = score_taste_match(
        {"artist": "Mixed Signals", "genre": "Ambient"}, model
    )

    assert -0.15 < score < 0.15
    assert reason == ""


def test_large_taste_profile_stays_bounded_and_path_free():
    signals = [
        _signal(
            f"Artist {index}",
            genre=f"Genre {index % 50}",
            plays=1 + index % 10,
            completes=index % 4,
        )
        for index in range(1500)
    ]
    recent = [
        {
            "artist": f"Recent {index}",
            "genre": f"Genre {index % 7}",
            "local_path": f"/private/recent/{index}.flac",
        }
        for index in range(50)
    ]

    profile = build_taste_model(
        signals,
        recent,
        adventure=0.9,
    ).as_dict()

    assert len(profile["identity"]["artists"]) <= 8
    assert len(profile["identity"]["genres"]) <= 8
    assert profile["context"]["recent_tracks"] == 20
    assert len(profile["context"]["artists"]) <= 5
    assert len(profile["context"]["genres"]) <= 5
    assert len(profile["session_reactions"]["artists"]) <= 5
    assert profile["exploration"]["adventure"] == 0.9
    assert "/private/" not in json.dumps(profile)


def test_mind_session_scoring_uses_and_explains_the_local_taste_model():
    model = build_taste_model([_signal("Northbound", genre="Ambient", loves=1)])
    mind = MindEngine(None, None)
    matching, matching_reason = mind.score(
        {"artist": "Northbound", "genre": "Ambient"},
        {},
        "balanced",
        0.35,
        1_800_000_000.0,
        {},
        {},
        {},
        model,
    )
    unknown, _ = mind.score(
        {"artist": "Unknown", "genre": "Unknown"},
        {},
        "balanced",
        0.35,
        1_800_000_000.0,
        {},
        {},
        {},
        model,
    )

    assert matching > unknown
    assert "matches your listening history with Northbound" in matching_reason


def test_built_session_attaches_explanation_from_user_state(tmp_path):
    class Flow:
        @staticmethod
        def plan_order(tracks, _path_for, **_kwargs):
            return {
                "tracks": tracks,
                "transitions": [],
                "analysed": 0,
                "metadata_only": len(tracks),
            }

    state = UserState(tmp_path / "taste.sqlite3")
    try:
        old_favorite = {
            "rel": "local:northbound/old",
            "artist": "Northbound",
            "genre": "Ambient",
            "title": "Old",
            "local_path": "/music/old.flac",
        }
        state.record_play(old_favorite)
        state.mark_completed(state.recent_tracks(1)[0]["_history_id"])
        state.record_feedback(old_favorite, True)
        candidate = {
            "rel": "local:northbound/new",
            "artist": "Northbound",
            "genre": "Ambient",
            "title": "New",
            "duration": 240,
            "local_path": "/music/new.flac",
        }

        plan = MindEngine(state, Flow()).build_session(
            [candidate], lambda track: track.get("local_path"), minutes=15
        )

        assert len(plan["tracks"]) == 1
        assert "matches your listening history with Northbound" in plan["tracks"][0]["_mind_reason"]
    finally:
        state.close()


def test_explicit_track_dislike_remains_stronger_than_profile_affinity():
    model = build_taste_model([_signal("Northbound", genre="Ambient", loves=1)])
    track = {"artist": "Northbound", "genre": "Ambient", "rel": "test:disliked"}
    key = UserState.track_key(track)
    score, reason = MindEngine(None, None).score(
        track,
        {key: {"dislikes": 1}},
        "balanced",
        0.35,
        1_800_000_000.0,
        {},
        {},
        {},
        model,
    )

    assert score < -15.0
    assert reason == "previously marked not for me"


def test_explicit_more_and_less_corrections_change_trait_scores_and_reasons():
    more = build_taste_model(
        [],
        corrections=[
            {"direction": "more", "artist": "Northbound", "genres": ["Ambient"]}
        ],
    )
    less = build_taste_model(
        [],
        corrections=[
            {"direction": "less", "artist": "Northbound", "genres": ["Ambient"]}
        ],
    )

    more_score, more_reason = score_taste_match(
        {"artist": "Northbound", "genre": "Ambient"}, more
    )
    less_score, less_reason = score_taste_match(
        {"artist": "Northbound", "genre": "Ambient"}, less
    )

    assert more_score > 0.0 > less_score
    assert "request for more Northbound" in more_reason
    assert "request for less Northbound" in less_reason


def test_taste_correction_is_path_free_reversible_and_idempotent_per_track(tmp_path):
    state = UserState(tmp_path / "taste.sqlite3")
    try:
        track = {
            "rel": "local:northbound/example",
            "title": "Example",
            "artist": "Northbound",
            "genre": "Ambient;Downtempo",
            "local_path": "/private/music/example.flac",
        }

        assert state.record_taste_correction(track, "more") is True
        assert state.record_taste_correction(track, "more") is True
        assert state.taste_correction(track) == "more"
        assert len(state.taste_corrections()) == 1
        correction = state.taste_corrections()[0]
        assert correction == {
            "direction": "more",
            "artist": "Northbound",
            "genres": "Ambient;Downtempo",
        }
        persisted = json.dumps(
            [tuple(row) for row in state._conn.execute("SELECT key,value FROM preferences")]
        )
        assert "/private/" not in persisted

        assert state.record_taste_correction(track, "less") is True
        assert state.taste_correction(track) == "less"
        assert len(state.taste_corrections()) == 1
        assert state.clear_taste_correction(track) is True
        assert state.taste_correction(track) == ""
        assert state.taste_corrections() == []
    finally:
        state.close()


def test_taste_correction_limit_keeps_the_latest_replacement(tmp_path):
    state = UserState(tmp_path / "taste-order.sqlite3")
    try:
        first = {"rel": "local:first", "artist": "First", "genre": "Ambient"}
        second = {"rel": "local:second", "artist": "Second", "genre": "Jazz"}

        state.record_taste_correction(first, "more")
        state.record_taste_correction(second, "less")
        state.record_taste_correction(first, "less")

        assert state.taste_corrections(limit=1) == [
            {"direction": "less", "artist": "First", "genres": "Ambient"}
        ]
    finally:
        state.close()


def test_user_state_profile_is_bounded_path_free_and_local(tmp_path):
    state = UserState(tmp_path / "taste.sqlite3")
    try:
        track = {
            "rel": "local:northbound/example",
            "title": "Example",
            "artist": "Northbound",
            "genre": "Ambient",
            "local_path": "/private/music/example.flac",
        }
        state.record_play(track)
        state.mark_completed(state.recent_tracks(1)[0]["_history_id"])
        state.record_feedback(track, True)

        profile = state.taste_profile(adventure=0.45)

        assert profile["storage"] == "on-device"
        assert profile["identity"]["artists"][0]["name"] == "Northbound"
        assert profile["context"]["recent_tracks"] == 1
        assert profile["session_reactions"]["completed_tracks"] == 1
        assert "/private/" not in json.dumps(profile)
        display = state.taste_display_summary()
        assert "Leans toward: Northbound" in display
        assert "Recent session: 1 completed · 0 quick skips." in display
        assert "stays on this device" in display
    finally:
        state.close()


def test_cold_start_can_build_a_session_without_taste_history(tmp_path):
    class Flow:
        @staticmethod
        def plan_order(tracks, _path_for, **_kwargs):
            return {
                "tracks": tracks,
                "transitions": [],
                "analysed": 0,
                "metadata_only": len(tracks),
            }

    state = UserState(tmp_path / "cold-start.sqlite3")
    try:
        candidate = {
            "rel": "local:first-play",
            "title": "First Play",
            "artist": "Unfamiliar",
            "duration": 210,
            "local_path": "/music/first-play.flac",
        }

        plan = MindEngine(state, Flow()).build_session(
            [candidate], lambda track: track.get("local_path"), minutes=15
        )

        assert len(plan["tracks"]) == 1
        assert plan["tracks"][0]["title"] == "First Play"
        assert "_mind_reason" in plan["tracks"][0]
        assert state.taste_profile()["identity"]["artists"] == []
    finally:
        state.close()
