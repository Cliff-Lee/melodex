import json

from melodex.user_state import UserState


def _stored_json(state: UserState, table: str) -> str:
    row = state._conn.execute(f"SELECT * FROM {table} LIMIT 1").fetchone()
    assert row is not None
    return " ".join(str(value) for value in row)


def test_checkpoint_persists_provider_identity_and_position_without_source_secrets(tmp_path):
    state = UserState(tmp_path / "state.sqlite")
    try:
        state.save_playback_checkpoint(
            {
                "provider_id": "bridge",
                "track_id": "track-17",
                "artist": "Portishead",
                "title": "Roads",
                "album": "Dummy",
                "duration": 300.0,
                "local_path": "https://source.invalid/local?token=path-secret",
                "stream_url": "https://stream.invalid/audio?token=short-lived",
                "url": "https://stream.invalid/audio?token=short-lived",
                "headers": {"Authorization": "Bearer private"},
                "cookies": {"session": "private"},
                "expires_at": "2099-01-01T00:00:00Z",
            },
            42850,
        )
        checkpoint = state.playback_checkpoint()
        assert checkpoint is not None
        assert checkpoint["position_ms"] == 42850
        assert checkpoint["track"] == {
            "provider_id": "bridge",
            "track_id": "track-17",
            "title": "Roads",
            "artist": "Portishead",
            "album": "Dummy",
            "duration": 300.0,
        }
        raw = _stored_json(state, "playback_checkpoint")
        for secret in ("stream_url", "short-lived", "Authorization", "private", "expires_at"):
            assert secret not in raw
    finally:
        state.close()


def test_queue_keeps_stable_local_and_provider_entries_and_current_index(tmp_path):
    state = UserState(tmp_path / "state.sqlite")
    try:
        state.save_playback_queue(
            [
                {
                    "provider_id": "local",
                    "track_id": "local-1",
                    "local_path": "/music/first.flac",
                    "title": "First",
                    "url": "file:///music/first.flac",
                },
                {
                    "provider_id": "bridge-a",
                    "track_id": "same-id",
                    "title": "Second",
                    "stream_url": "https://stream.invalid/a?token=one",
                    "headers": {"Authorization": "Bearer one"},
                },
                {"title": "Unresolvable without a stable identity", "stream_url": "https://expired.invalid/x"},
                {
                    "provider_id": "bridge-b",
                    "track_id": "same-id",
                    "title": "Fourth",
                    "stream_url": "https://stream.invalid/b?token=two",
                    "cookies": {"session": "two"},
                },
            ],
            3,
        )
        saved = state.playback_queue()
        assert saved is not None
        assert saved["queue_index"] == 2
        assert [track.get("provider_id") for track in saved["tracks"]] == [
            "local", "bridge-a", "bridge-b"
        ]
        assert UserState.playback_identity(saved["tracks"][2]) == 'provider:["bridge-b","same-id"]'
        raw = _stored_json(state, "playback_queue")
        for secret in ("stream_url", "expired.invalid", "Authorization", "cookies", "token=one", "token=two"):
            assert secret not in raw
    finally:
        state.close()


def test_history_and_moments_do_not_retain_transient_source_fields(tmp_path):
    state = UserState(tmp_path / "state.sqlite")
    try:
        track = {
            "provider_id": "bridge",
            "track_id": "track-9",
            "artist": "Massive Attack",
            "title": "Teardrop",
            "stream_url": "https://stream.invalid/track?token=private",
            "headers": {"Authorization": "Bearer private"},
        }
        state.record_play(track)
        state.save_moment(track, 15000, "favorite section")
        recent = state.recent_tracks(1)
        moment = state.moments(1)[0]
        assert recent[0]["track_id"] == "track-9"
        assert moment["track"]["provider_id"] == "bridge"
        for table in ("listening_history", "track_signals", "moments"):
            raw = _stored_json(state, table)
            assert "stream_url" not in raw
            assert "token=private" not in raw
            assert "Authorization" not in raw
    finally:
        state.close()


def test_playback_identity_distinguishes_same_track_id_across_providers():
    bridge_a = {"provider_id": "bridge-a", "track_id": "42", "title": "Same"}
    bridge_b = {"provider_id": "bridge-b", "track_id": "42", "title": "Same"}
    assert UserState.playback_identity(bridge_a) != UserState.playback_identity(bridge_b)
    assert not UserState.same_playback_track(bridge_a, bridge_b)
    assert UserState.same_playback_track(bridge_a, dict(bridge_a, stream_url="https://temp.invalid"))


def test_legacy_checkpoint_and_history_are_scrubbed_on_read(tmp_path):
    state = UserState(tmp_path / "state.sqlite")
    legacy_track = {
        "provider_id": "bridge",
        "track_id": "legacy-1",
        "artist": "A",
        "title": "B",
        "stream_url": "https://expired.invalid/track?token=legacy-secret",
        "headers": {"Authorization": "Bearer legacy-secret"},
    }
    try:
        with state._lock, state._conn:
            state._conn.execute(
                "INSERT INTO playback_checkpoint(id,track_json,position_ms,updated_at) VALUES(1,?,?,?)",
                (json.dumps(legacy_track), 27000, 1.0),
            )
            state._conn.execute(
                "INSERT INTO listening_history(rel,track_json,played_at,completed) VALUES('',?,?,0)",
                (json.dumps(legacy_track), 1.0),
            )

        assert state.playback_checkpoint()["track"]["track_id"] == "legacy-1"
        assert state.recent_tracks(1)[0]["track_id"] == "legacy-1"
        for table in ("playback_checkpoint", "listening_history"):
            raw = _stored_json(state, table)
            assert "stream_url" not in raw
            assert "legacy-secret" not in raw
            assert "Authorization" not in raw
    finally:
        state.close()
