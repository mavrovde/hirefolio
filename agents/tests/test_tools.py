"""Tests for the agent tool layer — safety (path jail + command allowlist),
core file ops, and the team playbook injection."""
import pytest

from agents.common import tools
from agents.common.roster import ROSTER, PROJECT_PLAYBOOK, effective_system_prompt


def test_path_jail_blocks_escape():
    with pytest.raises(ValueError):
        tools._safe_path("../../etc/passwd")
    with pytest.raises(ValueError):
        tools._safe_path("/etc/passwd")


def test_read_and_write_within_workdir(tmp_path, monkeypatch):
    monkeypatch.setattr(tools, "WORKDIR", tmp_path)
    assert "OK" in tools.write_file("sub/hello.txt", "hi there")
    assert tools.read_file("sub/hello.txt") == "hi there"
    assert "hello.txt" in tools.list_dir("sub")


def test_run_command_allowlist():
    assert tools.run_command("git status").startswith("exit=")  # allowed
    assert tools.run_command("rm -rf /").startswith("BLOCKED")   # blocked pattern
    assert tools.run_command("wget http://x").startswith("BLOCKED")  # not allowlisted


def test_execute_tool_unknown():
    assert tools.execute_tool("does_not_exist", {}).startswith("ERROR")


def test_tool_schemas_cover_registry():
    schema_names = {s["function"]["name"] for s in tools.TOOL_SCHEMAS}
    assert schema_names == set(tools.REGISTRY)


def test_fetch_url_rejects_non_http():
    assert tools.fetch_url("file:///etc/passwd").startswith("ERROR")


def test_mutating_git_blocked_for_everyone():
    for sub in ("commit", "push", "tag", "reset", "checkout", "add"):
        assert tools.run_command(f"git {sub} x").startswith("BLOCKED"), sub
    # read-only git still works
    assert tools.run_command("git status").startswith("exit=")


def test_readonly_role_cannot_write_or_run():
    ro = ROSTER["researcher"].allowed_tools()
    assert "write_file" not in ro and "run_command" not in ro
    assert {"read_file", "grep", "fetch_url", "run_tests"} <= ro
    # even if the model tries, execute_tool enforces the allowed set
    assert tools.execute_tool("write_file", {"path": "x", "content": "y"}, ro).startswith("BLOCKED")


def test_write_role_has_write_tools():
    for key in ("backend-dev", "frontend-dev", "integration-engineer"):
        assert {"write_file", "run_command"} <= ROSTER[key].allowed_tools()


def test_playbook_injected_into_every_agent():
    for spec in ROSTER.values():
        eff = effective_system_prompt(spec)
        assert PROJECT_PLAYBOOK.split("\n", 1)[0] in eff
        assert spec.system_prompt in eff
