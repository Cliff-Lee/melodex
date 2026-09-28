from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import sys
import threading
import zipfile
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .process_env import scrubbed_child_env


@dataclass(slots=True)
class ProviderInfo:
    id: str
    name: str
    version: str = "1.0"
    description: str = ""
    capabilities: list[str] = field(default_factory=list)
    permissions: dict[str, Any] = field(default_factory=dict)
    configuration: list[dict[str, Any]] = field(default_factory=list)


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

    def refresh(self, track: dict[str, Any]) -> dict[str, Any]:
        return self.resolve(track)


class ExternalProvider(MusicProvider):
    """MPP JSON-RPC provider running out-of-process over stdio."""

    def __init__(self, folder: Path, manifest: dict[str, Any]):
        self.folder = Path(folder)
        self.manifest = dict(manifest)
        self._lock = threading.RLock()
        self._seq = 0
        self._proc: subprocess.Popen[str] | None = None
        self._config: dict[str, Any] = {}

    @property
    def info(self) -> ProviderInfo:
        return ProviderInfo(
            id=str(self.manifest["id"]),
            name=str(self.manifest["name"]),
            version=str(self.manifest.get("version", "1.0")),
            description=str(self.manifest.get("description", "")),
            capabilities=list(self.manifest.get("capabilities", [])),
            permissions=dict(self.manifest.get("permissions", {})),
            configuration=list(self.manifest.get("configuration") or []),
        )

    def _platform_entrypoint_key(self) -> str:
        system = platform.system().casefold()
        machine = platform.machine().casefold()
        arch = "arm64" if machine in {"arm64", "aarch64"} else "x86_64"
        prefix = {"darwin": "macos", "windows": "windows", "linux": "linux"}.get(
            system, system
        )
        return f"{prefix}-{arch}"

    def _command(self) -> list[str]:
        entries = dict(self.manifest.get("entrypoints") or {})
        python_entry = str(entries.get("python") or "").strip()
        if python_entry:
            return [sys.executable, "-u", str(self.folder / python_entry)]
        native = str(
            entries.get(self._platform_entrypoint_key()) or entries.get("executable") or ""
        )
        if native:
            return [str(self.folder / native)]
        return [sys.executable, "-u", str(self.folder / "provider.py")]

    def _ensure(self) -> subprocess.Popen[str]:
        if self._proc and self._proc.poll() is None:
            return self._proc
        env = scrubbed_child_env(
            identifier_key="MELODEX_PROVIDER_ID",
            identifier=self.info.id,
        )
        paths = [str(self.folder)]
        vendor = self.folder / "vendor"
        if vendor.is_dir():
            paths.insert(0, str(vendor))
        env["PYTHONPATH"] = os.pathsep.join(paths)
        self._proc = subprocess.Popen(
            self._command(),
            cwd=str(self.folder),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            env=env,
        )
        return self._proc

    def configure(self, settings: dict[str, Any]) -> None:
        with self._lock:
            self._config = dict(settings or {})

    def _rpc(self, method: str, params: dict[str, Any] | None = None) -> Any:
        with self._lock:
            proc = self._ensure()
            self._seq += 1
            rid = self._seq
            request_params = dict(params or {})
            if self._config:
                request_params["_melodex_config"] = dict(self._config)
            request = {"jsonrpc": "2.0", "id": rid, "method": method, "params": request_params}
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
        result = self._rpc(
            "catalog.search",
            {"query": query, "types": ["track"], "limit": limit, "cursor": None},
        ) or {}
        return [
            _normalise_track(item, self.info.id)
            for item in result.get("items", [])
            if isinstance(item, dict)
        ]

    def _playback_params(self, track: dict[str, Any]) -> dict[str, Any]:
        track_id = str(
            track.get("track_id")
            or track.get("provider_track_id")
            or track.get("id")
            or ""
        )
        return {"track_id": track_id, "provider_track_id": track_id, "purpose": "stream"}

    def _merge_playback(
        self, track: dict[str, Any], resource: dict[str, Any]
    ) -> dict[str, Any]:
        out = dict(track)
        out.update(resource)
        hosts = list((self.info.permissions or {}).get("network_hosts") or [])
        out["_playback_allowed_hosts"] = [str(x) for x in hosts]
        return out

    def resolve(self, track: dict[str, Any]) -> dict[str, Any]:
        result = self._rpc("playback.resolve", self._playback_params(track)) or {}
        return self._merge_playback(track, dict(result))

    def refresh(self, track: dict[str, Any]) -> dict[str, Any]:
        params = self._playback_params(track)
        token = str(track.get("refresh_token") or "")
        if token:
            params["refresh_token"] = token
        try:
            result = self._rpc("playback.refresh", params) or {}
            return self._merge_playback(track, dict(result))
        except RuntimeError:
            return self.resolve(track)

    def close(self) -> None:
        if self._proc and self._proc.poll() is None:
            self._proc.terminate()


