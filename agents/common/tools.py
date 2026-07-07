"""Tools the agents can actually use — repo-scoped and safety-jailed.

All file paths are confined to A2A_WORKDIR (default: the mavrov.de repo root).
run_command only permits an allowlist of dev commands (git/pytest/npm/ruff/...),
never destructive ones. These are exposed to the LLM via the tool-calling brain.
"""
from __future__ import annotations

import os
import shlex
import subprocess
from pathlib import Path

# Work area (a git worktree/branch can be set via env for autonomous implementation).
WORKDIR = Path(os.getenv("A2A_WORKDIR", "/Users/maverick/Projects/mavrov.de")).resolve()

MAX_READ_BYTES = 60_000
CMD_TIMEOUT = int(os.getenv("A2A_CMD_TIMEOUT", "600"))

# First token of a command must be in this allowlist.
ALLOWED_CMDS = {
    "git", "ls", "cat", "grep", "rg", "find", "head", "tail", "wc",
    "python", "python3", "pytest", "ruff", "mypy", "npm", "npx", "node",
    "curl", "echo", "true",
}
# Hard-blocked substrings (defense-in-depth against destructive/exfil commands).
BLOCKED = ("rm -rf", "rm -r /", "sudo", ":(){", "mkfs", "dd if=", "> /dev/",
           "chmod -R 777", "curl -X POST", "shutdown", "reboot")

# Mutating git subcommands are NEVER allowed via tools. Commits/tags/pushes and
# the release happen only through the gated orchestration layer, never ad-hoc by
# an agent mid-reasoning (an agent once impulsively committed a hallucinated file).
MUTATING_GIT = {"commit", "push", "tag", "reset", "checkout", "switch", "merge",
                "rebase", "clean", "add", "rm", "mv", "stash", "cherry-pick",
                "revert", "restore", "apply", "am", "update-ref", "pull", "fetch",
                "gc", "prune", "config"}

# Tool permission tiers. Read-only roles (researcher, analysts, reviewers, PM...)
# get READONLY_TOOLS only; write-capable roles (devs, integration) also get WRITE_TOOLS.
READONLY_TOOLS = {"read_file", "list_dir", "grep", "fetch_url", "run_tests", "gh_cli"}
WRITE_TOOLS = {"write_file", "edit_file", "run_command"}


def _safe_path(path: str) -> Path:
    p = (WORKDIR / path).resolve() if not os.path.isabs(path) else Path(path).resolve()
    if WORKDIR not in p.parents and p != WORKDIR:
        raise ValueError(f"path escapes workdir: {path}")
    return p


def read_file(path: str) -> str:
    p = _safe_path(path)
    if not p.is_file():
        return f"ERROR: not a file: {path}"
    data = p.read_text(errors="replace")
    return data[:MAX_READ_BYTES] + ("\n...[truncated]" if len(data) > MAX_READ_BYTES else "")


def list_dir(path: str = ".") -> str:
    p = _safe_path(path)
    if not p.is_dir():
        return f"ERROR: not a directory: {path}"
    entries = sorted(f"{c.name}/" if c.is_dir() else c.name for c in p.iterdir())
    return "\n".join(entries[:400])


def write_file(path: str, content: str) -> str:
    p = _safe_path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)
    return f"OK: wrote {len(content)} bytes to {path}"


def edit_file(path: str, old_string: str, new_string: str) -> str:
    """Surgical edit: replace an EXACT unique snippet in an existing file. Prevents
    the whole-file-overwrite hazard (an agent once deleted endpoints by rewriting a
    file). Fails if old_string is absent or not unique — forcing precise edits."""
    p = _safe_path(path)
    if not p.is_file():
        return f"ERROR: not a file: {path} (use write_file to create new files)"
    data = p.read_text()
    n = data.count(old_string)
    if n == 0:
        return "ERROR: old_string not found — read the file and copy an exact snippet."
    if n > 1:
        return f"ERROR: old_string occurs {n} times — include more context to make it unique."
    p.write_text(data.replace(old_string, new_string, 1))
    return f"OK: edited {path} (1 replacement)"


