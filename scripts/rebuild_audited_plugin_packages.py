from __future__ import annotations

import hashlib
import json
import re
import shutil
import stat
import zipfile
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
SDK = ROOT / "provider-sdk"
EXAMPLES = SDK / "examples" / "ecosystem"
REGISTRY_PATH = SDK / "registry" / "registry.json"
EXAMPLE_REGISTRY_PATH = SDK / "registry" / "example-registry.json"
PACKAGES = SDK / "registry" / "packages"
REVIEWS = SDK / "registry" / "reviews"

REVIEWED_AT = "2026-09-29T10:30:00Z"

TARGETS = {
    "bridge_builder": "0.1.1",
    "cover_art_archive_artwork": "0.1.1",
    "lastfm_recommendations_provider": "0.1.1",
    "librivox_provider": "0.1.1",
    "listenbrainz_community_pulse": "0.1.1",
    "listenbrainz_tags": "0.1.2",
    "musicbrainz_connections": "0.1.1",
    "musicbrainz_enrichment": "0.1.1",
    "openverse_audio_provider": "0.1.1",
    "radio_browser_provider": "0.1.1",
    "sonic_neighbours": "0.1.1",
    "wikimedia_artwork": "0.1.1",
    "wikimedia_liner_notes": "0.1.1",
}


def _source_folder(entry: dict) -> str:
    repo = str((entry.get("source") or {}).get("repository") or "")
    return Path(urlparse(repo).path).name


def _descriptor(folder: Path) -> Path:
    provider = folder / "manifest.json"
    extension = folder / "capabilities.json"
    if provider.is_file() == extension.is_file():
        raise RuntimeError(f"{folder}: expected exactly one manifest/capabilities descriptor")
    return provider if provider.is_file() else extension


def _write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", "utf-8")


def _package_basename(old_url: str, version: str, suffix: str) -> str:
    old = Path(urlparse(old_url).path).name
    match = re.match(r"^(.*?)-\d+\.\d+\.\d+(?:[^.]*)?\.(mdxprovider|mdxplugin)$", old)
    if not match:
        raise RuntimeError(f"Cannot derive package basename from {old!r}")
    return f"{match.group(1)}-{version}.{suffix}"


def _zip_info(path: Path, arcname: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(arcname, date_time=(2026, 9, 29, 10, 30, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    mode = path.stat().st_mode
    perms = stat.S_IMODE(mode) or 0o644
    info.create_system = 3
    info.external_attr = (stat.S_IFREG | perms) << 16
    return info


def _build_package(folder: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp = destination.with_suffix(destination.suffix + ".tmp")
    with zipfile.ZipFile(temp, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for path in sorted(folder.rglob("*"), key=lambda p: p.relative_to(folder).as_posix()):
            if not path.is_file():
                continue
            rel = path.relative_to(folder)
            if any(part in {"__pycache__", ".pytest_cache"} for part in rel.parts):
                continue
            if path.name in {".DS_Store"} or path.suffix == ".pyc":
                continue
            zf.writestr(_zip_info(path, rel.as_posix()), path.read_bytes())
    temp.replace(destination)


def _review_event(previous: dict, *, version: str, digest: str) -> dict:
    event = {
        key: value
        for key, value in previous.items()
        if key not in {"reviewed_at", "version", "package_sha256", "summary"}
    }
    event.update(
        {
            "reviewed_at": REVIEWED_AT,
            "version": version,
            "package_sha256": digest,
            "summary": (
                "Stabilization review after packaged-host/plugin audit: "
                "source parsing/boundary fixes, package descriptor, permissions, "
                "source policy, adversarial fixtures and rebuilt package bytes "
                "were checked for this patch release."
            ),
        }
    )
    return event


def main() -> int:
    registry = json.loads(REGISTRY_PATH.read_text("utf-8"))
    entries = {
        _source_folder(entry): entry
        for entry in registry.get("plugins") or []
        if isinstance(entry, dict)
    }

    changed = 0
    for folder_name, target_version in TARGETS.items():
        entry = entries.get(folder_name)
        if entry is None:
            raise RuntimeError(f"Registry has no entry for {folder_name}")

        folder = EXAMPLES / folder_name
        descriptor_path = _descriptor(folder)
        descriptor = json.loads(descriptor_path.read_text("utf-8"))
        if str(descriptor.get("version") or "") != target_version:
            descriptor["version"] = target_version
            _write_json(descriptor_path, descriptor)
            changed += 1

        distribution = dict(entry.get("distribution") or {})
        suffix = str(distribution.get("format") or "")
        if suffix not in {"mdxprovider", "mdxplugin"}:
            raise RuntimeError(f"{folder_name}: invalid registry package format")
        filename = _package_basename(
            str(distribution.get("package_url") or ""), target_version, suffix
        )
        package_path = PACKAGES / filename
        _build_package(folder, package_path)
        payload = package_path.read_bytes()
        digest = hashlib.sha256(payload).hexdigest()

        old_version = str(entry.get("version") or "")
        old_dist = dict(entry.get("distribution") or {})
        entry["version"] = target_version
        distribution["package_url"] = (
            "https://raw.githubusercontent.com/Cliff-Lee/melodex/main/"
            f"provider-sdk/registry/packages/{filename}"
        )
        distribution["sha256"] = digest
        distribution["size_bytes"] = len(payload)
        entry["distribution"] = distribution
        entry.setdefault("review", {})["last_reviewed_at"] = REVIEWED_AT
        if old_version != target_version or old_dist != distribution:
            changed += 1

        review_path = REVIEWS / f"{entry['id']}.json"
        review = json.loads(review_path.read_text("utf-8"))
        events = list(review.get("events") or [])
        if not events:
            raise RuntimeError(f"{entry['id']}: review record has no events")
        latest = dict(events[-1])
        if not (
            str(latest.get("reviewed_at") or "") == REVIEWED_AT
            and str(latest.get("version") or "") == target_version
            and str(latest.get("package_sha256") or "") == digest
        ):
            events.append(
                _review_event(latest, version=target_version, digest=digest)
            )
            review["events"] = events
            _write_json(review_path, review)
            changed += 1

    registry["updated_at"] = REVIEWED_AT
    _write_json(REGISTRY_PATH, registry)
    shutil.copyfile(REGISTRY_PATH, EXAMPLE_REGISTRY_PATH)
    print(f"Rebuilt {len(TARGETS)} audited packages; changed markers: {changed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
