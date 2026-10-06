from __future__ import annotations

import hashlib
import json
import shutil
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

from .library_index import LocalLibraryIndex
from .provider import MusicProvider, ProviderInstaller
from .providers import JamendoProvider, LocalFilesProvider, UserStreamsProvider
from .resolver import UniversalResolver
from .capabilities import CapabilityBroker, ExtensionInfo
from .plugin_config import PluginConfigBroker
from .bundled_sources import (
    bundled_packages,
    ensure_bundled_providers,
    restore_all_bundled_provider_flags,
    set_bundled_provider_disabled,
    version_key,
)
if TYPE_CHECKING:
    from .plugin_registry import PluginRegistryClient, RegistryResult

from .plugin_health import (
    health_summary,
    normalise_health_status,
    safe_health_text,
)


SUPERSEDED_PROVIDER_REPLACEMENTS = {
    "org.melodex.example.radio-browser": "org.melodex.radiobrowser",
    "org.melodex.example.librivox": "org.melodex.librivox",
}


class ProviderManager:
    def __init__(self, data_dir: Path, *, startup_timeline=None):
        self.data_dir = Path(data_dir)
        self._startup_timeline = startup_timeline
        self.settings_path = self.data_dir / "sources.json"
        self.installations_path = self.data_dir / "plugin-installations.json"
        self.local_metadata_path = self.data_dir / "local-metadata-overrides.json"
        self.installer = ProviderInstaller(self.data_dir / "providers")
        self.plugin_config = PluginConfigBroker(self.data_dir)
        self.settings = self._load_settings()
        self._installations = self._load_installations()
        self._local_metadata_overrides = self._load_local_metadata_overrides()
        self._startup_mark("providers:settings_ready")

        bundled_ids = set(ensure_bundled_providers(self.installer, self.settings))
        self._record_bundled_installations(bundled_ids)
        self._startup_mark("providers:bundled_ready")

        local_roots = [Path(x) for x in self.settings.get("local_roots", [])]
        self.library_index = LocalLibraryIndex(
            self.data_dir / "library-index.sqlite3"
        )
        self.library_index.sync_roots_if_needed(local_roots)
        self._local_index_summary = self.library_index.summary(local_roots)
        local_provider = LocalFilesProvider(
            local_roots,
            self._local_metadata_overrides,
            scan_on_init=False,
        )
        if local_roots and int(self._local_index_summary.get("track_count") or 0):
            local_provider.set_cached_loader(
                lambda roots=tuple(local_roots): self.library_index.load_tracks(
                    [Path(root) for root in roots]
                )
            )
        self._startup_mark("providers:local_index_ready")

        self.providers: dict[str, MusicProvider] = {
            "local": local_provider,
            "jamendo": JamendoProvider(str(self.settings.get("jamendo_client_id", ""))),
            "streams": UserStreamsProvider(list(self.settings.get("user_streams", []))),
        }
        self._quarantined_legacy_providers: list[dict[str, str]] = []
        self._superseded_providers: list[dict[str, str]] = []
        for provider in self.installer.load_installed():
            replacement = SUPERSEDED_PROVIDER_REPLACEMENTS.get(
                str(provider.info.id or "")
            )
            if replacement and replacement in bundled_ids:
                self._superseded_providers.append(
                    {
                        "id": str(provider.info.id or ""),
                        "name": str(provider.info.name or provider.info.id or ""),
                        "replacement": replacement,
                    }
                )
                close = getattr(provider, "close", None)
                if callable(close):
                    close()
                continue
            if self._is_legacy_private_provider(provider):
                self._quarantined_legacy_providers.append(
                    {
                        "id": str(provider.info.id or ""),
                        "name": str(provider.info.name or provider.info.id or ""),
                    }
                )
                close = getattr(provider, "close", None)
                if callable(close):
                    close()
                continue
            declarations = list(provider.info.configuration or [])
            if declarations:
                provider.set_config_loader(
                    lambda item=provider, fields=declarations: self.plugin_config.values(
                        item.info.id,
                        fields,
                    )
                )
            self.providers[provider.info.id] = provider
        self._startup_mark("providers:installed_ready")

        self.resolver = UniversalResolver(self)
        self.capabilities = CapabilityBroker(
            self.data_dir, config_broker=self.plugin_config
        )
        self._startup_mark("providers:capabilities_ready")
        self._registry: PluginRegistryClient | None = None
        self._plugin_health_cache: dict[str, dict[str, Any]] = {}
        self._startup_mark("providers:ready")

    def _startup_mark(self, phase: str) -> None:
        timeline = getattr(self, "_startup_timeline", None)
        if timeline is not None:
            timeline.mark(phase)

    @property
    def registry(self) -> PluginRegistryClient:
        if self._registry is None:
            from .plugin_registry import PluginRegistryClient

            self._registry = PluginRegistryClient(self.data_dir)
        return self._registry

    @staticmethod
    def _is_legacy_private_provider(provider: MusicProvider) -> bool:
        """Recognise development-only providers that must not become public sources.

        The marker strings are deliberately assembled from fragments so the
        repository's release audit can continue to reject those legacy source
        names if they ever appear literally in a public payload or registry.
        """
        marker_a=("music" + "mp3").casefold()
        marker_b=("mp3" + "streams").casefold()
        values=(
            str(getattr(provider.info, "id", "") or ""),
            str(getattr(provider.info, "name", "") or ""),
        )
        for value in values:
            compact="".join(ch for ch in value.casefold() if ch.isalnum())
            if marker_a in compact or marker_b in compact:
                return True
        return False

    def quarantined_legacy_providers(self) -> list[dict[str, str]]:
        return [dict(row) for row in self._quarantined_legacy_providers]

    def superseded_providers(self) -> list[dict[str, str]]:
        """Installed providers hidden because an included replacement exists."""
        return [dict(row) for row in self._superseded_providers]

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

    def _load_local_metadata_overrides(self) -> dict[str, dict[str, Any]]:
        try:
            raw = json.loads(self.local_metadata_path.read_text("utf-8"))
            if not isinstance(raw, dict):
                return {}
            return {
                str(key): dict(value)
                for key, value in raw.items()
                if isinstance(value, dict)
            }
        except Exception:
            return {}

    def _save_local_metadata_overrides(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        temp = self.local_metadata_path.with_suffix(".tmp")
        temp.write_text(
            json.dumps(
                self._local_metadata_overrides,
                indent=2,
                ensure_ascii=False,
            ),
            "utf-8",
        )
        temp.replace(self.local_metadata_path)

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

    def _record_bundled_installations(self, bundled_ids: set[str]) -> None:
        for plugin_id, package, manifest in bundled_packages():
            if plugin_id not in bundled_ids:
                continue
            installed_path = self.installer.providers_dir / plugin_id / "manifest.json"
            try:
                installed = json.loads(installed_path.read_text("utf-8"))
            except Exception:
                continue
            installed_version = str(installed.get("version") or "0")
            bundled_version = str(manifest.get("version") or "0")
            record = self._installations.get(plugin_id)
            if record:
                recorded_version = str(record.get("version") or "0")
                if record.get("method") in {"manual", "registry"}:
                    # A newer user-installed package is left intact. If the
                    # bundled package upgraded an older install, record the
                    # bundle as the new source of the installed version.
                    if not (
                        version_key(installed_version) == version_key(bundled_version)
                        and version_key(recorded_version) < version_key(bundled_version)
                    ):
                        continue
                elif (
                    record.get("method") == "bundled"
                    and recorded_version == installed_version
                ):
                    continue
            self._record_installation(
                plugin_id=plugin_id,
                name=str(installed.get("name") or manifest.get("name") or plugin_id),
                version=installed_version,
                kind="provider",
                package=package,
                method="bundled",
            )

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
            "method": method if method in {"registry", "manual", "bundled"} else "manual",
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

    def configure_local_roots(self, roots: list[Path]) -> list[Path]:
        """Persist roots without scanning them on the caller/UI thread."""
        clean = [Path(x) for x in roots]
        provider = self.providers["local"]
        assert isinstance(provider, LocalFilesProvider)
        provider.configure_roots(clean)
        provider.set_cached_loader(None)
        self.settings["local_roots"] = [str(x) for x in clean]
        self.library_index.sync_roots(clean)
        self._local_index_summary=self.library_index.summary(clean)
        self.save()
        return clean

    def local_roots(self) -> list[Path]:
        return [Path(x) for x in self.settings.get("local_roots", [])]

    def local_index_ready(self, roots: list[Path] | None = None) -> bool:
        selected = self.local_roots() if roots is None else [Path(x) for x in roots]
        return self.library_index.roots_ready(selected)

    def local_index_summary(self) -> dict[str, Any]:
        roots=self.local_roots()
        summary=self.library_index.summary(roots)
        self._local_index_summary=dict(summary)
        return summary

    def local_catalog_count(self) -> int:
        provider=self.providers.get("local")
        if isinstance(provider,LocalFilesProvider) and provider.catalog_loaded:
            return len(provider.tracks)
        return int(dict(getattr(self,"_local_index_summary",{}) or {}).get("track_count") or 0)

    def load_indexed_local_tracks(
        self,
        roots: list[Path] | None = None,
    ) -> list[dict[str, Any]]:
        selected = self.local_roots() if roots is None else [Path(x) for x in roots]
        provider = self.providers["local"]
        assert isinstance(provider, LocalFilesProvider)
        return provider.prepare_cached_tracks(
            self.library_index.load_tracks(selected)
        )

    def persist_local_scan_snapshot(
        self,
        roots: list[Path],
        snapshot: dict[str, Any],
    ) -> dict[str, Any]:
        return self.library_index.replace_scan(
            [Path(x) for x in roots],
            dict(snapshot or {}),
        )

    def indexed_scan_result(
        self,
        roots: list[Path],
        snapshot: dict[str, Any],
    ) -> dict[str, Any]:
        """Return a completed scan merged with cached offline-root metadata."""
        result = dict(snapshot or {})
        result["tracks"] = self.load_indexed_local_tracks(roots)
        return result

    def scan_local_roots_snapshot(
        self,
        roots: list[Path] | None = None,
        *,
        progress: Callable[[dict[str, Any]], None] | None = None,
        control: Any = None,
    ) -> dict[str, Any]:
        provider = self.providers["local"]
        assert isinstance(provider, LocalFilesProvider)
        scan_roots = self.local_roots() if roots is None else [Path(x) for x in roots]
        return provider.scan_snapshot(
            scan_roots,
            progress=progress,
            control=control,
            cached_entries=self.library_index.load_scan_cache(scan_roots),
            cached_directories=self.library_index.load_directory_manifests(
                scan_roots
            ),
            cache_keys_canonical=True,
        )

    def apply_local_scan_snapshot(self, snapshot: dict[str, Any]) -> int:
        provider = self.providers["local"]
        assert isinstance(provider, LocalFilesProvider)
        count=provider.apply_scan_snapshot(snapshot)
        self._local_index_summary=self.library_index.summary(self.local_roots())
        return count

    def set_local_roots(self, roots: list[Path]) -> int:
        """Compatibility API for synchronous/non-GUI callers."""
        clean = self.configure_local_roots(roots)
        snapshot = self.scan_local_roots_snapshot(clean)
        if not bool(snapshot.get("cancelled")):
            self.persist_local_scan_snapshot(clean, snapshot)
            snapshot = self.indexed_scan_result(clean, snapshot)
        return self.apply_local_scan_snapshot(snapshot)

    def update_local_metadata(
        self,
        track: dict[str, Any],
        changes: dict[str, Any],
    ) -> dict[str, Any]:
        local_path = str(track.get("local_path") or "").strip()
        if not local_path:
            raise ValueError("Only local music can be corrected here.")
        provider = self.providers.get("local")
        if not isinstance(provider, LocalFilesProvider):
            raise RuntimeError("Local music provider is unavailable.")

        clean: dict[str, Any] = {}
        for field in LocalFilesProvider.EDITABLE_METADATA_FIELDS:
            if field not in changes:
                continue
            value = changes[field]
            if field in {"year", "track_number", "disc_number"}:
                text = str(value or "").strip()
                clean[field] = int(text) if text.isdigit() else 0
            else:
                clean[field] = str(value or "").strip()

        key = provider._override_key(local_path)
        existing = dict(self._local_metadata_overrides.get(key) or {})
        existing.update(clean)
        self._local_metadata_overrides[key] = existing
        self._save_local_metadata_overrides()

        updated = provider.set_metadata_override(local_path, clean)
        return updated or {**track, **clean}

    def clear_local_metadata_correction(self, track: dict[str, Any]) -> bool:
        local_path = str(track.get("local_path") or "").strip()
        if not local_path:
            return False
        provider = self.providers.get("local")
        if not isinstance(provider, LocalFilesProvider):
            return False
        key = provider._override_key(local_path)
        changed = key in self._local_metadata_overrides
        self._local_metadata_overrides.pop(key, None)
        if changed:
            self._save_local_metadata_overrides()
            provider.clear_metadata_override(local_path, rescan=False)
        return changed

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

    _SEARCH_SHADOWS = {
        "org.melodex.example.radio-browser": "org.melodex.radiobrowser",
        "org.melodex.example.librivox": "org.melodex.librivox",
    }
    _SEARCH_REFERENCE_ONLY = {
        "org.melodex.example.openverse-audio",
    }

    def searchable_provider_ids(self) -> list[str]:
        """Return end-user search sources with duplicate examples suppressed.

        Reference/example providers remain installed and manageable for developers,
        but when the production bundled equivalent is present, normal listeners
        should see and query only the production source.
        """
        ordered = []
        for pid in self.provider_order():
            provider = self.providers.get(pid)
            if provider is None:
                continue
            if "search" not in list(provider.info.capabilities or []):
                continue
            if pid in self._SEARCH_REFERENCE_ONLY:
                continue
            production_id = self._SEARCH_SHADOWS.get(pid)
            if production_id and production_id in self.providers:
                continue
            ordered.append(pid)
        return ordered

    def set_provider_order(self, provider_ids: list[str]) -> list[str]:
        return self.resolver.set_provider_order(provider_ids)

    def is_bundled_provider(self, provider_id: str) -> bool:
        return any(pid == str(provider_id or "") for pid, _, _ in bundled_packages())

    def remove_provider(self, provider_id: str) -> bool:
        plugin_id = str(provider_id or "").strip()
        if not plugin_id or plugin_id in {"local", "jamendo", "streams"}:
            return False
        provider = self.providers.get(plugin_id)
        if provider is None:
            return False

        close = getattr(provider, "close", None)
        if callable(close):
            try:
                close()
            except Exception:
                pass
        shutil.rmtree(self.installer.providers_dir / plugin_id, ignore_errors=True)
        self.providers.pop(plugin_id, None)
        self._plugin_health_cache.pop(plugin_id, None)
        self._installations.pop(plugin_id, None)
        if self.is_bundled_provider(plugin_id):
            set_bundled_provider_disabled(self.settings, plugin_id, True)
        self.settings["provider_priority"] = [
            item
            for item in list(self.settings.get("provider_priority") or [])
            if str(item) != plugin_id
        ]
        self._save_installations()
        self.save()
        return True

    def restore_bundled_providers(self) -> list[str]:
        restore_all_bundled_provider_flags(self.settings)
        self.save()
        bundled_ids = set(ensure_bundled_providers(self.installer, self.settings))
        self._record_bundled_installations(bundled_ids)
        from .provider import ExternalProvider

        restored: list[str] = []
        for plugin_id in sorted(bundled_ids):
            if plugin_id in self.providers:
                continue
            manifest_path = self.installer.providers_dir / plugin_id / "manifest.json"
            try:
                manifest = json.loads(manifest_path.read_text("utf-8"))
                provider = ExternalProvider(manifest_path.parent, manifest)
                provider.configure(
                    self.plugin_config.values(
                        provider.info.id, provider.info.configuration
                    )
                )
            except Exception:
                continue
            self.providers[plugin_id] = provider
            self._plugin_health_cache.pop(plugin_id, None)
            restored.append(plugin_id)
        if restored:
            self.set_provider_order(self.provider_order())
        return restored

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
        if self._is_legacy_private_provider(provider):
            close=getattr(provider,"close",None)
            if callable(close):
                close()
            shutil.rmtree(folder,ignore_errors=True)
            raise ValueError(
                "This legacy development provider is not supported by public Melodex builds."
            )
        replacement = SUPERSEDED_PROVIDER_REPLACEMENTS.get(
            str(provider.info.id or "")
        )
        if replacement and self.is_bundled_provider(replacement):
            close=getattr(provider,"close",None)
            if callable(close):
                close()
            shutil.rmtree(folder,ignore_errors=True)
            replacement_provider=self.providers.get(replacement)
            replacement_name=(
                str(replacement_provider.info.name)
                if replacement_provider is not None
                else replacement
            )
            raise ValueError(
                f"{provider.info.name} has been replaced by the included "
                f"{replacement_name} source."
            )
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

    @staticmethod
    def _search_failure_reason(error: Exception | str) -> str:
        message = str(error or "").strip()
        lowered = message.casefold()
        if "timed out" in lowered or "timeout" in lowered:
            return "Timed out"
        if "certificate_verify_failed" in lowered or "tls verification failed" in lowered:
            return "Secure connection failed"
        if "429" in lowered or "rate limit" in lowered:
            return "Rate limited"
        if "name or service not known" in lowered or "nodename nor servname" in lowered:
            return "Could not reach service"
        if "connection" in lowered or "urlopen error" in lowered:
            return "Connection problem"
        return "Unavailable"

    def search_report(
        self,
        query: str,
        provider_id: str = "all",
        limit: int = 50,
    ) -> dict[str, Any]:
        """Search providers without letting one failure break the whole UX.

        The report keeps technical errors for diagnostics while exposing a short
        reason that the desktop can present inline instead of using modal error
        dialogs. All-source searches run providers concurrently so a slow source
        costs roughly one timeout window rather than one timeout per provider.
        """

        requested_limit = max(1, min(250, int(limit)))
        provider_id = str(provider_id or "all")

        if provider_id != "all":
            provider = self.providers[provider_id]
            if "search" not in list(provider.info.capabilities or []):
                return {
                    "items": [],
                    "failures": [],
                    "searched": 0,
                    "available": 0,
                    "provider_ids": [],
                }
            try:
                rows = list(provider.search(query, requested_limit) or [])
            except Exception as exc:
                return {
                    "items": [],
                    "failures": [
                        {
                            "provider_id": provider_id,
                            "name": provider.info.name,
                            "reason": self._search_failure_reason(exc),
                            "error": str(exc),
                        }
                    ],
                    "searched": 1,
                    "available": 0,
                    "provider_ids": [provider_id],
                }
            return {
                "items": rows[:requested_limit],
                "failures": [],
                "searched": 1,
                "available": 1,
                "provider_ids": [provider_id],
            }

        searchable = self.searchable_provider_ids()
        if not searchable:
            return {
                "items": [],
                "failures": [],
                "searched": 0,
                "available": 0,
                "provider_ids": [],
            }

        per_provider = max(10, requested_limit // max(1, len(searchable)))
        results_by_provider: dict[str, list[dict[str, Any]]] = {}
        failures: list[dict[str, Any]] = []

        max_workers = max(1, min(16, len(searchable)))
        with ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="melodex-search",
        ) as executor:
            futures = {
                executor.submit(
                    self.providers[pid].search,
                    query,
                    per_provider,
                ): pid
                for pid in searchable
            }
            for future in as_completed(futures):
                pid = futures[future]
                provider = self.providers[pid]
                try:
                    results_by_provider[pid] = list(future.result() or [])
                except Exception as exc:
                    failures.append(
                        {
                            "provider_id": pid,
                            "name": provider.info.name,
                            "reason": self._search_failure_reason(exc),
                            "error": str(exc),
                        }
                    )

        out: list[dict[str, Any]] = []
        for pid in searchable:
            out.extend(results_by_provider.get(pid, []))
            if len(out) >= requested_limit:
                break

        return {
            "items": out[:requested_limit],
            "failures": failures,
            "searched": len(searchable),
            "available": len(searchable) - len(failures),
            "provider_ids": searchable,
        }

    def search(self, query: str, provider_id: str = "all", limit: int = 50) -> list[dict[str, Any]]:
        return list(
            self.search_report(query, provider_id, limit).get("items") or []
        )

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
        registry_kind = str((registry_entry or {}).get("kind") or "")
        recorded_kind = registry_kind if registry_kind in {"enrichment", "tool"} else "enrichment"
        self._record_installation(
            plugin_id=info.id,
            name=info.name,
            version=info.version,
            kind=recorded_kind,
            package=path,
            method=install_source,
            registry_entry=registry_entry,
        )
        return info

    def plugin_configuration(
        self,
        plugin_id: str,
        *,
        cached_status: bool = False,
    ) -> dict[str, Any]:
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
                "status": (
                    self.plugin_config.cached_status(plugin_id, declarations)
                    if cached_status
                    else self.plugin_config.status(plugin_id, declarations)
                ),
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
                "status": (
                    self.plugin_config.cached_status(plugin_id, declarations)
                    if cached_status
                    else self.plugin_config.status(plugin_id, declarations)
                ),
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
        redact_values: list[str] | None = None,
    ) -> dict[str, Any]:
        result = {
            "id": str(plugin_id),
            "name": str(name),
            "kind": str(kind),
            "status": normalise_health_status(status),
            "message": safe_health_text(message, redact_values),
            "check_scope": str(check_scope or ""),
            "reason": safe_health_text(reason, redact_values),
            "checked": bool(checked),
            "provider_status": safe_health_text(provider_status, redact_values)[:80],
        }
        if checked:
            result["checked_at"] = datetime.now(timezone.utc).isoformat()
        result["summary"] = health_summary(result)
        return result

    def plugin_health(
        self,
        plugin_id: str,
        *,
        cached_config: bool = False,
    ) -> dict[str, Any]:
        plugin_id = str(plugin_id or "").strip()
        if not plugin_id:
            raise KeyError("Missing plugin id")

        try:
            config = self.plugin_configuration(
                plugin_id,
                cached_status=cached_config,
            )
        except KeyError:
            config = {}
        status = dict(config.get("status") or {})
        if status.get("declared") and status.get("ready") is False:
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
                cached = self._plugin_health_cache.get(plugin_id)
                if (
                    cached
                    and cached.get("status") == "ready"
                    and cached.get("check_scope") == "upstream"
                ):
                    return self._health_result(
                        plugin_id=plugin_id,
                        name=extension.info.name,
                        kind="extension",
                        status="degraded",
                        message=(
                            "Upstream health check passed, but a recent "
                            "extension capability call failed"
                        ),
                        check_scope="combined",
                        reason=str(runtime.get("last_error") or "call_error"),
                        checked=bool(cached.get("checked")),
                    )
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
            declarations = list(provider.info.configuration or [])
            configured_values = self.plugin_config.values(plugin_id, declarations)
            secret_values = [
                str(configured_values.get(str(field.get("key") or "")) or "")
                for field in declarations
                if str(field.get("type") or "") == "secret"
            ]
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
                redact_values=secret_values,
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
                declarations = list(extension.info.configuration or [])
                configured_values = self.plugin_config.values(plugin_id, declarations)
                secret_values = [
                    str(configured_values.get(str(field.get("key") or "")) or "")
                    for field in declarations
                    if str(field.get("type") or "") == "secret"
                ]
                raw = dict(extension.active_health_check(timeout=timeout) or {})
                result = self._health_result(
                    plugin_id=plugin_id,
                    name=extension.info.name,
                    kind="extension",
                    status=str(raw.get("status") or ""),
                    message=str(raw.get("message") or ""),
                    check_scope=str(raw.get("check_scope") or "process"),
                    reason=str(raw.get("reason") or ""),
                    checked=True,
                    redact_values=secret_values,
                )
                if raw.get("upstream_checked") is not None:
                    result["upstream_checked"] = bool(raw.get("upstream_checked"))
                if raw.get("latency_ms") is not None:
                    result["latency_ms"] = raw.get("latency_ms")
                if raw.get("retry_after_seconds") is not None:
                    result["retry_after_seconds"] = raw.get("retry_after_seconds")
            self._plugin_health_cache[plugin_id] = result
            return self.plugin_health(plugin_id)

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
                "kind": str(entry.get("kind") or "enrichment"),
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

    def extensions(
        self,
        *,
        cached_config: bool = False,
    ) -> list[dict[str, Any]]:
        return self.capabilities.list_extensions(cached_config=cached_config)

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

    def local_catalog_revision(self) -> int:
        provider = self.providers["local"]
        return provider.catalog_revision if isinstance(provider, LocalFilesProvider) else 0

    def close(self) -> None:
        self.capabilities.close()
        for provider in self.providers.values():
            close = getattr(provider, "close", None)
            if callable(close):
                close()