def grep(pattern: str, path: str = ".") -> str:
    return run_command(f"grep -rInE {shlex.quote(pattern)} {shlex.quote(path)}")


def run_command(command: str) -> str:
    """Run an allowlisted shell command inside WORKDIR."""
    lowered = command.lower()
    for bad in BLOCKED:
        if bad in lowered:
            return f"BLOCKED: command contains forbidden pattern '{bad}'"
    try:
        first = shlex.split(command)[0]
    except ValueError:
        return "ERROR: could not parse command"
    if first not in ALLOWED_CMDS:
        return (f"BLOCKED: '{first}' is not allowed. Allowed: {', '.join(sorted(ALLOWED_CMDS))}")
    parts = shlex.split(command)
    if first == "git" and len(parts) > 1 and parts[1] in MUTATING_GIT:
        return (f"BLOCKED: 'git {parts[1]}' is not permitted via tools. Commits, tags, pushes and "
                f"releases happen only through the gated orchestration layer, not ad-hoc.")
    try:
        proc = subprocess.run(
            command, shell=True, cwd=WORKDIR, capture_output=True, text=True,
            timeout=CMD_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        return f"ERROR: command timed out after {CMD_TIMEOUT}s"
    out = (proc.stdout or "") + (("\n[stderr]\n" + proc.stderr) if proc.stderr else "")
    return f"exit={proc.returncode}\n{out[:MAX_READ_BYTES]}"


def fetch_url(url: str) -> str:
    """Fetch a URL (GET only) for flexible external research — docs, changelogs,
    advisories, API references. No POST/side effects."""
    if not url.lower().startswith(("http://", "https://")):
        return "ERROR: only http(s) URLs allowed"
    try:
        import httpx

        resp = httpx.get(url, timeout=30, follow_redirects=True,
                         headers={"User-Agent": "mavrovde-agent/1.0"})
        text = resp.text
    except Exception as exc:  # noqa: BLE001
        return f"ERROR fetching {url}: {exc}"
    return f"HTTP {resp.status_code}\n{text[:MAX_READ_BYTES]}"


def gh_cli(args: str) -> str:
    """Read-only GitHub CLI access — inspect CI runs, PRs, issues, releases via
    `gh`. Mutating gh (merge/create/delete/cancel, non-GET api) is blocked;
    those happen only in the deterministic orchestration/release layer."""
    try:
        parts = shlex.split(args)
    except ValueError:
        return "ERROR: could not parse gh args"
    if not parts:
        return "ERROR: no gh args"
    read = {
        "run": {"list", "view"}, "pr": {"list", "view", "checks", "diff", "status"},
        "issue": {"list", "view"}, "release": {"list", "view"},
        "workflow": {"list", "view"}, "status": set(), "search": None, "api": None,
    }
    top = parts[0]
    if top not in read:
        return f"BLOCKED: 'gh {top}' not permitted (read-only gh only: {', '.join(read)})"
    if top == "api":
        low = args.lower()
        if any(x in low for x in ("--method post", "--method patch", "--method delete",
                                  "--method put", "-x post", "-x patch", "-x delete",
                                  "-x put", " -f ", "--field ", "--input")):
            return "BLOCKED: only GET `gh api` calls are allowed"
    elif read[top] is not None and len(parts) > 1 and parts[1] not in read[top]:
        return f"BLOCKED: 'gh {top} {parts[1]}' not permitted (allowed: {read[top]})"
    try:
        r = subprocess.run(f"gh {args}", shell=True, cwd=WORKDIR, capture_output=True,
                           text=True, timeout=CMD_TIMEOUT)
    except subprocess.TimeoutExpired:
        return f"ERROR: gh timed out after {CMD_TIMEOUT}s"
    return f"exit={r.returncode}\n{(r.stdout or r.stderr)[:MAX_READ_BYTES]}"


def run_tests(layer: str = "backend") -> str:
    """Convenience wrapper mapping to the project's real test commands."""
    if layer == "backend":
        # Use the main checkout's venv by absolute path: a fresh worktree has no
        # venv of its own (it's gitignored), so a relative path would fail to run.
        # Include coverage at the SAME floor as the deterministic gate so an agent's
        # self-check matches what the gate will enforce (no "tests pass but gate fails
        # on coverage" surprise).
        cov = os.getenv("A2A_COV_MIN", "95")
        return run_command(
            "TESTING=true /Users/maverick/Projects/mavrov.de/backend/venv/bin/python "
            f"-m pytest backend/tests -q -p no:cacheprovider --cov=app --cov-report= "
            f"--cov-fail-under={cov}"
        )
    if layer == "frontend":
        return run_command("bash -lc 'cd frontend && npx vitest run'")
    return f"ERROR: unknown layer '{layer}' (use backend|frontend)"


# --- Tool registry + JSON schemas for the LLM (Ollama/Anthropic tool-calling) --

REGISTRY = {
    "read_file": read_file,
    "list_dir": list_dir,
    "write_file": write_file,
    "edit_file": edit_file,
    "grep": grep,
    "run_command": run_command,
    "run_tests": run_tests,
    "fetch_url": fetch_url,
    "gh_cli": gh_cli,
}


def _p(props, required):
    return {"type": "object", "properties": props, "required": required}


TOOL_SCHEMAS = [
    {"type": "function", "function": {
        "name": "read_file", "description": "Read a UTF-8 text file (repo-relative path).",
        "parameters": _p({"path": {"type": "string"}}, ["path"])}},
    {"type": "function", "function": {
        "name": "list_dir", "description": "List a directory's entries.",
        "parameters": _p({"path": {"type": "string"}}, [])}},
    {"type": "function", "function": {
        "name": "grep", "description": "Recursively regex-search files for a pattern.",
        "parameters": _p({"pattern": {"type": "string"}, "path": {"type": "string"}}, ["pattern"])}},
    {"type": "function", "function": {
        "name": "write_file",
        "description": "Create a NEW file (or fully replace one you intend to rewrite). For changing "
                       "existing files, prefer edit_file to avoid deleting unrelated code.",
        "parameters": _p({"path": {"type": "string"}, "content": {"type": "string"}}, ["path", "content"])}},
    {"type": "function", "function": {
        "name": "edit_file",
        "description": "Surgically replace an exact, unique snippet in an existing file. Use this for "
                       "changes to existing files so you never delete unrelated code.",
        "parameters": _p({"path": {"type": "string"}, "old_string": {"type": "string"},
                          "new_string": {"type": "string"}}, ["path", "old_string", "new_string"])}},
    {"type": "function", "function": {
        "name": "run_command",
        "description": "Run an allowlisted dev shell command (git/pytest/npm/ruff/...) in the repo.",
        "parameters": _p({"command": {"type": "string"}}, ["command"])}},
    {"type": "function", "function": {
        "name": "run_tests", "description": "Run the project's tests for a layer.",
        "parameters": _p({"layer": {"type": "string", "enum": ["backend", "frontend"]}}, [])}},
    {"type": "function", "function": {
        "name": "fetch_url",
        "description": "HTTP GET a URL for external research (docs, advisories, references).",
        "parameters": _p({"url": {"type": "string"}}, ["url"])}},
    {"type": "function", "function": {
        "name": "gh_cli",
        "description": "Read-only GitHub CLI: inspect CI runs, PRs, issues, releases "
                       "(e.g. 'run list --branch main', 'pr view 12', 'api /repos/o/r/dependabot/alerts').",
        "parameters": _p({"args": {"type": "string"}}, ["args"])}},
]


def schemas_for(names: set[str]) -> list[dict]:
    """The subset of tool schemas a role is allowed to use."""
    return [s for s in TOOL_SCHEMAS if s["function"]["name"] in names]


def execute_tool(name: str, arguments: dict, allowed: set[str] | None = None) -> str:
    if allowed is not None and name not in allowed:
        return f"BLOCKED: tool '{name}' is not permitted for this role."
    fn = REGISTRY.get(name)
    if fn is None:
        return f"ERROR: unknown tool '{name}'"
    try:
        return str(fn(**(arguments or {})))
    except Exception as exc:  # noqa: BLE001 - report tool errors back to the model
        return f"ERROR calling {name}: {exc}"
