from __future__ import annotations

import json
import os
import platform
import queue
import shutil
import subprocess
import sys
import threading
import time
import zipfile
from collections import deque
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .process_env import scrubbed_child_env
from .child_host import python_child_command
from .plugin_config import normalise_configuration
from .package_safety import (
    entrypoint_errors,
    extract_archive,
    replace_directory,
    resolve_entrypoint,
    staged_install_dir,
)


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

    def recommend(self, seed: dict[str, Any], limit: int = 25) -> list[dict[str, Any]]:
        return []

    def health_check(self, timeout: float = 8.0) -> dict[str, Any]:
        return {
            "status": "ready",
            "message": "Built-in provider is available",
            "check_scope": "local",
        }

    @abstractmethod
    def resolve(self, track: dict[str, Any]) -> dict[str, Any]: ...

    def refresh(self, track: dict[str, Any]) -> dict[str, Any]:
        return self.resolve(track)


class ExternalProvider(MusicProvider):
    """MPP JSON-RPC provider running out-of-process over stdio."""

    def __init__(
        self,
        folder: Path,
        manifest: dict[str, Any],
        timeout: float = 12.0,
    ):
        self.folder = Path(folder)
        self.manifest = dict(manifest)
        normalise_configuration(self.manifest.get("configuration"))
        self._lock = threading.RLock()
        self._seq = 0
        self._proc: subprocess.Popen[str] | None = None
        self.timeout = float(timeout)
        self._stdout: queue.Queue[str | None] = queue.Queue()
        self._stderr: deque[str] = deque(maxlen=30)
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
            configuration=normalise_configuration(self.manifest.get("configuration")),
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
            return python_child_command(resolve_entrypoint(self.folder, python_entry))
        native = str(
            entries.get(self._platform_entrypoint_key()) or entries.get("executable") or ""
        )
        if native:
            target = resolve_entrypoint(self.folder, native)
            if os.name != "nt" and not os.access(target, os.X_OK):
                raise RuntimeError(f"Provider native entrypoint is not executable: {target.name}")
            return [str(target)]
        return python_child_command(resolve_entrypoint(self.folder, "provider.py"))

    def _drain_stdout(self, proc: subprocess.Popen[str]) -> None:
        assert proc.stdout
        try:
            for line in proc.stdout:
                self._stdout.put(line)
        finally:
            self._stdout.put(None)

    def _drain_stderr(self, proc: subprocess.Popen[str]) -> None:
        assert proc.stderr
        for line in proc.stderr:
            value = line.rstrip()
            if value:
                self._stderr.append(value)

    def _ensure(self) -> subprocess.Popen[str]:
        if self._proc and self._proc.poll() is None:
            return self._proc
        self._stdout = queue.Queue()
        self._stderr.clear()
        env = scrubbed_child_env(
            identifier_key="MELODEX_PROVIDER_ID",
            identifier=self.info.id,
        )
        paths = [str(self.folder)]
        vendor = self.folder / "vendor"
        if vendor.is_dir():
            paths.insert(0, str(vendor))
        env["PYTHONPATH"] = os.pathsep.join(paths)
        env["PYTHONUNBUFFERED"] = "1"
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
        threading.Thread(
            target=self._drain_stdout, args=(self._proc,), daemon=True
        ).start()
        threading.Thread(
            target=self._drain_stderr, args=(self._proc,), daemon=True
        ).start()
        return self._proc

    def _stop(self) -> None:
        proc = self._proc
        self._proc = None
        if not proc or proc.poll() is not None:
            return
        proc.terminate()
        try:
            proc.wait(timeout=1.5)
        except subprocess.TimeoutExpired:
            proc.kill()

    def configure(self, settings: dict[str, Any]) -> None:
        with self._lock:
            self._config = dict(settings or {})

    def _rpc(
        self,
        method: str,
        params: dict[str, Any] | None = None,
        timeout: float | None = None,
    ) -> Any:
        with self._lock:
            proc = self._ensure()
            self._seq += 1
            rid = self._seq
            request_params = dict(params or {})
            if self._config:
                request_params["_melodex_config"] = dict(self._config)
            request = {
                "jsonrpc": "2.0",
                "id": rid,
                "method": method,
                "params": request_params,
            }
            assert proc.stdin
            try:
                proc.stdin.write(json.dumps(request, ensure_ascii=False) + "\n")
                proc.stdin.flush()
            except (BrokenPipeError, OSError) as exc:
                self._stop()
                raise RuntimeError(
                    f"Provider {self.info.name} stopped: {exc}"
                ) from exc

            deadline = time.monotonic() + float(timeout or self.timeout)
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    self._stop()
                    raise RuntimeError(
                        f"Provider {self.info.name} timed out after "
                        f"{float(timeout or self.timeout):.1f}s"
                    )
                try:
                    line = self._stdout.get(timeout=remaining)
                except queue.Empty as exc:
                    self._stop()
                    raise RuntimeError(
                        f"Provider {self.info.name} timed out"
                    ) from exc
                if line is None:
                    details = " | ".join(list(self._stderr)[-3:])
                    self._stop()
                    suffix = f": {details}" if details else ""
                    raise RuntimeError(
                        f"Provider {self.info.name} stopped unexpectedly{suffix}"
                    )
                try:
                    response = json.loads(line)
                except json.JSONDecodeError as exc:
                    self._stop()
                    raise RuntimeError(
                        f"Provider {self.info.name} wrote non-JSON data to stdout"
                    ) from exc
                if response.get("id") != rid:
                    continue
                if response.get("error"):
                    error = response.get("error") or {}
                    message = (
                        error.get("message")
                        if isinstance(error, dict)
                        else str(error)
                    )
                    raise RuntimeError(str(message or "Provider error"))
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

    def recommend(self, seed: dict[str, Any], limit: int = 25) -> list[dict[str, Any]]:
        result = self._rpc(
            "recommendations.get",
            {
                "seed": {
                    "artist": str(seed.get("artist") or ""),
                    "title": str(seed.get("title") or ""),
                    "album": str(seed.get("album") or ""),
                    "isrc": seed.get("isrc"),
                    "musicbrainz_recording_id": seed.get("musicbrainz_recording_id"),
                },
                "limit": max(1, min(100, int(limit))),
                "cursor": None,
            },
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
        hosts = [str(x) for x in list((self.info.permissions or {}).get("network_hosts") or [])]
        if hosts:
            url = str(out.get("stream_url") or out.get("url") or "").strip()
            host = (urlparse(url).hostname or "").strip().casefold()
            if host and host not in {value.casefold().strip(".") for value in hosts}:
                # The provider selected this exact media origin. Add only that
                # host; redirects are still checked against the resulting list.
                hosts.append(host)
        out["_playback_allowed_hosts"] = hosts
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

    def health_check(self, timeout: float = 8.0) -> dict[str, Any]:
        try:
            result = self._rpc(
                "provider.health",
                {},
                timeout=max(0.5, float(timeout)),
            )
        except Exception as exc:
            message = str(exc)
            timed_out = "timed out" in message.casefold()
            return {
                "status": "unavailable" if timed_out else "error",
                "message": (
                    f"Provider health check timed out after {float(timeout):.1f}s"
                    if timed_out
                    else "Provider health check failed"
                ),
                "check_scope": "provider",
                "reason": "timeout" if timed_out else "provider_error",
            }
        if not isinstance(result, dict):
            return {
                "status": "error",
                "message": "Provider returned an invalid health response",
                "check_scope": "provider",
                "reason": "protocol_error",
            }
        out = dict(result)
        out["status"] = str(out.get("status") or "unknown")
        out["check_scope"] = "provider"
        return out

    def close(self) -> None:
        with self._lock:
            self._stop()



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
        candidates = [
            name
            for name in zf.namelist()
            if not name.endswith("/") and Path(name).name == "manifest.json"
        ]
        if not candidates:
            raise ValueError("Provider package has no manifest.json")
        if len(candidates) != 1:
            raise ValueError("Provider package must contain exactly one manifest.json")
        manifest_name = candidates[0]
        manifest = json.loads(zf.read(manifest_name))
        if not isinstance(manifest, dict):
            raise ValueError("manifest.json must contain a JSON object")
        pid = str(manifest.get("id", "")).strip()
        if not pid or ".." in pid or "/" in pid or "\\" in pid:
            raise ValueError("Invalid provider id")
        normalise_configuration(manifest.get("configuration"))
        errors = entrypoint_errors(manifest.get("entrypoints"))
        if errors:
            raise ValueError("Invalid provider entrypoints: " + "; ".join(errors))
        return manifest_name, manifest

    def install(self, package: Path) -> Path:
        package = Path(package)
        if package.suffix.lower() not in {".mdxprovider", ".zip"}:
            raise ValueError("Provider packages must use .mdxprovider")
        staged: Path | None = None
        try:
            with zipfile.ZipFile(package) as zf:
                manifest_name, manifest = self._manifest_from_archive(zf)
                pid = str(manifest["id"])
                dest = self.providers_dir / pid
                staged = staged_install_dir(self.providers_dir, pid)
                extract_archive(
                    zf,
                    prefix=Path(manifest_name).parent,
                    destination=staged,
                )
                if not (staged / "manifest.json").is_file():
                    raise ValueError("Provider package did not install manifest.json")
                # Re-parse the extracted descriptor so the exact installed file
                # is what gets validated before replacing a working version.
                extracted = json.loads((staged / "manifest.json").read_text("utf-8"))
                if not isinstance(extracted, dict):
                    raise ValueError("Installed manifest.json is invalid")
                normalise_configuration(extracted.get("configuration"))
                errors = entrypoint_errors(extracted.get("entrypoints"))
                if errors:
                    raise ValueError("Invalid provider entrypoints: " + "; ".join(errors))
                replace_directory(staged, dest)
                staged = None
                return dest
        finally:
            if staged is not None and staged.exists():
                shutil.rmtree(staged, ignore_errors=True)

    def load_installed(self) -> list[ExternalProvider]:
        result: list[ExternalProvider] = []
        for manifest_path in self.providers_dir.glob("*/manifest.json"):
            try:
                manifest = json.loads(manifest_path.read_text("utf-8"))
                result.append(ExternalProvider(manifest_path.parent, manifest))
            except Exception:
                continue
        return result
