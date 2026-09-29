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
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .process_env import scrubbed_child_env
from .plugin_config import PluginConfigBroker, normalise_configuration


_METHODS = {
    "identity": "identity.resolve",
    "metadata": "metadata.enrich",
    "artwork": "artwork.lookup",
    "lyrics": "lyrics.lookup",
}


@dataclass(slots=True)
class ExtensionContract:
    capability: str
    contract_version: str
    method: str

    def as_dict(self) -> dict[str, str]:
        return {
            "capability": self.capability,
            "contract_version": self.contract_version,
            "method": self.method,
        }


@dataclass(slots=True)
class ExtensionInfo:
    id: str
    name: str
    version: str = "0.1.0"
    description: str = ""
    contracts: list[ExtensionContract] = field(default_factory=list)
    permissions: dict[str, Any] = field(default_factory=dict)
    configuration: list[dict[str, Any]] = field(default_factory=list)
    health_contract: dict[str, str] = field(default_factory=dict)

    @property
    def capabilities(self) -> list[str]:
        return [item.capability for item in self.contracts]

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "capabilities": self.capabilities,
            "contracts": [item.as_dict() for item in self.contracts],
            "permissions": dict(self.permissions),
            "configuration": list(self.configuration),
            "health": dict(self.health_contract),
        }


