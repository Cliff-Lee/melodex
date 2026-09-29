from __future__ import annotations

import hashlib
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .provider import MusicProvider, ProviderInstaller
from .providers import JamendoProvider, LocalFilesProvider, UserStreamsProvider
from .resolver import UniversalResolver
from .capabilities import CapabilityBroker, ExtensionInfo
from .plugin_registry import PluginRegistryClient, RegistryResult
from .plugin_config import PluginConfigBroker
from .plugin_health import (
    health_summary,
    normalise_health_status,
    safe_health_text,
)


class ProviderManager:
    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self.settings_path = self.data_dir / "sources.json"
        self.installations_path = self.data_dir / "plugin-installations.json"
        self.installer = ProviderInstaller(self.data_dir / "providers")
        self.plugin_config = PluginConfigBroker(self.data_dir)
        self.settings = self._load_settings()
        self._installations = self._load_installations()
        local_roots = [Path(x) for x in self.settings.get("local_roots", [])]
        self.providers: dict[str, MusicProvider] = {
            "local": LocalFilesProvider(local_roots),
            "jamendo": JamendoProvider(str(self.settings.get("jamendo_client_id", ""))),
            "streams": UserStreamsProvider(list(self.settings.get("user_streams", []))),
        }
        for provider in self.installer.load_installed():
            provider.configure(
                self.plugin_config.values(
                    provider.info.id, provider.info.configuration
                )
            )
            self.providers[provider.info.id] = provider
        self.resolver = UniversalResolver(self)
        self.capabilities = CapabilityBroker(
            self.data_dir, config_broker=self.plugin_config
        )
        self.registry = PluginRegistryClient(self.data_dir)
        self._plugin_health_cache: dict[str, dict[str, Any]] = {}

    def _load_settings(self) -> dict[str, Any]:
        try:
            return json.loads(self.settings_path.read_text("utf-8"))
        except Exception:
            return {}

    def save(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.settings_path.write_text(
            json.dumps(self.settings, indent=2, ensure_ascii=False), "utf-8"
        )

    def _load_installations(self) -> dict[str, dict[str, Any]]:
        try:
            raw = json.loads(self.installations_path.read_text("utf-8"))
            if not isinstance(raw, dict):
                return {}
            return {
                str(key): dict(value)
                for key, value in raw.items()
                if isinstance(value, dict)
            }
        except Exception:
            return {}

    def _save_installations(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        temp = self.installations_path.with_suffix(".tmp")
        temp.write_text(
            json.dumps(self._installations, indent=2, ensure_ascii=False),
            "utf-8",
        )
        temp.replace(self.installations_path)

    @staticmethod
    def _package_sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with Path(path).open("rb") as handle:
            for chunk in iter(lambda: handle.read(64 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def _record_installation(
        self,
        *,
        plugin_id: str,
        name: str,
        version: str,
        kind: str,
        package: Path,
        method: str,
        registry_entry: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        package = Path(package)
        local_sha256 = self._package_sha256(package)
        entry = dict(registry_entry or {})
        distribution = dict(entry.get("distribution") or {})
        source = dict(entry.get("source") or {})
        registry_sha256 = str(distribution.get("sha256") or "").lower()
        record = {
            "id": str(plugin_id),
            "name": str(name),
            "version": str(version),
            "kind": str(kind),
            "installed_at": datetime.now(timezone.utc).isoformat(),
            "method": "registry" if method == "registry" else "manual",
            "package_name": package.name,
            "package_size": package.stat().st_size,
            "package_sha256": local_sha256,
            "registry_verified": bool(
                method == "registry"
                and registry_sha256
                and registry_sha256 == local_sha256
            ),
            "registry_status": str(entry.get("status") or ""),
            "publisher": str(entry.get("publisher") or ""),
            "package_url": str(distribution.get("package_url") or ""),
            "registry_sha256": registry_sha256,
            "source_repository": str(source.get("repository") or ""),
        }
        self._installations[str(plugin_id)] = record
        self._save_installations()
        return dict(record)

    def installation_record(self, plugin_id: str) -> dict[str, Any]:
        return dict(self._installations.get(str(plugin_id), {}))

    def plugin_installations(self) -> list[dict[str, Any]]:
        return [
            dict(value)
            for _, value in sorted(self._installations.items())
            if isinstance(value, dict)
        ]

    def set_local_roots(self, roots: list[Path]) -> int:
        provider = self.providers["local"]
        assert isinstance(provider, LocalFilesProvider)
        provider.set_roots(roots)
        self.settings["local_roots"] = [str(x) for x in roots]
        self.save()
        return len(provider.tracks)

    def set_jamendo_client_id(self, client_id: str) -> None:
        provider = self.providers["jamendo"]
        provider.configure({"client_id": client_id})
        self.settings["jamendo_client_id"] = client_id.strip()
        self.save()

    def _streams_provider(self) -> UserStreamsProvider:
        provider = self.providers["streams"]
        assert isinstance(provider, UserStreamsProvider)
        return provider

    def _save_user_streams(self) -> None:
        self.settings["user_streams"] = self._streams_provider().entries
        self.save()

    def user_streams(self) -> list[dict[str, Any]]:
        return self._streams_provider().entries

    def add_user_stream(
        self,
        name: str,
        url: str,
        genre: str = "",
        description: str = "",
    ) -> dict[str, Any]:
        item = self._streams_provider().add_stream(name, url, genre, description)
        self._save_user_streams()
        return item

    def update_user_stream(
        self,
        stream_id: str,
        name: str,
        url: str,
        genre: str = "",
        description: str = "",
    ) -> dict[str, Any]:
        item = self._streams_provider().update_stream(
            stream_id, name, url, genre, description
        )
        self._save_user_streams()
        return item

    def remove_user_stream(self, stream_id: str) -> bool:
        changed = self._streams_provider().remove_stream(stream_id)
        if changed:
            self._save_user_streams()
        return changed

    def import_user_stream_playlist(self, path: Path) -> list[dict[str, Any]]:
        items = self._streams_provider().import_playlist(path)
        if items:
            self._save_user_streams()
        return items

    def provider_order(self) -> list[str]:
        return self.resolver.provider_order()

    def set_provider_order(self, provider_ids: list[str]) -> list[str]:
        return self.resolver.set_provider_order(provider_ids)

    def install_package(
        self,
        path: Path,
        *,
        install_source: str = "manual",
        registry_entry: dict[str, Any] | None = None,
    ) -> MusicProvider:
        path = Path(path)
        folder = self.installer.install(path)
        manifest = json.loads((folder / "manifest.json").read_text("utf-8"))
        from .provider import ExternalProvider

        provider = ExternalProvider(folder, manifest)
        provider.configure(
            self.plugin_config.values(
                provider.info.id, provider.info.configuration
            )
        )
        previous = self.providers.get(provider.info.id)
        if previous is not None and previous is not provider:
            close = getattr(previous, "close", None)
            if callable(close):
                close()
        self.providers[provider.info.id] = provider
        self._plugin_health_cache.pop(provider.info.id, None)
        self._record_installation(
            plugin_id=provider.info.id,
            name=provider.info.name,
            version=provider.info.version,
            kind="provider",
            package=path,
            method=install_source,
            registry_entry=registry_entry,
        )
        return provider

    def search(self, query: str, provider_id: str = "all", limit: int = 50) -> list[dict[str, Any]]:
        if provider_id != "all":
            provider = self.providers[provider_id]
            if "search" not in list(provider.info.capabilities or []):
                return []
            return provider.search(query, limit)
        searchable = [
            pid
            for pid in self.provider_order()
            if "search" in list(self.providers[pid].info.capabilities or [])
        ]
        out: list[dict[str, Any]] = []
        per_provider = max(10, limit // max(1, len(searchable)))
        for pid in searchable:
            provider = self.providers[pid]
            try:
                out.extend(provider.search(query, per_provider))
            except Exception:
                continue
        return out[:limit]

    def recommend(
        self,
        seed: dict[str, Any],
        provider_id: str = "all",
        limit: int = 25,
    ) -> list[dict[str, Any]]:
        limit = max(1, min(100, int(limit)))
        if provider_id != "all":
            provider = self.providers[provider_id]
            if "recommendations" not in list(provider.info.capabilities or []):
                return []
            return provider.recommend(seed, limit)

        recommendation_providers = [
            pid
            for pid in self.provider_order()
            if "recommendations" in list(self.providers[pid].info.capabilities or [])
        ]
        out: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()
        per_provider = max(10, limit // max(1, len(recommendation_providers)))
        for pid in recommendation_providers:
            try:
                rows = self.providers[pid].recommend(seed, per_provider)
            except Exception:
                continue
            for row in rows:
                key = (
                    str(row.get("artist") or "").casefold().strip(),
                    str(row.get("title") or "").casefold().strip(),
                )
                if key == ("", "") or key in seen:
                    continue
                seen.add(key)
                out.append(row)
                if len(out) >= limit:
                    return out
        return out[:limit]

    def browse(self, provider_id: str, kind: str = "featured", limit: int = 50) -> list[dict[str, Any]]:
        return self.providers[provider_id].browse(kind, limit)

    def resolve(self, track: dict[str, Any]) -> dict[str, Any]:
        return self.resolver.resolve(track)

    def refresh_playback(self, track: dict[str, Any]) -> dict[str, Any]:
        provider_id = str(track.get("provider_id") or "")
        provider = self.providers.get(provider_id)
        if provider is None:
            return self.resolve(track)
        return provider.refresh(track)

    def resolve_exact(self, candidate: dict[str, Any], requested: dict[str, Any] | None = None) -> dict[str, Any]:
        return self.resolver.resolve_exact(candidate, requested)

    def resolve_candidates(self, track: dict[str, Any], limit: int = 20) -> list[dict[str, Any]]:
        return [item.as_dict() for item in self.resolver.candidates(track, total_limit=limit)]

    def inspect_resolution(self, track: dict[str, Any], limit: int = 20) -> dict[str, Any]:
        return self.resolver.inspect(track, limit)

    def resolve_playlist(self, tracks: list[dict[str, Any]]) -> dict[str, Any]:
        return self.resolver.resolve_many(tracks)

    def block_resolution(self, requested: dict[str, Any], matched: dict[str, Any]) -> None:
        self.resolver.block(requested, matched)

    def prefer_resolution(self, requested: dict[str, Any], matched: dict[str, Any]) -> None:
        self.resolver.prefer(requested, matched)

    def clear_resolution_preference(self, requested: dict[str, Any]) -> None:
        self.resolver.clear_preference(requested)

    def clear_resolution_blocks(self, requested: dict[str, Any]) -> None:
        self.resolver.unblock_target(requested)

    def clear_resolution_blocklist(self) -> None:
        self.resolver.unblock_all()

    def install_extension(
        self,
        path: Path,
        *,
        install_source: str = "manual",
        registry_entry: dict[str, Any] | None = None,
    ) -> ExtensionInfo:
        path = Path(path)
        info = self.capabilities.install_package(path)
        self._plugin_health_cache.pop(info.id, None)
        self._record_installation(
            plugin_id=info.id,
            name=info.name,
            version=info.version,
            kind="enrichment",
            package=path,
            method=install_source,
            registry_entry=registry_entry,
        )
        return info

    def plugin_configuration(self, plugin_id: str) -> dict[str, Any]:
        plugin_id = str(plugin_id or "").strip()
        provider = self.providers.get(plugin_id)
        if provider is not None and plugin_id not in {"local", "jamendo", "streams"}:
            declarations = list(provider.info.configuration or [])
            return {
                "id": plugin_id,
                "name": provider.info.name,
                "kind": "provider",
                "fields": declarations,
                "values": self.plugin_config.editable_values(
                    plugin_id, declarations
                ),
                "status": self.plugin_config.status(plugin_id, declarations),
            }

        extension = self.capabilities.extensions.get(plugin_id)
        if extension is not None:
            declarations = list(extension.info.configuration or [])
            return {
                "id": plugin_id,
                "name": extension.info.name,
                "kind": "extension",
                "fields": declarations,
                "values": self.plugin_config.editable_values(
                    plugin_id, declarations
                ),
                "status": self.plugin_config.status(plugin_id, declarations),
            }
        raise KeyError(f"Unknown configurable plugin: {plugin_id}")

    def set_plugin_configuration(
        self, plugin_id: str, changes: dict[str, Any]
    ) -> dict[str, Any]:
        info = self.plugin_configuration(plugin_id)
        declarations = list(info.get("fields") or [])
        status = self.plugin_config.update(plugin_id, declarations, dict(changes))
        values = self.plugin_config.values(plugin_id, declarations)

        provider = self.providers.get(plugin_id)
        if provider is not None and plugin_id not in {"local", "jamendo", "streams"}:
            provider.configure(values)
        extension = self.capabilities.extensions.get(plugin_id)
        if extension is not None:
            extension.configure(values)
        self._plugin_health_cache.pop(str(plugin_id), None)
        return status

    def _health_result(
        self,
        *,
        plugin_id: str,
        name: str,
        kind: str,
        status: str,
        message: str = "",
        check_scope: str = "",
        reason: str = "",
        checked: bool = False,
        provider_status: str = "",
    ) -> dict[str, Any]:
        result = {
            "id": str(plugin_id),
            "name": str(name),
            "kind": str(kind),
            "status": normalise_health_status(status),
            "message": safe_health_text(message),
            "check_scope": str(check_scope or ""),
            "reason": str(reason or ""),
            "checked": bool(checked),
            "provider_status": str(provider_status or ""),
        }
        if checked:
            result["checked_at"] = datetime.now(timezone.utc).isoformat()
        result["summary"] = health_summary(result)
        return result

    def plugin_health(self, plugin_id: str) -> dict[str, Any]:
        plugin_id = str(plugin_id or "").strip()
        if not plugin_id:
            raise KeyError("Missing plugin id")

        try:
            config = self.plugin_configuration(plugin_id)
        except KeyError:
            config = {}
        status = dict(config.get("status") or {})
        if status.get("declared") and not status.get("ready", True):
            return self._health_result(
                plugin_id=plugin_id,
                name=str(config.get("name") or plugin_id),
                kind=str(config.get("kind") or "plugin"),
                status="setup_required",
                message="Required configuration is incomplete",
                check_scope="configuration",
            )

        provider = self.providers.get(plugin_id)
        if provider is not None and plugin_id not in {"local", "jamendo", "streams"}:
            cached = self._plugin_health_cache.get(plugin_id)
            if cached:
                return dict(cached)
            return self._health_result(
                plugin_id=plugin_id,
                name=provider.info.name,
                kind="provider",
                status="untested",
                message="Connection has not been tested in this session",
                check_scope="provider",
            )

        extension = self.capabilities.extensions.get(plugin_id)
        if extension is not None:
            if not self.capabilities.enabled(plugin_id):
                return self._health_result(
                    plugin_id=plugin_id,
                    name=extension.info.name,
                    kind="extension",
                    status="disabled",
                    message="Extension is disabled",
                    check_scope="runtime",
                )
            runtime = extension.health()
            runtime_status = str(runtime.get("status") or "idle")
            if runtime_status == "ok":
                return self._health_result(
                    plugin_id=plugin_id,
                    name=extension.info.name,
                    kind="extension",
                    status="ready",
                    message="Recent extension calls succeeded",
                    check_scope="runtime",
                )
            if runtime_status == "error":
                return self._health_result(
                    plugin_id=plugin_id,
                    name=extension.info.name,
                    kind="extension",
                    status="error",
                    message="Recent extension call failed",
                    check_scope="runtime",
                    reason=str(runtime.get("last_error") or "call_error"),
                )
            cached = self._plugin_health_cache.get(plugin_id)
            if cached:
                return dict(cached)
            return self._health_result(
                plugin_id=plugin_id,
                name=extension.info.name,
                kind="extension",
                status="untested",
                message="Extension has not been exercised in this session",
                check_scope="runtime",
            )

        raise KeyError(f"Unknown plugin: {plugin_id}")

    def test_plugin_health(
        self, plugin_id: str, timeout: float = 8.0
    ) -> dict[str, Any]:
        plugin_id = str(plugin_id or "").strip()
        current = self.plugin_health(plugin_id)
        if current.get("status") == "setup_required":
            return current

        provider = self.providers.get(plugin_id)
        if provider is not None and plugin_id not in {"local", "jamendo", "streams"}:
            raw = dict(provider.health_check(timeout=timeout) or {})
            provider_status = str(raw.get("status") or "")
            result = self._health_result(
                plugin_id=plugin_id,
                name=provider.info.name,
                kind="provider",
                status=provider_status,
                message=str(raw.get("message") or ""),
                check_scope=str(raw.get("check_scope") or "provider"),
                reason=str(raw.get("reason") or ""),
                checked=True,
                provider_status=provider_status,
            )
            self._plugin_health_cache[plugin_id] = result
            return dict(result)

        extension = self.capabilities.extensions.get(plugin_id)
        if extension is not None:
            if not self.capabilities.enabled(plugin_id):
                result = self._health_result(
                    plugin_id=plugin_id,
                    name=extension.info.name,
                    kind="extension",
                    status="disabled",
                    message="Extension is disabled",
                    check_scope="process",
                    checked=True,
                )
            else:
                raw = dict(extension.process_check() or {})
                result = self._health_result(
                    plugin_id=plugin_id,
                    name=extension.info.name,
                    kind="extension",
                    status=str(raw.get("status") or ""),
                    message=str(raw.get("message") or ""),
                    check_scope=str(raw.get("check_scope") or "process"),
                    reason=str(raw.get("reason") or ""),
                    checked=True,
                )
            self._plugin_health_cache[plugin_id] = result
            return dict(result)

        raise KeyError(f"Unknown plugin: {plugin_id}")

    def plugin_registry(self, force: bool = False) -> RegistryResult:
        return self.registry.fetch(force=force)

    def download_registry_entry(self, entry: dict[str, Any]) -> Path:
        return self.registry.download_package(dict(entry or {}))

    def install_downloaded_registry_entry(
        self, entry: dict[str, Any], package: Path
    ) -> dict[str, Any]:
        entry = dict(entry or {})
        package = Path(package)
        fmt = str((entry.get("distribution") or {}).get("format") or "")
        expected_id = str(entry.get("id") or "")
        expected_version = str(entry.get("version") or "")

        with zipfile.ZipFile(package) as archive:
            if fmt == "mdxprovider":
                _, descriptor = self.installer._manifest_from_archive(archive)
                actual_id = str(descriptor.get("id") or "")
                actual_version = str(descriptor.get("version") or "")
            elif fmt == "mdxplugin":
                _, descriptor = self.capabilities.installer._descriptor_from_archive(
                    archive
                )
                actual_id = str(descriptor.get("extension_id") or "")
                actual_version = str(descriptor.get("version") or "")
            else:
                raise RuntimeError(
                    f"Unsupported registry package format: {fmt}"
                )

        if actual_id != expected_id:
            raise RuntimeError(
                f"Registry/package id mismatch: expected {expected_id!r}, "
                f"package declares {actual_id!r}"
            )
        if expected_version and actual_version != expected_version:
            raise RuntimeError(
                f"Registry/package version mismatch: expected {expected_version!r}, "
                f"package declares {actual_version!r}"
            )
        if fmt == "mdxprovider":
            provider = self.install_package(
                package,
                install_source="registry",
                registry_entry=entry,
            )
            return {
                "id": provider.info.id,
                "name": provider.info.name,
                "kind": "provider",
                "package": str(package),
            }
        if fmt == "mdxplugin":
            info = self.install_extension(
                package,
                install_source="registry",
                registry_entry=entry,
            )
            return {
                "id": info.id,
                "name": info.name,
                "kind": "enrichment",
                "package": str(package),
            }
        raise RuntimeError(f"Unsupported registry package format: {fmt}")

    def install_registry_entry(self, entry: dict[str, Any]) -> dict[str, Any]:
        package = self.download_registry_entry(entry)
        return self.install_downloaded_registry_entry(entry, package)

    def remove_extension(self, extension_id: str) -> bool:
        changed = self.capabilities.remove(extension_id)
        if changed and extension_id in self._installations:
            self._installations.pop(extension_id, None)
            self._save_installations()
        if changed:
            self._plugin_health_cache.pop(str(extension_id), None)
        return changed

    def extensions(self) -> list[dict[str, Any]]:
        return self.capabilities.list_extensions()

    def set_extension_enabled(self, extension_id: str, enabled: bool) -> None:
        self.capabilities.set_enabled(extension_id, enabled)
        self._plugin_health_cache.pop(str(extension_id), None)

    def set_capability_preference(
        self, capability: str, extension_ids: list[str]
    ) -> list[str]:
        return self.capabilities.set_preference(capability, extension_ids)

    def local_catalog(self) -> list[dict[str, Any]]:
        provider = self.providers["local"]
        return provider.tracks if isinstance(provider, LocalFilesProvider) else []

    def close(self) -> None:
        self.capabilities.close()
        for provider in self.providers.values():
            close = getattr(provider, "close", None)
            if callable(close):
                close()
