"""R1-3B optional OpenSubsonic MPP contract: no external network required."""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "bundled_provider_sources" / "opensubsonic_personal"
SPEC = importlib.util.spec_from_file_location("melodex_test_opensubsonic", SOURCE / "provider.py")
assert SPEC and SPEC.loader
provider = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(provider)


def _params(server="https://music.example", username="tester", password="secret"):
    return {"_melodex_config": {
        "server_url": server, "username": username, "password": password,
    }}


def test_optional_source_has_provider_sdk_prerequisites_and_is_not_bundled():
    manifest = json.loads((SOURCE / "manifest.json").read_text("utf-8"))
    assert manifest["id"] == provider.PROVIDER_ID
    assert "secret" == next(item["type"] for item in manifest["configuration"]
                            if item["key"] == "password")
    assert set(("README.md", "SOURCE_POLICY.md", "LICENSE", "provider.py")).issubset(
        {path.name for path in SOURCE.iterdir()}
    )
    assert not (ROOT / "melodex" / "bundled_providers" /
                "opensubsonic_personal.mdxprovider").exists()


def test_provider_info_does_not_need_credentials_or_network():
    info = provider.respond({"method": "provider.info", "params": {}})
    assert info["id"] == provider.PROVIDER_ID
    assert set(info["capabilities"]) == {"search", "track", "playback"}


@pytest.mark.parametrize("server", [
    "http://music.example", "file:///music", "https://u:p@music.example",
    "https://music.example/?t=secret", "https://music.example/#fragment",
])
def test_unsafe_url_configurations_fail_without_leaking_credentials(server):
    with pytest.raises(provider.ProviderError) as err:
        provider._config(_params(server=server))
    assert "secret" not in str(err.value)


def test_track_identity_is_scoped_to_server_and_account():
    cfg_a = provider._config(_params())
    cfg_b = provider._config(_params(username="second"))
    cfg_c = provider._config(_params(password="rotated"))
    first = provider._track_id("123", cfg_a)
    assert first == provider._track_id("123", cfg_c)
    assert first != provider._track_id("123", cfg_b)
    with pytest.raises(provider.ProviderError):
        provider._native_id(first, cfg_b)


def test_authenticated_playback_has_no_password_and_fresh_salts():
    params = _params()
    track_id = provider._track_id("123", provider._config(params))
    request = {"method": "playback.resolve", "params": {
        **params, "provider_track_id": track_id,
    }}
    a = provider.respond(request)
    b = provider.respond(request)
    assert a["kind"] == "http" and a["seekable"] is True
    assert a["url"] != b["url"]
    assert "secret" not in a["url"]
    assert a["url"].startswith("https://music.example/rest/stream.view?")
    assert a["cache_policy"] == "session"


def test_malformed_server_error_code_is_not_in_provider_exception():
    cfg = provider._config(_params())
    class FakeReply:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return None
        def read(self, _limit):
            return json.dumps({"subsonic-response": {
                "status": "failed", "error": {
                    "code": "LEAK-my-secret-token", "message": "sensitive",
                },
            }}).encode()
    with patch.object(provider._OPENER, "open", return_value=FakeReply()):
        with pytest.raises(provider.ProviderError) as err:
            provider._request_json("ping", cfg)
    assert "LEAK" not in str(err.value)
    assert "sensitive" not in str(err.value)
    assert "unknown" in str(err.value)


def test_json_rpc_subprocess_responds_with_clean_stdout():
    proc = subprocess.run(
        [sys.executable, str(SOURCE / "provider.py")],
        input=json.dumps({"jsonrpc": "2.0", "id": 101, "method": "provider.info", "params": {}}) + "\n",
        capture_output=True, text=True, timeout=5, check=True,
    )
    lines = proc.stdout.splitlines()
    assert len(lines) == 1
    result = json.loads(lines[0])
    assert result["id"] == 101
    assert result["result"]["id"] == provider.PROVIDER_ID
