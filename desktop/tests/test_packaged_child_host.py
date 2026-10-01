from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from melodex.capabilities import ExternalExtension
from melodex.child_host import CHILD_FLAG, maybe_run_child_from_argv, python_child_command
from melodex.provider import ExternalProvider
from melodex.instance_identity import instance_server_name
from melodex.process_env import scrubbed_child_env


def test_frozen_python_children_reenter_melodex_in_worker_mode(monkeypatch, tmp_path: Path):
    script = tmp_path / "plugin.py"
    script.write_text("pass\n", "utf-8")
    monkeypatch.setattr(sys, "frozen", True, raising=False)

    command = python_child_command(script)
    assert command[0] == sys.executable
    assert command[1] == CHILD_FLAG
    assert command[2] == str(script.resolve())


def test_source_python_children_use_python_unbuffered(monkeypatch, tmp_path: Path):
    script = tmp_path / "plugin.py"
    script.write_text("pass\n", "utf-8")
    monkeypatch.delattr(sys, "frozen", raising=False)
    assert python_child_command(script) == [sys.executable, "-u", str(script.resolve())]


def test_child_worker_executes_script_without_gui(tmp_path: Path):
    marker = tmp_path / "marker.json"
    script = tmp_path / "worker.py"
    script.write_text(
        "import json, os, sys\n"
        "from pathlib import Path\n"
        "Path(sys.argv[1]).write_text(json.dumps({'argv': sys.argv[2:], 'child': os.getenv('MELODEX_CHILD_PROCESS')}), 'utf-8')\n",
        "utf-8",
    )
    code = maybe_run_child_from_argv([CHILD_FLAG, str(script), str(marker), "hello"])
    assert code == 0
    payload = json.loads(marker.read_text("utf-8"))
    assert payload == {"argv": ["hello"], "child": "1"}


def test_external_provider_frozen_command_uses_child_host(monkeypatch, tmp_path: Path):
    (tmp_path / "provider.py").write_text("pass\n", "utf-8")
    provider = ExternalProvider(
        tmp_path,
        {
            "id": "org.example.provider",
            "name": "Provider",
            "capabilities": ["search"],
            "entrypoints": {"python": "provider.py"},
        },
    )
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    command = provider._command()
    assert command[:2] == [sys.executable, CHILD_FLAG]


def test_external_extension_frozen_command_uses_child_host(monkeypatch, tmp_path: Path):
    (tmp_path / "plugin.py").write_text("pass\n", "utf-8")
    extension = ExternalExtension(
        tmp_path,
        {
            "schema_version": "0.1",
            "extension_id": "org.example.extension",
            "name": "Extension",
            "entrypoints": {"python": "plugin.py"},
            "contracts": [
                {
                    "capability": "metadata",
                    "contract_version": "0.1",
                    "method": "metadata.enrich",
                }
            ],
        },
    )
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    command = extension._command()
    assert command[:2] == [sys.executable, CHILD_FLAG]


def test_external_provider_rpc_timeout_stops_hung_process(tmp_path: Path):
    script = tmp_path / "provider.py"
    script.write_text(
        "import sys, time\n"
        "for line in sys.stdin:\n"
        "    if line.strip():\n"
        "        time.sleep(5)\n",
        "utf-8",
    )
    provider = ExternalProvider(
        tmp_path,
        {
            "id": "org.example.hung",
            "name": "Hung Provider",
            "capabilities": ["search"],
            "entrypoints": {"python": "provider.py"},
        },
        timeout=0.15,
    )
    with pytest.raises(RuntimeError, match="timed out"):
        provider._rpc("catalog.search", {"query": "x"})
    assert provider._proc is None


def test_single_instance_server_name_is_stable_and_per_data_dir(tmp_path: Path):
    a = instance_server_name(tmp_path / "one")
    b = instance_server_name(tmp_path / "one")
    c = instance_server_name(tmp_path / "two")
    assert a == b
    assert a != c
    assert a.startswith("melodex-")



def test_child_worker_restores_missing_standard_streams(monkeypatch):
    import io

    import melodex.child_host as child_host

    streams = {0: io.StringIO(), 1: io.StringIO(), 2: io.StringIO()}
    monkeypatch.setattr(child_host.sys, "stdin", None)
    monkeypatch.setattr(child_host.sys, "stdout", None)
    monkeypatch.setattr(child_host.sys, "stderr", None)
    monkeypatch.setattr(
        child_host,
        "_open_inherited_stdio",
        lambda fd, mode: streams[fd],
    )

    assert child_host._restore_child_stdio()
    assert child_host.sys.stdin is streams[0]
    assert child_host.sys.stdout is streams[1]
    assert child_host.sys.stderr is streams[2]



def test_child_environment_supplies_ca_bundle_when_parent_has_none(monkeypatch):
    import melodex.process_env as process_env

    class FakeCertifi:
        @staticmethod
        def where():
            return "/tmp/melodex-test-ca.pem"

    monkeypatch.setitem(sys.modules, "certifi", FakeCertifi())
    env = scrubbed_child_env(
        identifier_key="MELODEX_EXTENSION_ID",
        identifier="org.example.context",
        parent={"PATH": "/usr/bin"},
    )

    assert env["SSL_CERT_FILE"] == "/tmp/melodex-test-ca.pem"
    assert env["MELODEX_EXTENSION_ID"] == "org.example.context"
