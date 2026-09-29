from melodex.plugin_onboarding import (
    configuration_state,
    configuration_summary,
    plugin_configuration_info,
    plugin_needs_setup,
)


def test_configuration_state_distinguishes_none_ready_and_setup_needed():
    assert configuration_state({}) == "none"
    assert configuration_state({"fields": []}) == "none"
    assert configuration_state(
        {"fields": [{"key": "token"}], "status": {"ready": True}}
    ) == "ready"
    assert configuration_state(
        {
            "fields": [{"key": "token"}],
            "status": {"ready": False, "missing_required": ["token"]},
        }
    ) == "setup_needed"


def test_configuration_summary_does_not_expose_values():
    info = {
        "fields": [{"key": "api_key"}],
        "values": {"api_key": "should-never-be-shown"},
        "status": {
            "ready": False,
            "missing_required": ["api_key"],
        },
    }
    summary = configuration_summary(info)
    assert summary == "Setup needed — missing: api_key"
    assert "should-never-be-shown" not in summary


class Manager:
    def __init__(self, info=None):
        self.info = info
    def plugin_configuration(self, plugin_id):
        if self.info is None:
            raise KeyError(plugin_id)
        return self.info


def test_plugin_needs_setup_handles_unknown_and_configured_plugins():
    assert plugin_configuration_info(Manager(), "missing") == {}
    assert plugin_needs_setup(Manager(), "missing") is False

    manager = Manager(
        {
            "fields": [{"key": "api_key"}],
            "status": {"ready": False, "missing_required": ["api_key"]},
        }
    )
    assert plugin_needs_setup(manager, "org.example.plugin") is True

    manager.info["status"] = {"ready": True, "missing_required": []}
    assert plugin_needs_setup(manager, "org.example.plugin") is False
