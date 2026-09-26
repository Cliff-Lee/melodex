from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import zipfile
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class ProviderInfo:
    id: str
    name: str
    version: str = "1.0"
    description: str = ""
    capabilities: list[str] = field(default_factory=list)
    permissions: dict[str, Any] = field(default_factory=dict)


class MusicProvider(ABC):
    @property
    @abstractmethod
    def info(self) -> ProviderInfo: ...

    def configure(self, settings: dict[str, Any]) -> None:
        pass

    @abstractmethod
    def search(self, query: str, limit: int = 50) -> list[dict[str, Any]]: ...

    def browse(self, kind: str = "featured", limit: int = 50) -> list[dict[str, Any]]:
        return []

    @abstractmethod
    def resolve(self, track: dict[str, Any]) -> dict[str, Any]: ...


class ExternalProvider(MusicProvider):
    """MPP v1 JSON-RPC provider running out-of-process over stdio."""

    def __init__(self, folder: Path, manifest: dict[str, Any]):
        self.folder = Path(folder)
        self.manifest = dict(manifest)
        self._lock = threading.RLock()
        self._seq = 0
        self._proc: subprocess.Popen[str] | None = None

    @property
    def info(self) -> ProviderInfo:
        return ProviderInfo(
            id=str(self.manifest["id"]), name=str(self.manifest["name"]),
            version=str(self.manifest.get("version", "1.0")),
            description=str(self.manifest.get("description", "")),
            capabilities=list(self.manifest.get("capabilities", [])),
            permissions=dict(self.manifest.get("permissions", {})),
        )

    def _command(self) -> list[str]:
        entry = str((self.manifest.get("entrypoints") or {}).get("python", "provider.py"))
        return [sys.executable, "-u", str(self.folder / entry)]

    def _ensure(self) -> subprocess.Popen[str]:
        if self._proc and self._proc.poll() is None:
            return self._proc
        self._proc = subprocess.Popen(
            self._command(), cwd=str(self.folder), stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1,
            env={**os.environ, "MELODEX_PROVIDER_ID": self.info.id},
        )
        return self._proc

    def _rpc(self, method: str, params: dict[str, Any] | None = None) -> Any:
        with self._lock:
            proc = self._ensure()
            self._seq += 1
            rid = self._seq
            request = {"jsonrpc": "2.0", "id": rid, "method": method, "params": params or {}}
            assert proc.stdin and proc.stdout
            proc.stdin.write(json.dumps(request, ensure_ascii=False) + "\n")
            proc.stdin.flush()
            line = proc.stdout.readline()
            if not line:
                raise RuntimeError(f"Provider {self.info.name} stopped unexpectedly")
            response = json.loads(line)
            if response.get("error"):
                raise RuntimeError(str(response["error"].get("message", "Provider error")))
            return response.get("result")

    def search(self, query: str, limit: int = 50) -> list[dict[str, Any]]:
        result = self._rpc("catalog.search", {"query": query, "types": ["track"], "limit": limit, "cursor": None}) or {}
        return [_normalise_track(x, self.info.id) for x in result.get("items", []) if isinstance(x, dict)]

    def resolve(self, track: dict[str, Any]) -> dict[str, Any]:
        result = self._rpc("playback.resolve", {"track_id": str(track.get("track_id") or track.get("id") or "")}) or {}
        out = dict(track)
        out.update(result)
        return out

    def close(self) -> None:
        if self._proc and self._proc.poll() is None:
            self._proc.terminate()


def _normalise_track(raw: dict[str, Any], provider_id: str) -> dict[str, Any]:
    item = dict(raw)
    track_id = str(item.get("track_id") or item.get("id") or "")
    item.update({
        "provider_id": provider_id,
        "track_id": track_id,
        "title": str(item.get("title") or item.get("name") or "Unknown track"),
        "artist": str(item.get("artist") or item.get("artist_name") or "Unknown artist"),
        "album": str(item.get("album") or item.get("album_name") or ""),
        "rel": str(item.get("rel") or f"{provider_id}:{track_id}"),
    })
    return item


class ProviderInstaller:
    def __init__(self, providers_dir: Path):
        self.providers_dir = Path(providers_dir)
        self.providers_dir.mkdir(parents=True, exist_ok=True)

    def install(self, package: Path) -> Path:
        package = Path(package)
        if package.suffix.lower() not in {".mdxprovider", ".zip"}:
            raise ValueError("Provider packages must use .mdxprovider")
        with zipfile.ZipFile(package) as zf:
            names = zf.namelist()
            manifest_name = next((n for n in names if n.rstrip("/").endswith("manifest.json")), None)
            if not manifest_name:
                raise ValueError("Provider package has no manifest.json")
            manifest = json.loads(zf.read(manifest_name))
            pid = str(manifest.get("id", "")).strip()
            if not pid or ".." in pid or "/" in pid or "\\" in pid:
                raise ValueError("Invalid provider id")
            dest = self.providers_dir / pid
            if dest.exists():
                import shutil
                shutil.rmtree(dest)
            dest.mkdir(parents=True)
            for member in zf.infolist():
                target = (dest / member.filename).resolve()
                if not str(target).startswith(str(dest.resolve())):
                    raise ValueError("Unsafe path in provider package")
                zf.extract(member, dest)
        return dest

    def load_installed(self) -> list[ExternalProvider]:
        result: list[ExternalProvider] = []
        for manifest_path in self.providers_dir.glob("*/manifest.json"):
            try:
                manifest = json.loads(manifest_path.read_text("utf-8"))
                result.append(ExternalProvider(manifest_path.parent, manifest))
            except Exception:
                continue
        return result