def _normalise_track(raw: dict[str, Any], provider_id: str) -> dict[str, Any]:
    item = dict(raw)
    track_id = str(
        item.get("track_id") or item.get("provider_track_id") or item.get("id") or ""
    )
    item.update(
        {
            "provider_id": provider_id,
            "track_id": track_id,
            "provider_track_id": str(item.get("provider_track_id") or track_id),
            "title": str(item.get("title") or item.get("name") or "Unknown track"),
            "artist": str(item.get("artist") or item.get("artist_name") or "Unknown artist"),
            "album": str(item.get("album") or item.get("album_name") or ""),
            "rel": str(item.get("rel") or f"{provider_id}:{track_id}"),
        }
    )
    return item


class ProviderInstaller:
    def __init__(self, providers_dir: Path):
        self.providers_dir = Path(providers_dir)
        self.providers_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _manifest_from_archive(zf: zipfile.ZipFile) -> tuple[str, dict[str, Any]]:
        manifest_name = next(
            (
                name
                for name in zf.namelist()
                if name.rstrip("/").endswith("manifest.json")
            ),
            None,
        )
        if not manifest_name:
            raise ValueError("Provider package has no manifest.json")
        manifest = json.loads(zf.read(manifest_name))
        if not isinstance(manifest, dict):
            raise ValueError("manifest.json must contain a JSON object")
        pid = str(manifest.get("id", "")).strip()
        if not pid or ".." in pid or "/" in pid or "\\" in pid:
            raise ValueError("Invalid provider id")
        return manifest_name, manifest

    def install(self, package: Path) -> Path:
        package = Path(package)
        if package.suffix.lower() not in {".mdxprovider", ".zip"}:
            raise ValueError("Provider packages must use .mdxprovider")
        with zipfile.ZipFile(package) as zf:
            manifest_name, manifest = self._manifest_from_archive(zf)
            pid = str(manifest["id"])
            dest = self.providers_dir / pid
            if dest.exists():
                shutil.rmtree(dest)
            dest.mkdir(parents=True)

            prefix = Path(manifest_name).parent
            for member in zf.infolist():
                source = Path(member.filename)
                try:
                    relative = (
                        source.relative_to(prefix)
                        if str(prefix) != "."
                        else source
                    )
                except ValueError:
                    continue
                if not relative.parts or relative.name == "":
                    continue
                unix_mode = (member.external_attr >> 16) & 0o170000
                if unix_mode == 0o120000:
                    raise ValueError("Symlinks are not allowed in provider packages")
                target = (dest / relative).resolve()
                if not target.is_relative_to(dest.resolve()):
                    raise ValueError("Unsafe path in provider package")
                if member.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(member) as source_file, target.open("wb") as output:
                    shutil.copyfileobj(source_file, output)

            if not (dest / "manifest.json").is_file():
                raise ValueError("Provider package did not install manifest.json")
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
