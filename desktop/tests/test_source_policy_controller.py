from __future__ import annotations

from dataclasses import dataclass

from melodex.source_policy_controller import SourcePolicyController


@dataclass
class Info:
    name: str
    capabilities: list[str]
    configuration: list[dict]


class Provider:
    def __init__(self, name, capabilities=(), configuration=()):
        self.info = Info(
            name=name,
            capabilities=list(capabilities),
            configuration=list(configuration),
        )


class ConfigBroker:
    def __init__(self, statuses=None):
        self.statuses = dict(statuses or {})

    def cached_status(self, plugin_id, _configuration):
        return dict(self.statuses.get(plugin_id, {"ready": True}))


class Providers:
    def __init__(self):
        self.settings = {"jamendo_client_id": ""}
        self.providers = {
            "local": Provider("Local Files"),
            "jamendo": Provider(
                "Jamendo",
                capabilities=["search"],
                configuration=[{"id": "client_id"}],
            ),
            "searchable": Provider("Searchable Source", capabilities=["search"]),
            "configured": Provider(
                "Needs Setup",
                capabilities=["search"],
                configuration=[{"id": "token"}],
            ),
            "plain": Provider("Plain Source"),
        }
        self.plugin_config = ConfigBroker({"configured": {"ready": False}})
        self._extensions = [
            {
                "id": "lyrics-ext",
                "name": "Lyrics Plus",
                "enabled": True,
                "capabilities": ["lyrics", "context"],
                "configuration_status": {"declared": False, "ready": True},
            },
            {
                "id": "art-ext",
                "name": "Artwork Lab",
                "enabled": True,
                "capabilities": ["artwork"],
                "configuration_status": {"declared": True, "ready": False},
            },
        ]

    def extensions(self, cached_config=True):
        return [dict(row) for row in self._extensions]

    def searchable_provider_ids(self):
        return ["searchable", "configured"]


def test_capability_and_extension_policy():
    controller = SourcePolicyController(Providers())

    assert controller.capability_label("library_suggestions") == "recommendations"
    assert controller.capability_label("audio_analysis") == "audio analysis"
    assert controller.extension_record("lyrics-ext")["name"] == "Lyrics Plus"
    assert controller.extension_record("missing") == {}


def test_setup_detection_handles_providers_and_extensions():
    providers = Providers()
    controller = SourcePolicyController(providers)

    assert controller.plugin_needs_setup("configured") is True
    assert controller.plugin_needs_setup("searchable") is False
    assert controller.plugin_needs_setup("extension:art-ext") is True
    assert controller.plugin_needs_setup("extension:lyrics-ext") is False


def test_selection_presentation_preserves_existing_source_copy():
    providers = Providers()
    controller = SourcePolicyController(providers)

    local = controller.selection_presentation("local")
    assert local.button_text == "Add music"
    assert "browse the collection in My Music" in local.hint

    jamendo = controller.selection_presentation("jamendo")
    assert jamendo.button_text == "Set up Jamendo"

    providers.settings["jamendo_client_id"] = "client"
    providers.plugin_config.statuses["jamendo"] = {"ready": True}
    jamendo = controller.selection_presentation("jamendo")
    assert jamendo.button_text == "Search Jamendo"

    extension = controller.selection_presentation("extension:lyrics-ext")
    assert extension.button_text == "Use plugin"
    assert "lyrics, context" in extension.hint

    needs_setup = controller.selection_presentation("configured")
    assert needs_setup.button_text == "Set up source"


def test_primary_action_routes_without_ui_dependencies():
    providers = Providers()
    controller = SourcePolicyController(providers)

    assert controller.primary_action("local").kind == "choose_music_folder"
    assert controller.primary_action("jamendo").kind == "jamendo_settings"
    assert controller.primary_action("extension:art-ext").kind == "configure_plugin"
    assert controller.primary_action("extension:lyrics-ext").kind == "use_extension"
    assert controller.primary_action("configured").kind == "configure_plugin"
    assert controller.primary_action("searchable").kind == "open_provider_search"
    assert controller.primary_action("plain").kind == "test_plugin"

    providers.settings["jamendo_client_id"] = "client"
    providers.plugin_config.statuses["jamendo"] = {"ready": True}
    assert controller.primary_action("jamendo").kind == "open_provider_search"


def test_presence_lists_hide_unready_plugins():
    controller = SourcePolicyController(Providers())

    assert controller.active_extension_names("lyrics") == ["Lyrics Plus"]
    assert controller.active_extension_names("artwork") == []
    assert controller.searchable_source_names() == ["Searchable Source"]


def test_selected_plugin_id_normalises_special_source_keys():
    selected = SourcePolicyController.selected_plugin_id

    assert selected("extension:lyrics-ext") == "lyrics-ext"
    assert selected("plain") == "plain"
    assert selected("local") == ""
    assert selected("jamendo") == ""
    assert selected("streams") == ""
