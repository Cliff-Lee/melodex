from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SourceSelectionPresentation:
    button_text: str
    hint: str


@dataclass(frozen=True)
class SourcePrimaryAction:
    kind: str
    target: str = ""


class SourcePolicyController:
    """Source/plugin policy that does not depend on Qt widgets."""

    def __init__(self, providers: Any) -> None:
        self.providers = providers

    @staticmethod
    def capability_label(capability: str) -> str:
        return {
            "library_suggestions": "recommendations",
            "artwork": "artwork",
            "lyrics": "lyrics",
            "context": "context",
            "metadata": "metadata",
            "identity": "identity",
        }.get(
            str(capability or ""),
            str(capability or "").replace("_", " "),
        )

    def extension_record(self, extension_id: str) -> dict[str, Any]:
        wanted = str(extension_id or "")
        return next(
            (
                dict(row)
                for row in self.providers.extensions(cached_config=True)
                if str(row.get("id") or "") == wanted
            ),
            {},
        )

    def plugin_needs_setup(self, plugin_id: str) -> bool:
        plugin_id = str(plugin_id or "")
        if not plugin_id:
            return False
        if plugin_id.startswith("extension:"):
            row = self.extension_record(plugin_id.split(":", 1)[1])
            status = dict(row.get("configuration_status") or {})
            return bool(
                status.get("declared")
                and status.get("ready") is False
            )

        provider = self.providers.providers.get(plugin_id)
        if provider is None or not provider.info.configuration:
            return False
        status = self.providers.plugin_config.cached_status(
            plugin_id,
            provider.info.configuration,
        )
        return status.get("ready") is False

    def _jamendo_ready(self) -> bool:
        return bool(
            not self.plugin_needs_setup("jamendo")
            and str(self.providers.settings.get("jamendo_client_id", "")).strip()
        )

    def _provider_is_searchable(self, provider_id: str) -> bool:
        provider = self.providers.providers.get(provider_id)
        return bool(
            provider is not None
            and "search" in list(provider.info.capabilities or [])
        )

    def selection_presentation(self, key: str) -> SourceSelectionPresentation:
        key = str(key or "")
        if not key:
            return SourceSelectionPresentation("Use selected", "")

        if key == "local":
            return SourceSelectionPresentation(
                "Add music",
                "This computer · add another folder here, or browse the collection in My Music.",
            )

        if key == "jamendo":
            if not self._jamendo_ready():
                return SourceSelectionPresentation(
                    "Set up Jamendo",
                    "Jamendo is an optional online source. Set it up once, then use it from Explore → Search everything.",
                )
            return SourceSelectionPresentation(
                "Search Jamendo",
                "Jamendo is a music source. Use it in Explore → Search everything; Melodex will open Search already filtered to Jamendo.",
            )

        if key == "streams":
            return SourceSelectionPresentation(
                "Manage streams",
                "My streams contains direct radio/audio URLs you add yourself.",
            )

        if key.startswith("extension:"):
            extension_id = key.split(":", 1)[1]
            if self.plugin_needs_setup(key):
                return SourceSelectionPresentation(
                    "Set up plugin",
                    "This plugin is installed but needs setup before Melodex can use it.",
                )
            row = self.extension_record(extension_id)
            capabilities = [
                str(value)
                for value in list(row.get("capabilities") or [])
                if value
            ]
            labels = ", ".join(
                self.capability_label(value)
                for value in capabilities
            ) or "extra capabilities"
            return SourceSelectionPresentation(
                "Use plugin",
                f"This plugin provides {labels}. Choose Use plugin and Melodex will open the feature where it participates.",
            )

        if self.plugin_needs_setup(key):
            return SourceSelectionPresentation(
                "Set up source",
                "This provider is installed but needs setup before it can search or play.",
            )
        if self._provider_is_searchable(key):
            return SourceSelectionPresentation(
                "Search this source",
                "This provider is used from Explore → Search everything. The button will open Search already filtered to this source.",
            )
        return SourceSelectionPresentation(
            "Use source",
            "This provider is active. Choose Use source to open the closest matching Melodex feature.",
        )

    def primary_action(self, key: str) -> SourcePrimaryAction:
        key = str(key or "")
        if not key:
            return SourcePrimaryAction("none")
        if key == "local":
            return SourcePrimaryAction("choose_music_folder")
        if key == "jamendo":
            return SourcePrimaryAction(
                "open_provider_search" if self._jamendo_ready() else "jamendo_settings",
                "jamendo",
            )
        if key == "streams":
            return SourcePrimaryAction("manage_streams")
        if key.startswith("extension:"):
            extension_id = key.split(":", 1)[1]
            if self.plugin_needs_setup(key):
                return SourcePrimaryAction("configure_plugin", extension_id)
            return SourcePrimaryAction("use_extension", extension_id)
        if self.plugin_needs_setup(key):
            return SourcePrimaryAction("configure_plugin", key)
        if self._provider_is_searchable(key):
            return SourcePrimaryAction("open_provider_search", key)
        return SourcePrimaryAction("test_plugin", key)

    def active_extension_names(self, *capabilities: str) -> list[str]:
        wanted = {str(value) for value in capabilities if str(value)}
        names: list[str] = []
        for row in self.providers.extensions(cached_config=True):
            if not bool(row.get("enabled", True)):
                continue
            config = dict(row.get("configuration_status") or {})
            if config.get("declared") and config.get("ready") is False:
                continue
            caps = {
                str(value)
                for value in list(row.get("capabilities") or [])
                if value
            }
            if wanted and not (wanted & caps):
                continue
            name = str(row.get("name") or row.get("id") or "").strip()
            if name:
                names.append(name)
        return names

    def searchable_source_names(self) -> list[str]:
        names: list[str] = []
        for provider_id in self.providers.searchable_provider_ids():
            provider = self.providers.providers.get(provider_id)
            if provider is None or self.plugin_needs_setup(provider_id):
                continue
            name = str(provider.info.name or provider_id)
            name = name.replace(" (reference provider)", "").strip()
            if name:
                names.append(name)
        return names

    @staticmethod
    def selected_plugin_id(value: str) -> str:
        value = str(value or "")
        if value.startswith("extension:"):
            return value.split(":", 1)[1]
        return value if value not in {"local", "jamendo", "streams"} else ""
