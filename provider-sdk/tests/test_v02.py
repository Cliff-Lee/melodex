from pathlib import Path

from melodex_provider_sdk import PlaybackResource, first_of, opaque_id
from melodex_provider_sdk.cli import main


def test_playback_resource_v02_fields():
    resource = PlaybackResource(
        kind="http",
        url="https://example.invalid/a.mp3",
        headers={"Referer": "https://example.invalid/item"},
        cookies={"session": "abc"},
        refresh_token="r1",
    )
    data = resource.to_dict()
    assert data["cookies"]["session"] == "abc"
    assert data["refresh_token"] == "r1"


def test_web_normalization_helpers():
    data = {"track": {"name": "Example"}, "title": "Fallback"}
    assert first_of(data, ["missing", "track.name", "title"]) == "Example"
    assert opaque_id("a", 1) == opaque_id("a", 1)
    assert opaque_id("a", 1) != opaque_id("a", 2)


def test_doctor_generated_provider(tmp_path: Path):
    root = tmp_path / "provider"
    assert main(["init", str(root), "--id", "org.example.doctor"]) == 0
    assert main(["doctor", str(root), "--query", "anything"]) == 0
