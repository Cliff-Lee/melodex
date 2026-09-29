from __future__ import annotations

from pathlib import Path

from melodex.music_knowledge import MusicKnowledgeStore, build_knowledge_graph


def _track(name: str, artist: str = "Artist", album: str = "Album"):
    return {
        "provider_id": "local",
        "track_id": f"/music/{name}.flac",
        "rel": f"local:/music/{name}.flac",
        "local_path": f"/music/{name}.flac",
        "title": name,
        "artist": artist,
        "album": album,
    }


def test_knowledge_store_merges_partial_updates(tmp_path: Path):
    store = MusicKnowledgeStore(tmp_path / "knowledge.sqlite3")
    track = _track("One")
    try:
        first = store.remember(
            track,
            identity={
                "recording_mbid": "rec-1",
                "artist_mbid": "artist-1",
                "artist": "Artist",
                "title": "One",
            },
        )
        assert first["identity"]["recording_mbid"] == "rec-1"

        second = store.remember(
            track,
            credits=[
                {
                    "kind": "artist",
                    "role": "producer",
                    "name": "Producer",
                    "mbid": "person-1",
                }
            ],
        )
        assert second["identity"]["artist_mbid"] == "artist-1"
        assert second["credits"][0]["name"] == "Producer"
        assert store.count() == 1
    finally:
        store.close()


def test_knowledge_snapshot_surfaces_tagged_musicbrainz_ids(tmp_path: Path):
    store = MusicKnowledgeStore(tmp_path / "knowledge.sqlite3")
    track = _track("Tagged")
    track["musicbrainz_recording_id"] = "rec-tagged"
    track["musicbrainz_artist_id"] = "artist-tagged"
    try:
        snapshot = store.snapshot({"t0": track})
        assert snapshot["t0"]["identity"]["recording_mbid"] == "rec-tagged"
        assert snapshot["t0"]["identity"]["artist_mbid"] == "artist-tagged"
        assert store.count() == 0  # snapshot itself does not persist anything
    finally:
        store.close()


def test_knowledge_graph_builds_distinct_connection_families():
    ref_map = {
        "t0": _track("A1", "Artist A", "Album A"),
        "t1": _track("A2", "Artist A", "Album A"),
        "t2": _track("B1", "Artist B", "Album B"),
    }
    knowledge = {
        "t0": {
            "identity": {
                "recording_mbid": "rec-a1",
                "artist_mbid": "artist-a",
                "artist": "Artist A",
            },
            "artist": {
                "related": [
                    {"id": "artist-b", "name": "Artist B", "type": "collaboration"}
                ]
            },
            "credits": [
                {
                    "kind": "artist",
                    "role": "producer",
                    "name": "Producer P",
                    "mbid": "producer-p",
                },
                {
                    "kind": "artist",
                    "role": "guitar",
                    "name": "Player X",
                    "mbid": "player-x",
                },
                {
                    "kind": "artist",
                    "role": "composer",
                    "name": "Writer W",
                    "mbid": "writer-w",
                },
                {
                    "kind": "work",
                    "role": "performance",
                    "name": "Shared Work",
                    "mbid": "work-1",
                },
            ],
            "context": [
                {
                    "id": "song-connections",
                    "title": "Song Connections",
                    "items": [
                        {
                            "title": "B1",
                            "relation": "samples",
                            "canonical_ids": {
                                "musicbrainz_recording_id": "rec-b1"
                            },
                        }
                    ],
                },
                {
                    "id": "recording-places",
                    "title": "Where It Was Recorded",
                    "items": [{"title": "Studio Z"}],
                },
            ],
        },
        "t1": {
            "identity": {
                "recording_mbid": "rec-a2",
                "artist_mbid": "artist-a",
                "artist": "Artist A",
            },
            "credits": [
                {
                    "kind": "artist",
                    "role": "producer",
                    "name": "Producer P",
                    "mbid": "producer-p",
                },
                {
                    "kind": "artist",
                    "role": "guitar",
                    "name": "Player X",
                    "mbid": "player-x",
                },
                {
                    "kind": "artist",
                    "role": "composer",
                    "name": "Writer W",
                    "mbid": "writer-w",
                },
                {
                    "kind": "work",
                    "role": "performance",
                    "name": "Shared Work",
                    "mbid": "work-1",
                },
            ],
            "context": [
                {
                    "id": "recording-places",
                    "title": "Where It Was Recorded",
                    "items": [{"title": "Studio Z"}],
                }
            ],
        },
        "t2": {
            "identity": {
                "recording_mbid": "rec-b1",
                "artist_mbid": "artist-b",
                "artist": "Artist B",
            },
            "credits": [],
            "context": [],
        },
    }

    graph = build_knowledge_graph(ref_map, knowledge)
    kinds = {edge["kind"] for edge in graph["edges"]}

    assert {
        "artist",
        "album",
        "production",
        "performer",
        "composition_credit",
        "work",
        "song_relation",
        "artist_relation",
        "place",
    }.issubset(kinds)

    song = next(edge for edge in graph["edges"] if edge["kind"] == "song_relation")
    assert {song["a"], song["b"]} == {"t0", "t2"}
    assert song["label"] == "samples"

    producer = next(edge for edge in graph["edges"] if edge["kind"] == "production")
    assert "Producer P" in producer["label"]

    performer = next(edge for edge in graph["edges"] if edge["kind"] == "performer")
    assert "Player X" in performer["label"]

    work = next(edge for edge in graph["edges"] if edge["kind"] == "work")
    assert work["label"] == "Shared Work"

    place = next(edge for edge in graph["edges"] if edge["kind"] == "place")
    assert "Studio Z" in place["label"]


def test_same_artist_falls_back_to_local_metadata_without_mbid():
    ref_map = {
        "t0": _track("One", "Local Artist", "First"),
        "t1": _track("Two", "Local Artist", "Second"),
    }
    graph = build_knowledge_graph(ref_map, {})
    artist_edges = [edge for edge in graph["edges"] if edge["kind"] == "artist"]
    assert len(artist_edges) == 1
    assert artist_edges[0]["evidence"] == "local artist metadata"
