from __future__ import annotations

import json
import os
import re
import threading
from pathlib import Path
from typing import Any, Protocol


_KEY_RE = re.compile(r"^[A-Za-z][A-Za-z0-9._-]{0,63}$")
_FIELD_TYPES = {"string", "secret", "boolean"}


def normalise_configuration(raw: Any) -> list[dict[str, Any]]:
    if raw in (None, []):
        return []
    if not isinstance(raw, list):
        raise ValueError("configuration must be an array")

    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            raise ValueError(f"configuration[{index}] must be an object")
        key = str(item.get("key") or "").strip()
        label = str(item.get("label") or "").strip()
        field_type = str(item.get("type") or "").strip()
        if not _KEY_RE.fullmatch(key):
            raise ValueError(
                f"configuration[{index}].key must start with a letter and contain "
                "only letters, digits, '.', '_' or '-'"
            )
        if key in seen:
            raise ValueError(f"duplicate configuration key: {key}")
        if not label:
            raise ValueError(f"configuration[{index}].label is required")
        if field_type not in _FIELD_TYPES:
            raise ValueError(
                f"configuration[{index}].type must be one of: "
                + ", ".join(sorted(_FIELD_TYPES))
            )
        seen.add(key)
        field: dict[str, Any] = {
            "key": key,
            "label": label,
            "type": field_type,
            "required": bool(item.get("required", False)),
        }
        help_text = str(item.get("help") or "").strip()
        if help_text:
            field["help"] = help_text
        out.append(field)
    return out


class _SecretStore(Protocol):
    mode: str

    def get(self, plugin_id: str, key: str) -> str | None: ...

    def set(self, plugin_id: str, key: str, value: str) -> None: ...

    def delete(self, plugin_id: str, key: str) -> None: ...


class _MemorySecretStore:
    mode = "session-only"

    def __init__(self) -> None:
        self._values: dict[tuple[str, str], str] = {}

    def get(self, plugin_id: str, key: str) -> str | None:
        return self._values.get((plugin_id, key))

    def set(self, plugin_id: str, key: str, value: str) -> None:
        self._values[(plugin_id, key)] = str(value)

    def delete(self, plugin_id: str, key: str) -> None:
        self._values.pop((plugin_id, key), None)


class _SystemKeyringSecretStore:
    mode = "system-keyring"
    _SERVICE = "Melodex plugin configuration"

    def __init__(self) -> None:
        import keyring  # type: ignore

        backend = keyring.get_keyring()
        priority = float(getattr(backend, "priority", 0) or 0)
        if priority <= 0:
            raise RuntimeError("No usable system keyring backend")
        self._keyring = keyring

    @staticmethod
    def _username(plugin_id: str, key: str) -> str:
        return f"{plugin_id}:{key}"

    def get(self, plugin_id: str, key: str) -> str | None:
        return self._keyring.get_password(
            self._SERVICE, self._username(plugin_id, key)
        )

    def set(self, plugin_id: str, key: str, value: str) -> None:
        self._keyring.set_password(
            self._SERVICE, self._username(plugin_id, key), str(value)
        )

    def delete(self, plugin_id: str, key: str) -> None:
        username = self._username(plugin_id, key)
        try:
            self._keyring.delete_password(self._SERVICE, username)
        except Exception:
            # Deleting an absent item should be idempotent across keyring backends.
            return



class _ResilientSecretStore:
    """Use the system keyring when possible, with session memory as fallback."""

    mode = "system-keyring (session fallback)"

    def __init__(self, primary: _SecretStore) -> None:
        self._primary = primary
        self._fallback = _MemorySecretStore()

    def get(self, plugin_id: str, key: str) -> str | None:
        try:
            value = self._primary.get(plugin_id, key)
        except Exception:
            value = None
        return value if value is not None else self._fallback.get(plugin_id, key)

    def set(self, plugin_id: str, key: str, value: str) -> None:
        try:
            self._primary.set(plugin_id, key, value)
            self._fallback.delete(plugin_id, key)
        except Exception:
            self._fallback.set(plugin_id, key, value)

    def delete(self, plugin_id: str, key: str) -> None:
        try:
            self._primary.delete(plugin_id, key)
        except Exception:
            pass
        self._fallback.delete(plugin_id, key)

def _default_secret_store() -> _SecretStore:
    try:
        return _ResilientSecretStore(_SystemKeyringSecretStore())
    except Exception:
        return _MemorySecretStore()


