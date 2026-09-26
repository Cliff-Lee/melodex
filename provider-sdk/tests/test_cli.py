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
    assert main(["validate", str(provider), "--schema", str(SCHEMA)]) == 0

    output = tmp_path / "test.mdxprovider"
    assert main(["pack", str(provider), "-o", str(output), "--schema", str(SCHEMA)]) == 0
    with zipfile.ZipFile(output) as archive:
        names = set(archive.namelist())
    assert "manifest.json" in names
    assert "README.md" in names
    assert "LICENSE" in names
