from __future__ import annotations

import hashlib
import json
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests

from . import __version__ as MELODEX_VERSION


DEFAULT_REGISTRY_URL = (
    "https://raw.githubusercontent.com/Cliff-Lee/melodex/main/"
    "provider-sdk/registry/registry.json"
)
MAX_PACKAGE_BYTES = 25 * 1024 * 1024
CACHE_MAX_AGE_SECONDS = 6 * 60 * 60
_SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")


@dataclass(slots=True)
class RegistryResult:
    plugins: list[dict[str, Any]]
    source: str
    stale: bool = False
    error: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "plugins": [dict(item) for item in self.plugins],
            "source": self.source,
            "stale": self.stale,
            "error": self.error,
        }


def version_tuple(value: str) -> tuple[int, ...]:
    parts: list[int] = []
    for raw in re.split(r"[.+-]", str(value or "")):
        match = re.match(r"^(\d+)", raw)
        if match:
            parts.append(int(match.group(1)))
        else:
            break
    return tuple(parts or [0])


def validate_registry(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["registry must be a JSON object"]
    if str(data.get("schema_version") or "") != "0.1":
        errors.append("schema_version must be '0.1'")
    plugins = data.get("plugins")
    if not isinstance(plugins, list):
        return errors + ["plugins must be an array"]

    seen: set[str] = set()
    for index, raw in enumerate(plugins):
        prefix = f"plugins[{index}]"
        if not isinstance(raw, dict):
            errors.append(f"{prefix} must be an object")
            continue
        plugin_id = str(raw.get("id") or "").strip()
        if not plugin_id:
            errors.append(f"{prefix}.id is required")
        elif plugin_id in seen:
            errors.append(f"{prefix}.id is duplicated: {plugin_id}")
        else:
            seen.add(plugin_id)

        for key in ("name", "version", "kind", "status", "license"):
            if not str(raw.get(key) or "").strip():
                errors.append(f"{prefix}.{key} is required")
        if raw.get("kind") not in {"provider", "enrichment", "tool"}:
            errors.append(f"{prefix}.kind is invalid")
        if raw.get("status") not in {
            "example",
            "community",
            "reviewed",
            "deprecated",
            "blocked",
        }:
            errors.append(f"{prefix}.status is invalid")
        if not isinstance(raw.get("capabilities"), list):
            errors.append(f"{prefix}.capabilities must be an array")
        if not isinstance(raw.get("permissions"), list):
            errors.append(f"{prefix}.permissions must be an array")

        source = raw.get("source")
        if not isinstance(source, dict) or not str(source.get("repository") or ""):
            errors.append(f"{prefix}.source.repository is required")

        review = raw.get("review")
        if not isinstance(review, dict):
            errors.append(f"{prefix}.review is required")
        else:
            record_url = str(review.get("record") or "").strip()
            if not record_url or urlparse(record_url).scheme != "https":
                errors.append(f"{prefix}.review.record must use HTTPS")
            if not str(review.get("last_reviewed_at") or "").strip():
                errors.append(f"{prefix}.review.last_reviewed_at is required")

        distribution = raw.get("distribution")
        if not isinstance(distribution, dict):
            errors.append(f"{prefix}.distribution is required")
            continue
        fmt = str(distribution.get("format") or "")
        if fmt not in {"mdxprovider", "mdxplugin"}:
            errors.append(f"{prefix}.distribution.format is invalid")
        kind = str(raw.get("kind") or "")
        if kind == "provider" and fmt != "mdxprovider":
            errors.append(
                f"{prefix}.distribution.format must be mdxprovider for providers"
            )
        if kind == "enrichment" and fmt != "mdxplugin":
            errors.append(
                f"{prefix}.distribution.format must be mdxplugin for enrichment"
            )
        package_url = distribution.get("package_url")
        sha256 = distribution.get("sha256")
        if package_url:
            parsed = urlparse(str(package_url))
            if parsed.scheme != "https":
                errors.append(f"{prefix}.distribution.package_url must use HTTPS")
            if not isinstance(sha256, str) or not _SHA256_RE.fullmatch(sha256):
                errors.append(
                    f"{prefix}.distribution.sha256 is required for installable packages"
                )
        elif sha256:
            errors.append(
                f"{prefix}.distribution.sha256 is meaningless without package_url"
            )
        size_bytes = distribution.get("size_bytes")
        if size_bytes is not None:
            try:
                if int(size_bytes) <= 0 or int(size_bytes) > MAX_PACKAGE_BYTES:
                    raise ValueError
            except (TypeError, ValueError):
                errors.append(f"{prefix}.distribution.size_bytes is invalid")
    return errors


class PluginRegistryClient:
    def __init__(
        self,
        data_dir: Path,
        registry_url: str | None = None,
        session: requests.Session | None = None,
        timeout: float = 15.0,
    ):
        self.data_dir = Path(data_dir)
        self.cache_dir = self.data_dir / "registry"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.download_dir = self.cache_dir / "downloads"
        self.download_dir.mkdir(parents=True, exist_ok=True)
        self.cache_path = self.cache_dir / "registry-cache.json"
        self.registry_url = (
            str(registry_url or os.environ.get("MELODEX_REGISTRY_URL") or DEFAULT_REGISTRY_URL)
            .strip()
        )
        self.session = session or requests.Session()
        self.timeout = float(timeout)
        self.user_agent = (
            "Melodex-Plugin-Directory/0.1 "
            "(https://github.com/Cliff-Lee/melodex)"
        )

    def _read_cache(self) -> dict[str, Any] | None:
        try:
            data = json.loads(self.cache_path.read_text("utf-8"))
            return data if not validate_registry(data) else None
        except Exception:
            return None

    def _write_cache(self, data: dict[str, Any]) -> None:
        temp = self.cache_path.with_suffix(".tmp")
        temp.write_text(json.dumps(data, indent=2, ensure_ascii=False), "utf-8")
        temp.replace(self.cache_path)

    def fetch(self, force: bool = False) -> RegistryResult:
        cached = self._read_cache()
        cache_fresh = False
        if cached is not None:
            try:
                cache_fresh = (
                    time.time() - self.cache_path.stat().st_mtime
                    <= CACHE_MAX_AGE_SECONDS
                )
            except OSError:
                cache_fresh = False
        if cached is not None and cache_fresh and not force:
            return RegistryResult(
                plugins=list(cached.get("plugins") or []),
                source="cache",
            )
        try:
            response = self.session.get(
                self.registry_url,
                headers={"User-Agent": self.user_agent, "Accept": "application/json"},
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()
            errors = validate_registry(data)
            if errors:
                raise RuntimeError("Registry validation failed: " + "; ".join(errors))
            self._write_cache(data)
            return RegistryResult(
                plugins=list(data.get("plugins") or []),
                source=self.registry_url,
            )
        except Exception as exc:
            if cached is not None:
                return RegistryResult(
                    plugins=list(cached.get("plugins") or []),
                    source="cache",
                    stale=True,
                    error=str(exc),
                )
            raise RuntimeError(f"Could not load plugin registry: {exc}") from exc

    @staticmethod
    def compatibility(entry: dict[str, Any]) -> tuple[bool, str]:
        compatibility = dict(entry.get("compatibility") or {})
        minimum = str(compatibility.get("melodex_min") or "").strip()
        if minimum and version_tuple(MELODEX_VERSION) < version_tuple(minimum):
            return (
                False,
                f"Requires Melodex {minimum} or newer; this build is {MELODEX_VERSION}.",
            )
        return True, ""

    @staticmethod
    def update_available(entry: dict[str, Any], installed_version: str) -> bool:
        remote = version_tuple(str(entry.get("version") or "0"))
        local = version_tuple(str(installed_version or "0"))
        return remote > local

    @staticmethod
    def filter_plugins(
        plugins: list[dict[str, Any]],
        query: str = "",
        kind: str = "all",
        capability: str = "all",
    ) -> list[dict[str, Any]]:
        q = str(query or "").casefold().strip()
        out: list[dict[str, Any]] = []
        for raw in plugins:
            item = dict(raw)
            if str(item.get("status") or "") == "blocked":
                continue
            if kind != "all" and str(item.get("kind") or "") != kind:
                continue
            capabilities = [str(x) for x in item.get("capabilities") or []]
            if capability != "all" and capability not in capabilities:
                continue
            haystack = " ".join(
                [
                    str(item.get("name") or ""),
                    str(item.get("id") or ""),
                    str(item.get("publisher") or ""),
                    str(item.get("description") or ""),
                    " ".join(capabilities),
                ]
            ).casefold()
            if q and q not in haystack:
                continue
            out.append(item)
        out.sort(
            key=lambda item: (
                {"reviewed": 0, "example": 1, "community": 2, "deprecated": 3}.get(
                    str(item.get("status") or ""), 9
                ),
                str(item.get("name") or "").casefold(),
            )
        )
        return out

    def download_package(self, entry: dict[str, Any]) -> Path:
        entry = dict(entry or {})
        if str(entry.get("status") or "") == "blocked":
            raise RuntimeError("This registry entry is blocked and cannot be installed")
        compatible, reason = self.compatibility(entry)
        if not compatible:
            raise RuntimeError(reason)

        distribution = dict(entry.get("distribution") or {})
        package_url = str(distribution.get("package_url") or "").strip()
        expected_hash = str(distribution.get("sha256") or "").lower().strip()
        fmt = str(distribution.get("format") or "").strip()
        if fmt not in {"mdxprovider", "mdxplugin"}:
            raise RuntimeError(f"Unsupported package format: {fmt or 'missing'}")
        if not package_url:
            raise RuntimeError("This registry entry does not publish an installable package")
        if not _SHA256_RE.fullmatch(expected_hash):
            raise RuntimeError("Registry package has no valid SHA-256 digest")
        parsed = urlparse(package_url)
        if parsed.scheme != "https":
            raise RuntimeError("Registry packages must be downloaded over HTTPS")

        suffix = ".mdxprovider" if fmt == "mdxprovider" else ".mdxplugin"
        plugin_id = re.sub(r"[^A-Za-z0-9._-]+", "_", str(entry.get("id") or "plugin"))
        destination = self.download_dir / f"{plugin_id}-{entry.get('version')}{suffix}"
        part = destination.with_suffix(destination.suffix + ".part")

        digest = hashlib.sha256()
        total = 0
        try:
            with self.session.get(
                package_url,
                headers={
                    "User-Agent": self.user_agent,
                    "Accept": "application/octet-stream",
                },
                timeout=self.timeout,
                stream=True,
            ) as response:
                response.raise_for_status()
                final_url = urlparse(str(getattr(response, "url", package_url)))
                if final_url.scheme != "https":
                    raise RuntimeError("Package download redirected away from HTTPS")
                content_length = response.headers.get("Content-Length")
                if content_length and int(content_length) > MAX_PACKAGE_BYTES:
                    raise RuntimeError("Package is larger than Melodex's 25 MB registry limit")
                with part.open("wb") as handle:
                    for chunk in response.iter_content(chunk_size=64 * 1024):
                        if not chunk:
                            continue
                        total += len(chunk)
                        if total > MAX_PACKAGE_BYTES:
                            raise RuntimeError(
                                "Package is larger than Melodex's 25 MB registry limit"
                            )
                        digest.update(chunk)
                        handle.write(chunk)
            expected_size = distribution.get("size_bytes")
            if expected_size is not None and int(expected_size) != total:
                raise RuntimeError(
                    f"Package size mismatch: expected {expected_size}, received {total}"
                )
            actual_hash = digest.hexdigest()
            if actual_hash != expected_hash:
                raise RuntimeError(
                    "Package SHA-256 mismatch. The download may be corrupted or changed."
                )
            part.replace(destination)
            return destination
        except Exception:
            part.unlink(missing_ok=True)
            raise
