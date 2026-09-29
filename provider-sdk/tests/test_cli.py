import json
import zipfile
from pathlib import Path

from melodex_provider_sdk.cli import main

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "spec" / "provider_manifest.schema.json"


def test_cli_init_validate_pack(tmp_path):
    provider = tmp_path / "provider"
    assert main(["init", str(provider), "--id", "org.example.test", "--name", "Test Provider"]) == 0
    manifest = json.loads((provider / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["id"] == "org.example.test"
    assert (provider / "SOURCE_POLICY.md").is_file()
    assert "# Test Provider" in (provider / "README.md").read_text(encoding="utf-8")
    assert main(["validate", str(provider), "--schema", str(SCHEMA)]) == 0
    assert main(["doctor", str(provider), "--schema", str(SCHEMA)]) == 0

    output = tmp_path / "test.mdxprovider"
    assert main(["pack", str(provider), "-o", str(output), "--schema", str(SCHEMA)]) == 0
    with zipfile.ZipFile(output) as archive:
        names = set(archive.namelist())
    assert "manifest.json" in names
    assert "README.md" in names
    assert "SOURCE_POLICY.md" in names
    assert "LICENSE" in names


def test_doctor_accepts_recommendation_only_provider(tmp_path):
    provider = tmp_path / "recommend-provider"
    provider.mkdir()
    manifest = {
        "schema_version": 1,
        "id": "org.example.recommend",
        "name": "Recommend Only",
        "version": "0.1.0",
        "publisher": "Example",
        "protocol_version": "1.0",
        "description": "Recommendation-only test provider.",
        "capabilities": ["recommendations"],
        "permissions": {
            "network_hosts": [],
            "offline_downloads": False,
            "local_files": False,
            "browser_auth": False,
            "lan_discovery": False,
        },
        "entrypoints": {"python": "provider.py"},
    }
    (provider / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    (provider / "README.md").write_text("# Recommend Only\n", encoding="utf-8")
    (provider / "SOURCE_POLICY.md").write_text("# Source Policy\n", encoding="utf-8")
    (provider / "LICENSE").write_text("test\n", encoding="utf-8")
    (provider / "provider.py").write_text(
        """import json, sys
for line in sys.stdin:
    req = json.loads(line)
    if req.get("method") == "provider.info":
        result = {"id":"org.example.recommend","name":"Recommend Only","version":"0.1.0","protocol_version":"1.0","capabilities":["recommendations"]}
    elif req.get("method") == "provider.health":
        result = {"status":"auth_required","message":"Configure API key"}
    else:
        raise RuntimeError("doctor should not call this method")
    print(json.dumps({"jsonrpc":"2.0","id":req["id"],"result":result}), flush=True)
""",
        encoding="utf-8",
    )
    assert main(["doctor", str(provider), "--schema", str(SCHEMA)]) == 0
