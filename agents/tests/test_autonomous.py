"""Hermetic tests for the autonomous pipeline's deterministic helpers.
(The git-worktree/gate/release paths run real subprocesses and are exercised
via live runs, not unit tests.)"""
from agents import autonomous


def test_slugify():
    assert autonomous.slugify("Add a health field X to /stats!") == "add-a-health-field-x-to-stats"
    assert autonomous.slugify("") == "feature"
    assert len(autonomous.slugify("x" * 100)) <= 40


def test_shell_quote_round_trips_through_shell():
    import subprocess
    for value in ("it's a test", 'a "b" c', "feat(x): do y", "line1\nline2"):
        r = subprocess.run("printf %s " + autonomous.shell_quote(value),
                           shell=True, capture_output=True, text=True)
        assert r.stdout == value, value


def test_public_api_exists():
    for fn in ("run", "run_gate", "commit_and_push_branch", "open_pr",
               "auto_merge_with_recovery", "create_worktree", "remove_worktree",
               "start_agents", "stop_agents"):
        assert hasattr(autonomous, fn)


def test_gate_enforces_configurable_coverage():
    # the gate enforces a coverage floor deterministically (default 95, env-tunable)
    import inspect
    assert autonomous.COV_MIN == 95  # path B default
    src = inspect.getsource(autonomous.run_gate)
    assert "--cov-fail-under={COV_MIN}" in src or "cov-fail-under" in src
    assert "returncode" in src  # trusts exit codes, not the LLM


def test_verdict_parsing():
    assert autonomous._verdict("looks good. APPROVE") == "APPROVE/GO"
    assert autonomous._verdict("Decision: GO") == "APPROVE/GO"
    assert autonomous._verdict("REQUEST-CHANGES: bug on line 4") == "REQUEST-CHANGES/NO-GO"
    assert autonomous._verdict("NO-GO — blocker") == "REQUEST-CHANGES/NO-GO"
    assert autonomous._verdict("hmm not sure") == "unclear"


def test_escalates_to_human_never_rolls_back():
    # the team must diagnose+fix a red pipeline, and if it can't, ESCALATE to a
    # human — never silently roll back.
    import inspect
    src = inspect.getsource(autonomous.auto_merge_with_recovery)
    assert "reset --hard" not in src, "must NOT roll back main"
    assert "gh issue create" in src, "must escalate via a GitHub issue"
    assert "ESCALATED" in src
    # diagnosis/fix loop must precede escalation
    assert src.index("diagnosis") < src.index("ESCALATED")


def test_commit_message_has_title_and_body():
    import inspect
    src = inspect.getsource(autonomous._commit_message)
    assert "Critical decisions" in src and "Co-Authored-By" in src
