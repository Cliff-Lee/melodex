from __future__ import annotations

import json
import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SDK = ROOT / "provider-sdk"


def fail(errors: list[str]) -> int:
    if errors:
        print("Ecosystem consistency check failed:")
        for error in errors:
            print(f"  - {error}")
        return 1
    print("Ecosystem consistency check passed")
    return 0


def main() -> int:
    errors: list[str] = []

    pyproject = tomllib.loads((SDK / "pyproject.toml").read_text("utf-8"))
    version = str(pyproject["project"]["version"])

    init_text = (SDK / "src/melodex_provider_sdk/__init__.py").read_text("utf-8")
    match = re.search(r'__version__\s*=\s*"([^"]+)"', init_text)
    init_version = match.group(1) if match else ""
    if init_version != version:
        errors.append(
            f"provider-sdk __version__ {init_version!r} != pyproject version {version!r}"
        )

    for relative in (
        "src/melodex_provider_sdk/cli.py",
        "src/melodex_provider_sdk/extension_cli.py",
        "src/melodex_provider_sdk/registry_cli.py",
    ):
        text = (SDK / relative).read_text("utf-8")
        if f"%(prog)s {version}" not in text:
            errors.append(f"{relative} does not expose CLI version {version}")

    registry = json.loads((SDK / "registry/registry.json").read_text("utf-8"))
    example = json.loads((SDK / "registry/example-registry.json").read_text("utf-8"))

    for entry in list(registry.get("plugins") or []):
        if not isinstance(entry, dict):
            continue
        if str(entry.get("kind") or "") != "enrichment":
            continue
        minimum = str((entry.get("compatibility") or {}).get("melodex_min") or "")
        parts = tuple(int(x) for x in re.findall(r"\d+", minimum)[:3]) if minimum else (0,)
        parts = parts + (0,) * (3 - len(parts))
        if parts < (0, 3, 0):
            errors.append(
                f"enrichment registry entry {entry.get('id')!r} must require Melodex 0.3.0 or newer"
            )
    if registry != example:
        errors.append(
            "registry/example-registry.json no longer mirrors canonical registry.json"
        )

    required_docs = (
        ROOT / "docs/DEVELOPER_QUICKSTART.md",
        ROOT / "docs/developers/00_STATUS_AND_STABILITY.md",
        ROOT / "docs/developers/01_ECOSYSTEM_ARCHITECTURE.md",
        ROOT / "docs/developers/02_DOCUMENTATION_POLICY.md",
        ROOT / "docs/developers/07_PERMISSIONS_SECURITY.md",
        ROOT / "docs/RELEASES_AND_MAIN.md",
        ROOT / "docs/PLUGIN_DIRECTORY.md",
    )
    for path in required_docs:
        if not path.is_file():
            errors.append(f"required developer/trust documentation missing: {path.relative_to(ROOT)}")

    readme = (ROOT / "README.md").read_text("utf-8")
    for required_link in (
        "docs/DEVELOPER_QUICKSTART.md",
        "docs/developers/00_STATUS_AND_STABILITY.md",
        "docs/developers/01_ECOSYSTEM_ARCHITECTURE.md",
        "docs/RELEASES_AND_MAIN.md",
    ):
        if required_link not in readme:
            errors.append(f"README does not surface {required_link}")

    openai_text = (ROOT / "desktop/melodex/openai_tools.py").read_text("utf-8")
    mcp_text = (ROOT / "desktop/melodex/mcp_server.py").read_text("utf-8")
    openai_names = set(re.findall(r'"name": "(melodex_[a-z_]+)"', openai_text))
    mcp_names = set(re.findall(r'@mcp\.tool\(name="(melodex_[a-z_]+)"', mcp_text))
    if openai_names != mcp_names:
        errors.append(
            "MCP/OpenAI high-level tool names differ: "
            f"OpenAI-only={sorted(openai_names - mcp_names)}, "
            f"MCP-only={sorted(mcp_names - openai_names)}"
        )

    start_here = (ROOT / "docs/START_HERE.md").read_text("utf-8")
    for phrase in ("Sources", "Add local folder…", "Play for me", "Build this journey"):
        if phrase not in start_here:
            errors.append(f"Start Here is missing current UI phrase: {phrase}")

    privacy = (ROOT / "docs/PRIVACY.md").read_text("utf-8")
    if "SQLite preferences database" not in privacy:
        errors.append("Privacy documentation no longer discloses current LLM API-key storage")

    return fail(errors)


if __name__ == "__main__":
    sys.exit(main())
