from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .provider import MusicProvider, ProviderInstaller
from .providers import JamendoProvider, LocalFilesProvider


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
        }
        for provider in self.installer.load_installed():
            self.providers[provider.info.id] = provider

    def _load_settings(self) -> dict[str, Any]:
        try:
            return json.loads(self.settings_path.read_text("utf-8"))
        except Exception:
            return {}

    def save(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.settings_path.write_text(json.dumps(self.settings, indent=2, ensure_ascii=False), "utf-8")

    def set_local_roots(self, roots: list[Path]) -> int:
        p = self.providers["local"]
        assert isinstance(p, LocalFilesProvider)
        p.set_roots(roots)
        self.settings["local_roots"] = [str(x) for x in roots]
        self.save()
        return len(p.tracks)

    def set_jamendo_client_id(self, client_id: str) -> None:
        p = self.providers["jamendo"]
        p.configure({"client_id": client_id})
        self.settings["jamendo_client_id"] = client_id.strip()
        self.save()

    def install_package(self, path: Path) -> MusicProvider:
        folder = self.installer.install(path)
        manifest = json.loads((folder / "manifest.json").read_text("utf-8"))
        from .provider import ExternalProvider
        p = ExternalProvider(folder, manifest)
        self.providers[p.info.id] = p
        return p

    def search(self, query: str, provider_id: str = "all", limit: int = 50) -> list[dict[str, Any]]:
        if provider_id != "all":
            return self.providers[provider_id].search(query, limit)
        out: list[dict[str, Any]] = []
        for pid, provider in self.providers.items():
            try:
                out.extend(provider.search(query, max(10, limit // max(1, len(self.providers)))))
            except Exception:
                continue
        return out[:limit]

    def browse(self, provider_id: str, kind: str = "featured", limit: int = 50) -> list[dict[str, Any]]:
        return self.providers[provider_id].browse(kind, limit)

    def resolve(self, track: dict[str, Any]) -> dict[str, Any]:
        pid = str(track.get("provider_id") or "local")
        if pid not in self.providers:
            raise RuntimeError(f"Source '{pid}' is not installed")
        return self.providers[pid].resolve(track)

    def local_catalog(self) -> list[dict[str, Any]]:
        p = self.providers["local"]
        return p.tracks if isinstance(p, LocalFilesProvider) else []

    def close(self) -> None:
        for provider in self.providers.values():
            close = getattr(provider, "close", None)
            if callable(close):
                close()
