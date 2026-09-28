from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .provider import MusicProvider, ProviderInstaller
from .providers import JamendoProvider, LocalFilesProvider, UserStreamsProvider
from .resolver import UniversalResolver
from .capabilities import CapabilityBroker, ExtensionInfo


class ProviderManager:
    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self.settings_path = self.data_dir / "sources.json"
        self.installer = ProviderInstaller(self.data_dir / "providers")
        self.settings = self._load_settings()
        local_roots = [Path(x) for x in self.settings.get("local_roots", [])]
        self.providers: dict[str, MusicProvider] = {
            "local": LocalFilesProvider(local_roots),
            "jamendo": JamendoProvider(str(self.settings.get("jamendo_client_id", ""))),
            "streams": UserStreamsProvider(list(self.settings.get("user_streams", []))),
        }
        for provider in self.installer.load_installed():
            self.providers[provider.info.id] = provider
        self.resolver = UniversalResolver(self)
        self.capabilities = CapabilityBroker(self.data_dir)

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

    def install_package(self, path: Path) -> MusicProvider:
        folder = self.installer.install(path)
        manifest = json.loads((folder / "manifest.json").read_text("utf-8"))
        from .provider import ExternalProvider

        provider = ExternalProvider(folder, manifest)
        self.providers[provider.info.id] = provider
        return provider

    def search(self, query: str, provider_id: str = "all", limit: int = 50) -> list[dict[str, Any]]:
        if provider_id != "all":
            return self.providers[provider_id].search(query, limit)
        out: list[dict[str, Any]] = []
        per_provider = max(10, limit // max(1, len(self.providers)))
        for pid in self.provider_order():
            provider = self.providers[pid]
            try:
                out.extend(provider.search(query, per_provider))
            except Exception:
                continue
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

    def install_extension(self, path: Path) -> ExtensionInfo:
        return self.capabilities.install_package(path)

    def remove_extension(self, extension_id: str) -> bool:
        return self.capabilities.remove(extension_id)

    def extensions(self) -> list[dict[str, Any]]:
        return self.capabilities.list_extensions()

    def set_extension_enabled(self, extension_id: str, enabled: bool) -> None:
        self.capabilities.set_enabled(extension_id, enabled)

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