class PluginConfigBroker:
    """Broker declared plugin configuration without putting secrets in JSON."""

    def __init__(
        self,
        data_dir: Path,
        *,
        secret_store: _SecretStore | None = None,
    ):
        self.data_dir = Path(data_dir)
        self.path = self.data_dir / "plugin-config.json"
        self._secret_store: _SecretStore = secret_store or _default_secret_store()
        self._settings = self._load()
        self._secret_presence: dict[tuple[str, str], bool] = {}
        self._presence_lock = threading.RLock()

    @property
    def secret_storage(self) -> str:
        return str(getattr(self._secret_store, "mode", "session-only"))

    def _load(self) -> dict[str, dict[str, Any]]:
        try:
            raw = json.loads(self.path.read_text("utf-8"))
        except Exception:
            return {}
        if not isinstance(raw, dict):
            return {}
        return {
            str(plugin_id): dict(values)
            for plugin_id, values in raw.items()
            if isinstance(values, dict)
        }

    def _save(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_suffix(".tmp")
        temp.write_text(
            json.dumps(self._settings, indent=2, ensure_ascii=False) + "\n",
            "utf-8",
        )
        try:
            os.chmod(temp, 0o600)
        except OSError:
            pass
        temp.replace(self.path)
        try:
            os.chmod(self.path, 0o600)
        except OSError:
            pass

    @staticmethod
    def _field_map(declarations: Any) -> dict[str, dict[str, Any]]:
        return {
            field["key"]: field
            for field in normalise_configuration(declarations)
        }

    def values(self, plugin_id: str, declarations: Any) -> dict[str, Any]:
        plugin_id = str(plugin_id)
        fields = self._field_map(declarations)
        stored = dict(self._settings.get(plugin_id, {}))
        out: dict[str, Any] = {}
        for key, field in fields.items():
            if field["type"] == "secret":
                value = self._secret_store.get(plugin_id, key)
                present = value is not None and bool(str(value))
                with self._presence_lock:
                    self._secret_presence[(plugin_id, key)] = present
                if value is not None:
                    out[key] = value
            elif key in stored:
                value = stored[key]
                out[key] = bool(value) if field["type"] == "boolean" else str(value)
        return out

    def cached_status(self, plugin_id: str, declarations: Any) -> dict[str, Any]:
        """Return configuration readiness without touching the system keyring.

        Required secrets that have not been observed in this process are reported
        as pending rather than missing. This method is safe for read-only UI paths.
        """
        plugin_id = str(plugin_id)
        fields = self._field_map(declarations)
        stored = dict(self._settings.get(plugin_id, {}))
        configured: dict[str, bool | None] = {}
        missing: list[str] = []
        pending: list[str] = []

        with self._presence_lock:
            secret_presence = dict(self._secret_presence)

        for key, field in fields.items():
            if field["type"] == "secret":
                present = secret_presence.get((plugin_id, key))
                configured[key] = present
                if field.get("required"):
                    if present is False:
                        missing.append(key)
                    elif present is None:
                        pending.append(key)
                continue

            if field["type"] == "boolean":
                present = key in stored
            else:
                present = bool(str(stored.get(key) or "").strip())
            configured[key] = present
            if field.get("required") and not present:
                missing.append(key)

        ready: bool | None
        if missing:
            ready = False
        elif pending:
            ready = None
        else:
            ready = True

        return {
            "declared": bool(fields),
            "configured": configured,
            "ready": ready,
            "pending": bool(pending),
            "pending_required": pending,
            "missing_required": missing,
            "secret_storage": self.secret_storage,
        }

    def editable_values(self, plugin_id: str, declarations: Any) -> dict[str, Any]:
        fields = self._field_map(declarations)
        stored = dict(self._settings.get(str(plugin_id), {}))
        return {
            key: (
                bool(stored[key])
                if field["type"] == "boolean"
                else str(stored[key])
            )
            for key, field in fields.items()
            if field["type"] != "secret" and key in stored
        }

    def status(self, plugin_id: str, declarations: Any) -> dict[str, Any]:
        fields = self._field_map(declarations)
        values = self.values(plugin_id, declarations)
        configured: dict[str, bool] = {}
        missing: list[str] = []
        for key, field in fields.items():
            if field["type"] == "boolean":
                present = key in values
            else:
                present = bool(str(values.get(key) or "").strip())
            configured[key] = present
            if field.get("required") and not present:
                missing.append(key)
        return {
            "declared": bool(fields),
            "configured": configured,
            "ready": not missing,
            "pending": False,
            "pending_required": [],
            "missing_required": missing,
            "secret_storage": self.secret_storage,
        }

    def update(
        self,
        plugin_id: str,
        declarations: Any,
        changes: dict[str, Any],
    ) -> dict[str, Any]:
        plugin_id = str(plugin_id)
        fields = self._field_map(declarations)
        unknown = sorted(set(changes) - set(fields))
        if unknown:
            raise ValueError(
                "Configuration contains undeclared keys: " + ", ".join(unknown)
            )

        stored = dict(self._settings.get(plugin_id, {}))
        for key, value in changes.items():
            field = fields[key]
            field_type = field["type"]
            if field_type == "secret":
                if value is None:
                    continue
                text = str(value)
                if text:
                    self._secret_store.set(plugin_id, key, text)
                    present = True
                else:
                    self._secret_store.delete(plugin_id, key)
                    present = False
                with self._presence_lock:
                    self._secret_presence[(plugin_id, key)] = present
                continue

            if value is None:
                stored.pop(key, None)
            elif field_type == "boolean":
                stored[key] = bool(value)
            else:
                stored[key] = str(value)

        if stored:
            self._settings[plugin_id] = stored
        else:
            self._settings.pop(plugin_id, None)
        self._save()
        return self.status(plugin_id, declarations)

    def remove(self, plugin_id: str, declarations: Any) -> None:
        plugin_id = str(plugin_id)
        fields = self._field_map(declarations)
        for key, field in fields.items():
            if field["type"] == "secret":
                self._secret_store.delete(plugin_id, key)
                with self._presence_lock:
                    self._secret_presence.pop((plugin_id, key), None)
        if plugin_id in self._settings:
            self._settings.pop(plugin_id, None)
            self._save()