def validate_descriptor(descriptor: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if str(descriptor.get("schema_version") or "") != "0.1":
        errors.append("schema_version must be '0.1'")
    extension_id = str(descriptor.get("extension_id") or "").strip()
    if not extension_id:
        errors.append("extension_id is required")
    if extension_id and (
        ".." in extension_id or "/" in extension_id or "\\" in extension_id
    ):
        errors.append("extension_id contains an unsafe path sequence")

    contracts = descriptor.get("contracts")
    if not isinstance(contracts, list) or not contracts:
        errors.append("contracts must contain at least one capability contract")
        return errors

    seen: set[str] = set()
    for index, raw in enumerate(contracts):
        if not isinstance(raw, dict):
            errors.append(f"contracts[{index}] must be an object")
            continue
        capability = str(raw.get("capability") or "")
        version = str(raw.get("contract_version") or "")
        method = str(raw.get("method") or "")
        if capability not in _METHODS:
            errors.append(f"contracts[{index}].capability is unsupported: {capability!r}")
        if version != "0.1":
            errors.append(f"contracts[{index}].contract_version must be '0.1'")
        expected = _METHODS.get(capability)
        if expected and method != expected:
            errors.append(
                f"contracts[{index}].method must be {expected!r} for {capability!r}"
            )
        if capability in seen:
            errors.append(f"duplicate capability contract: {capability}")
        seen.add(capability)

    health = descriptor.get("health")
    if health is not None:
        if not isinstance(health, dict):
            errors.append("health must be an object when present")
        else:
            if str(health.get("contract_version") or "") != "0.1":
                errors.append("health.contract_version must be '0.1'")
            if str(health.get("method") or "") != "extension.health":
                errors.append("health.method must be 'extension.health'")

    entrypoints = descriptor.get("entrypoints")
    if entrypoints is not None and not isinstance(entrypoints, dict):
        errors.append("entrypoints must be an object when present")
    permissions = descriptor.get("permissions")
    if permissions is not None and not isinstance(permissions, dict):
        errors.append("permissions must be an object when present")
    try:
        normalise_configuration(descriptor.get("configuration"))
    except ValueError as exc:
        errors.append(str(exc))
    return errors


class ExternalExtension:
    """Experimental v0.1 capability extension running over JSON-RPC/stdin/stdout."""

    def __init__(self, folder: Path, descriptor: dict[str, Any], timeout: float = 12.0):
        self.folder = Path(folder)
        self.descriptor = dict(descriptor)
        errors = validate_descriptor(self.descriptor)
        if errors:
            raise ValueError("; ".join(errors))
        self.timeout = float(timeout)
        self._lock = threading.RLock()
        self._seq = 0
        self._proc: subprocess.Popen[str] | None = None
        self._stdout: queue.Queue[str | None] = queue.Queue()
        self._stderr: deque[str] = deque(maxlen=30)
        self._health_lock = threading.Lock()
        self._config: dict[str, Any] = {}
        self._health: dict[str, Any] = {
            "status": "idle",
            "calls": 0,
            "successes": 0,
            "failures": 0,
            "consecutive_failures": 0,
            "last_error": "",
        }

    @property
    def info(self) -> ExtensionInfo:
        contracts = [
            ExtensionContract(
                capability=str(raw.get("capability") or ""),
                contract_version=str(raw.get("contract_version") or ""),
                method=str(raw.get("method") or ""),
            )
            for raw in list(self.descriptor.get("contracts") or [])
            if isinstance(raw, dict)
        ]
        extension_id = str(self.descriptor["extension_id"])
        return ExtensionInfo(
            id=extension_id,
            name=str(self.descriptor.get("name") or extension_id),
            version=str(self.descriptor.get("version") or "0.1.0"),
            description=str(self.descriptor.get("description") or ""),
            contracts=contracts,
            permissions=dict(self.descriptor.get("permissions") or {}),
            configuration=normalise_configuration(self.descriptor.get("configuration")),
            health_contract={
                str(key): str(value)
                for key, value in dict(self.descriptor.get("health") or {}).items()
            },
        )

    def configure(self, settings: dict[str, Any]) -> None:
        with self._lock:
            self._config = dict(settings or {})

    def contract(self, capability: str) -> ExtensionContract | None:
        return next(
            (item for item in self.info.contracts if item.capability == capability),
            None,
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
        entries = dict(self.descriptor.get("entrypoints") or {})
        python_entry = str(entries.get("python") or "").strip()
        if python_entry:
            return [sys.executable, "-u", str(self.folder / python_entry)]
        if not entries and (self.folder / "plugin.py").is_file():
            return [sys.executable, "-u", str(self.folder / "plugin.py")]
        native = str(
            entries.get(self._platform_entrypoint_key())
            or entries.get("executable")
            or ""
        ).strip()
        if native:
            return [str(self.folder / native)]
        raise RuntimeError(f"Extension {self.info.name} has no runnable entrypoint")

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
            identifier_key="MELODEX_EXTENSION_ID",
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

    def _rpc_method(
        self,
        method: str,
        params: dict[str, Any],
        timeout: float | None = None,
    ) -> Any:
        with self._lock:
            proc = self._ensure()
            self._seq += 1
            request_id = self._seq
            request_params = dict(params)
            if self._config:
                request_params["_melodex_config"] = dict(self._config)
            request = {
                "jsonrpc": "2.0",
                "id": request_id,
                "method": contract.method,
                "params": request_params,
            }
            assert proc.stdin
            try:
                proc.stdin.write(json.dumps(request, ensure_ascii=False) + "\n")
                proc.stdin.flush()
            except (BrokenPipeError, OSError) as exc:
                self._stop()
                raise RuntimeError(f"Extension {self.info.name} stopped: {exc}") from exc

            deadline = time.monotonic() + float(timeout or self.timeout)
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    self._stop()
                    raise RuntimeError(
                        f"Extension {self.info.name} timed out after "
                        f"{float(timeout or self.timeout):.1f}s"
                    )
                try:
                    line = self._stdout.get(timeout=remaining)
                except queue.Empty as exc:
                    self._stop()
                    raise RuntimeError(
                        f"Extension {self.info.name} timed out"
                    ) from exc
                if line is None:
                    details = " | ".join(list(self._stderr)[-3:])
                    self._stop()
                    suffix = f": {details}" if details else ""
                    raise RuntimeError(
                        f"Extension {self.info.name} stopped unexpectedly{suffix}"
                    )
                try:
                    response = json.loads(line)
                except json.JSONDecodeError as exc:
                    self._stop()
                    raise RuntimeError(
                        f"Extension {self.info.name} wrote non-JSON data to stdout"
                    ) from exc
                if response.get("id") != request_id:
                    continue
                if response.get("error"):
                    error = response.get("error") or {}
                    message = (
                        error.get("message")
                        if isinstance(error, dict)
                        else str(error)
                    )
                    raise RuntimeError(str(message or "Extension error"))
                return response.get("result")

    def _call_once(
        self,
        capability: str,
        params: dict[str, Any],
        timeout: float | None = None,
    ) -> Any:
        contract = self.contract(capability)
        if contract is None:
            raise RuntimeError(
                f"Extension {self.info.name} does not implement {capability}"
            )
        return self._rpc_method(contract.method, params, timeout=timeout)

    def active_health_check(self, timeout: float = 8.0) -> dict[str, Any]:
        declaration = dict(self.info.health_contract or {})
        if not declaration:
            return self.process_check()
        try:
            raw = self._rpc_method(
                str(declaration.get("method") or "extension.health"),
                {"schema_version": "0.1", "check": "live"},
                timeout=max(0.5, float(timeout)),
            )
        except Exception as exc:
            category = self._diagnostic_error(exc)
            return {
                "status": "unavailable" if category in {"timeout", "process_error"} else "error",
                "message": "Extension health check failed",
                "check_scope": "upstream",
                "reason": category,
                "upstream_checked": False,
            }
        if not isinstance(raw, dict):
            return {
                "status": "error",
                "message": "Extension returned an invalid health response",
                "check_scope": "upstream",
                "reason": "protocol_error",
                "upstream_checked": False,
            }
        status = str(raw.get("status") or "error")
        upstream_checked = bool(raw.get("upstream_checked"))
        return {
            "status": status,
            "message": str(raw.get("message") or ""),
            "check_scope": "upstream" if upstream_checked else "extension",
            "reason": "",
            "upstream_checked": upstream_checked,
            "latency_ms": raw.get("latency_ms"),
            "retry_after_seconds": raw.get("retry_after_seconds"),
        }

    @staticmethod
    def _diagnostic_error(exc: Exception) -> str:
        text = str(exc).casefold()
        if "timed out" in text:
            return "timeout"
        if "non-json" in text:
            return "protocol_error"
        if "stopped" in text or "broken pipe" in text:
            return "process_error"
        return "call_error"

    def health(self) -> dict[str, Any]:
        with self._health_lock:
            health = dict(self._health)
        health["process_running"] = bool(
            self._proc is not None and self._proc.poll() is None
        )
        return health

    def process_check(self) -> dict[str, Any]:
        """Verify the extension can start without claiming upstream connectivity."""
        try:
            proc = self._ensure()
        except Exception:
            return {
                "status": "error",
                "message": "Extension process could not start",
                "check_scope": "process",
                "reason": "process_start_failed",
            }
        time.sleep(0.05)
        if proc.poll() is not None:
            details = " | ".join(list(self._stderr)[-3:])
            return {
                "status": "error",
                "message": "Extension process exited during startup",
                "check_scope": "process",
                "reason": "process_exited",
                "details": details[:500] if details else "",
            }
        return {
            "status": "ready",
            "message": (
                "Extension process started successfully. "
                "Upstream service access is tested when the extension is used."
            ),
            "check_scope": "process",
        }

    def call(
        self,
        capability: str,
        params: dict[str, Any],
        timeout: float | None = None,
    ) -> Any:
        with self._health_lock:
            self._health["calls"] += 1
            self._health["status"] = "running"
        try:
            result = self._call_once(capability, params, timeout=timeout)
        except Exception as exc:
            with self._health_lock:
                self._health["failures"] += 1
                self._health["consecutive_failures"] += 1
                self._health["status"] = "error"
                self._health["last_error"] = self._diagnostic_error(exc)
            raise
        else:
            with self._health_lock:
                self._health["successes"] += 1
                self._health["consecutive_failures"] = 0
                self._health["status"] = "ok"
                self._health["last_error"] = ""
            return result

    def close(self) -> None:
        with self._lock:
            self._stop()


class ExtensionInstaller:
    def __init__(self, extensions_dir: Path):
        self.extensions_dir = Path(extensions_dir)
        self.extensions_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _descriptor_from_archive(
        archive: zipfile.ZipFile,
    ) -> tuple[str, dict[str, Any]]:
        names = archive.namelist()
        descriptor_name = next(
            (
                name
                for name in names
                if name.rstrip("/").endswith("capabilities.json")
            ),
            None,
        )
        if not descriptor_name:
            raise ValueError("Extension package has no capabilities.json")
        descriptor = json.loads(archive.read(descriptor_name))
        if not isinstance(descriptor, dict):
            raise ValueError("capabilities.json must contain a JSON object")
        errors = validate_descriptor(descriptor)
        if errors:
            raise ValueError("Invalid capabilities.json: " + "; ".join(errors))
        return descriptor_name, descriptor

    def install(self, package: Path) -> Path:
        package = Path(package)
        if package.suffix.lower() not in {".mdxplugin", ".zip"}:
            raise ValueError("Extension packages must use .mdxplugin")
        with zipfile.ZipFile(package) as archive:
            descriptor_name, descriptor = self._descriptor_from_archive(archive)
            extension_id = str(descriptor["extension_id"])
            destination = self.extensions_dir / extension_id
            if destination.exists():
                shutil.rmtree(destination)
            destination.mkdir(parents=True)
            prefix = Path(descriptor_name).parent
            for member in archive.infolist():
                source = Path(member.filename)
                try:
                    relative = source.relative_to(prefix) if str(prefix) != "." else source
                except ValueError:
                    continue
                if not relative.parts or relative.name == "":
                    continue
                # Reject symlink entries and path traversal.
                unix_mode = (member.external_attr >> 16) & 0o170000
                if unix_mode == 0o120000:
                    raise ValueError("Symlinks are not allowed in extension packages")
                target = (destination / relative).resolve()
                if not target.is_relative_to(destination.resolve()):
                    raise ValueError("Unsafe path in extension package")
                if member.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(member) as source_file, target.open("wb") as out:
                    shutil.copyfileobj(source_file, out)
            if not (destination / "capabilities.json").is_file():
                raise ValueError("Extension package did not install capabilities.json")
        return destination

    def load_installed(self) -> list[ExternalExtension]:
        out: list[ExternalExtension] = []
        for descriptor_path in self.extensions_dir.glob("*/capabilities.json"):
            try:
                descriptor = json.loads(descriptor_path.read_text("utf-8"))
                out.append(ExternalExtension(descriptor_path.parent, descriptor))
            except Exception:
                continue
        return out

    def remove(self, extension_id: str) -> bool:
        extension_id = str(extension_id or "").strip()
        if not extension_id or ".." in extension_id or "/" in extension_id or "\\" in extension_id:
            return False
        destination = self.extensions_dir / extension_id
        if not destination.exists():
            return False
        shutil.rmtree(destination)
        return True


class CapabilityBroker:
    """Discover, route and merge experimental enrichment capabilities."""

    def __init__(self, data_dir: Path, config_broker: PluginConfigBroker | None = None):
        self.data_dir = Path(data_dir)
        self.config_broker = config_broker or PluginConfigBroker(self.data_dir)
        self.installer = ExtensionInstaller(self.data_dir / "extensions")
        self.settings_path = self.data_dir / "extension-settings.json"
        self.settings = self._load_settings()
        self.extensions: dict[str, ExternalExtension] = {}
        for extension in self.installer.load_installed():
            extension.configure(
                self.config_broker.values(
                    extension.info.id, extension.info.configuration
                )
            )
            self.extensions[extension.info.id] = extension

    def _load_settings(self) -> dict[str, Any]:
        try:
            raw = json.loads(self.settings_path.read_text("utf-8"))
            return raw if isinstance(raw, dict) else {}
        except Exception:
            return {}

    def save(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.settings_path.write_text(
            json.dumps(self.settings, indent=2, ensure_ascii=False), "utf-8"
        )

    def _enabled_map(self) -> dict[str, bool]:
        raw = self.settings.get("enabled")
        if not isinstance(raw, dict):
            raw = {}
            self.settings["enabled"] = raw
        return raw

    def enabled(self, extension_id: str) -> bool:
        return bool(self._enabled_map().get(extension_id, True))

    def set_enabled(self, extension_id: str, enabled: bool) -> None:
        self._enabled_map()[extension_id] = bool(enabled)
        self.save()

    def _preference_map(self) -> dict[str, list[str]]:
        raw = self.settings.get("preference")
        if not isinstance(raw, dict):
            raw = {}
            self.settings["preference"] = raw
        return raw

    def preference(self, capability: str) -> list[str]:
        values = self._preference_map().get(capability, [])
        return [str(x) for x in values if str(x) in self.extensions]

    def set_preference(self, capability: str, extension_ids: list[str]) -> list[str]:
        if capability not in _METHODS:
            raise ValueError(f"Unknown capability: {capability}")
        seen: set[str] = set()
        cleaned: list[str] = []
        for extension_id in extension_ids:
            extension_id = str(extension_id)
            extension = self.extensions.get(extension_id)
            if (
                extension
                and extension.contract(capability)
                and extension_id not in seen
            ):
                seen.add(extension_id)
                cleaned.append(extension_id)
        self._preference_map()[capability] = cleaned
        self.save()
        return cleaned

    def _for_capability(self, capability: str) -> list[ExternalExtension]:
        available = [
            extension
            for extension in self.extensions.values()
            if self.enabled(extension.info.id) and extension.contract(capability)
        ]
        preferred = self.preference(capability)
        rank = {extension_id: index for index, extension_id in enumerate(preferred)}
        available.sort(
            key=lambda item: (
                rank.get(item.info.id, len(rank) + 1),
                item.info.id.casefold(),
            )
        )
        return available

    def install_package(self, path: Path) -> ExtensionInfo:
        folder = self.installer.install(path)
        descriptor = json.loads((folder / "capabilities.json").read_text("utf-8"))
        extension = ExternalExtension(folder, descriptor)
        extension.configure(
            self.config_broker.values(
                extension.info.id, extension.info.configuration
            )
        )
        previous = self.extensions.get(extension.info.id)
        if previous:
            previous.close()
        self.extensions[extension.info.id] = extension
        return extension.info

    def remove(self, extension_id: str) -> bool:
        extension = self.extensions.pop(extension_id, None)
        if extension:
            extension.close()
        changed = self.installer.remove(extension_id)
        if changed:
            if extension is not None:
                self.config_broker.remove(
                    extension_id, extension.info.configuration
                )
            self._enabled_map().pop(extension_id, None)
            for capability, ids in list(self._preference_map().items()):
                self._preference_map()[capability] = [
                    item for item in ids if item != extension_id
                ]
            self.save()
        return changed

    def list_extensions(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for extension in sorted(
            self.extensions.values(), key=lambda item: item.info.name.casefold()
        ):
            info = extension.info.as_dict()
            info["enabled"] = self.enabled(extension.info.id)
            info["configuration_status"] = self.config_broker.status(
                extension.info.id, extension.info.configuration
            )
            info["health"] = extension.health()
            info["preferred_for"] = [
                capability
                for capability in _METHODS
                if self.preference(capability)
                and self.preference(capability)[0] == extension.info.id
            ]
            out.append(info)
        return out

    @staticmethod
    def entity_ref(
        track: dict[str, Any],
        identity: dict[str, Any] | None = None,
        entity_type: str = "track",
    ) -> dict[str, Any]:
        track = dict(track or {})
        identity = dict(identity or {})
        provider_id = str(track.get("provider_id") or "").strip()
        track_id = str(
            track.get("track_id")
            or track.get("provider_track_id")
            or track.get("id")
            or ""
        ).strip()
        canonical: dict[str, str] = {}
        mappings = {
            "isrc": ("isrc",),
            "musicbrainz_recording_id": (
                "musicbrainz_recording_id",
                "recording_mbid",
            ),
            "musicbrainz_release_id": (
                "musicbrainz_release_id",
                "release_mbid",
            ),
            "musicbrainz_release_group_id": (
                "musicbrainz_release_group_id",
                "release_group_mbid",
            ),
            "musicbrainz_artist_id": (
                "musicbrainz_artist_id",
                "artist_mbid",
            ),
            "wikidata_id": ("wikidata_id",),
        }
        for canonical_name, names in mappings.items():
            value = next(
                (
                    str(identity.get(name) or track.get(name) or "").strip()
                    for name in names
                    if identity.get(name) or track.get(name)
                ),
                "",
            )
            if value:
                canonical[canonical_name] = value

        duration_ms: int | None = None
        raw_duration_ms = track.get("duration_ms")
        raw_duration = track.get("duration")
        try:
            if raw_duration_ms not in (None, ""):
                duration_ms = max(0, int(float(raw_duration_ms)))
            elif raw_duration not in (None, ""):
                duration_ms = max(0, int(float(raw_duration) * 1000))
        except (TypeError, ValueError):
            duration_ms = None

        hints: dict[str, Any] = {}
        for key in ("title", "artist", "album"):
            value = str(identity.get(key) or track.get(key) or "").strip()
            if value:
                hints[key] = value
        if entity_type == "artist":
            name = str(
                identity.get("artist") or track.get("artist") or track.get("name") or ""
            ).strip()
            if name:
                hints["name"] = name
        if duration_ms is not None:
            hints["duration_ms"] = duration_ms

        subject: dict[str, Any] = {"entity_type": entity_type}
        if provider_id and track_id and entity_type == "track":
            subject["provider_refs"] = [
                {
                    "provider_id": provider_id,
                    "provider_entity_id": track_id,
                    "entity_type": "track",
                }
            ]
        if canonical:
            subject["canonical_ids"] = canonical
        if hints:
            subject["hints"] = hints
        return subject

    def _call_all(
        self,
        capability: str,
        params: dict[str, Any],
    ) -> tuple[list[tuple[ExternalExtension, dict[str, Any]]], list[str]]:
        results: list[tuple[ExternalExtension, dict[str, Any]]] = []
        errors: list[str] = []
        for extension in self._for_capability(capability):
            try:
                raw = extension.call(capability, params)
                if isinstance(raw, dict):
                    results.append((extension, raw))
                else:
                    errors.append(
                        f"{extension.info.name}: returned a non-object response"
                    )
            except Exception as exc:
                classifier = getattr(extension, "_diagnostic_error", None)
                category = classifier(exc) if callable(classifier) else "call_error"
                errors.append(f"{extension.info.name}: {category}")
        return results, errors

    def resolve_identity(
        self, subject: dict[str, Any], max_candidates: int = 5
    ) -> dict[str, Any]:
        results, errors = self._call_all(
            "identity",
            {
                "schema_version": "0.1",
                "capability": "identity",
                "subject": dict(subject),
                "max_candidates": max(1, min(20, int(max_candidates))),
            },
        )
        candidates: list[dict[str, Any]] = []
        for order, (extension, result) in enumerate(results):
            for raw in list(result.get("candidates") or []):
                if not isinstance(raw, dict):
                    continue
                candidate = dict(raw)
                candidate["_extension_id"] = extension.info.id
                candidate["_extension_order"] = order
                candidates.append(candidate)
        candidates.sort(
            key=lambda row: (
                -float(row.get("score") or 0.0),
                int(row.get("_extension_order") or 0),
                str(row.get("_extension_id") or ""),
            )
        )
        status = "not_found"
        if candidates:
            status = "matched"
            if len(candidates) > 1:
                first = float(candidates[0].get("score") or 0.0)
                second = float(candidates[1].get("score") or 0.0)
                if first - second < 0.03:
                    status = "ambiguous"
        return {
            "schema_version": "0.1",
            "capability": "identity",
            "status": status,
            "subject": dict(subject),
            "candidates": candidates[: max(1, int(max_candidates))],
            "errors": errors,
        }

    def enrich_metadata(
        self,
        subject: dict[str, Any],
        requested_fields: list[str] | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "schema_version": "0.1",
            "capability": "metadata",
            "subject": dict(subject),
        }
        if requested_fields:
            params["requested_fields"] = [str(x) for x in requested_fields]
        results, errors = self._call_all("metadata", params)
        fields: dict[str, Any] = {}
        alternatives: dict[str, list[dict[str, Any]]] = {}
        for extension, result in results:
            for field_name, raw in dict(result.get("fields") or {}).items():
                if not isinstance(raw, dict) or "value" not in raw:
                    continue
                value = dict(raw)
                provenance = value.get("provenance")
                if isinstance(provenance, dict):
                    provenance.setdefault("source_extension_id", extension.info.id)
                if field_name not in fields:
                    fields[field_name] = value
                elif fields[field_name].get("value") != value.get("value"):
                    alternatives.setdefault(field_name, []).append(value)
        return {
            "schema_version": "0.1",
            "capability": "metadata",
            "subject": dict(subject),
            "fields": fields,
            "alternatives": alternatives,
            "errors": errors,
        }

    def lookup_artwork(
        self,
        subject: dict[str, Any],
        roles: list[str] | None = None,
        max_results: int = 8,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "schema_version": "0.1",
            "capability": "artwork",
            "subject": dict(subject),
            "max_results": max(1, min(50, int(max_results))),
        }
        if roles:
            params["roles"] = [str(x) for x in roles]
        results, errors = self._call_all("artwork", params)
        assets: list[dict[str, Any]] = []
        seen: set[str] = set()
        for order, (extension, result) in enumerate(results):
            for raw in list(result.get("assets") or []):
                if not isinstance(raw, dict):
                    continue
                url = str(raw.get("url") or "").strip()
                if not url or url in seen:
                    continue
                seen.add(url)
                asset = dict(raw)
                provenance = asset.get("provenance")
                if isinstance(provenance, dict):
                    provenance.setdefault("source_extension_id", extension.info.id)
                asset["_extension_id"] = extension.info.id
                asset["_extension_order"] = order
                assets.append(asset)
        assets.sort(
            key=lambda row: (
                -float(row.get("score") or 0.0),
                int(row.get("_extension_order") or 0),
                str(row.get("url") or ""),
            )
        )
        return {
            "schema_version": "0.1",
            "capability": "artwork",
            "subject": dict(subject),
            "assets": assets[: max(1, int(max_results))],
            "errors": errors,
        }

    def lookup_lyrics(
        self,
        subject: dict[str, Any],
        kinds: list[str] | None = None,
        languages: list[str] | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "schema_version": "0.1",
            "capability": "lyrics",
            "subject": dict(subject),
        }
        if kinds:
            params["kinds"] = [str(x) for x in kinds]
        if languages:
            params["languages"] = [str(x) for x in languages]
        results, errors = self._call_all("lyrics", params)
        entries: list[dict[str, Any]] = []
        seen: set[tuple[str, str, str]] = set()
        for order, (extension, result) in enumerate(results):
            for raw in list(result.get("entries") or []):
                if not isinstance(raw, dict):
                    continue
                key = (
                    str(raw.get("kind") or ""),
                    str(raw.get("language") or ""),
                    str(raw.get("text") or ""),
                )
                if key in seen:
                    continue
                seen.add(key)
                entry = dict(raw)
                provenance = entry.get("provenance")
                if isinstance(provenance, dict):
                    provenance.setdefault("source_extension_id", extension.info.id)
                entry["_extension_id"] = extension.info.id
                entry["_extension_order"] = order
                entries.append(entry)
        return {
            "schema_version": "0.1",
            "capability": "lyrics",
            "subject": dict(subject),
            "entries": entries,
            "errors": errors,
        }

    @staticmethod
    def legacy_identity(
        track: dict[str, Any], candidate: dict[str, Any]
    ) -> dict[str, Any]:
        canonical = dict(candidate.get("canonical_ids") or {})
        display = dict(candidate.get("display") or {})
        return {
            "recording_mbid": str(
                canonical.get("musicbrainz_recording_id") or ""
            ),
            "artist_mbid": str(canonical.get("musicbrainz_artist_id") or ""),
            "release_mbid": str(canonical.get("musicbrainz_release_id") or ""),
            "release_group_mbid": str(
                canonical.get("musicbrainz_release_group_id") or ""
            ),
            "artist": str(display.get("artist") or track.get("artist") or ""),
            "title": str(display.get("title") or track.get("title") or ""),
            "album": str(display.get("album") or track.get("album") or ""),
            "date": str(display.get("date") or ""),
            "score": float(candidate.get("score") or 0.0),
            "_canonical_ids": canonical,
            "_provenance": candidate.get("provenance"),
            "_extension_id": str(candidate.get("_extension_id") or ""),
        }

    def close(self) -> None:
        for extension in list(self.extensions.values()):
            extension.close()
