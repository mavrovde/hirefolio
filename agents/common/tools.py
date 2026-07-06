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
           "chmod -R 777", "curl -X POST", "git push --force", "shutdown", "reboot")


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


def run_tests(layer: str = "backend") -> str:
    """Convenience wrapper mapping to the project's real test commands."""
    if layer == "backend":
        return run_command(
            "TESTING=true backend/venv/bin/python -m pytest backend/tests -q -p no:cacheprovider"
        )
    if layer == "frontend":
        return run_command("bash -lc 'cd frontend && npx vitest run'")
    return f"ERROR: unknown layer '{layer}' (use backend|frontend)"


# --- Tool registry + JSON schemas for the LLM (Ollama/Anthropic tool-calling) --

REGISTRY = {
    "read_file": read_file,
    "list_dir": list_dir,
    "write_file": write_file,
    "grep": grep,
    "run_command": run_command,
    "run_tests": run_tests,
    "fetch_url": fetch_url,
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
        "name": "write_file", "description": "Create/overwrite a repo file with content.",
        "parameters": _p({"path": {"type": "string"}, "content": {"type": "string"}}, ["path", "content"])}},
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
]


def execute_tool(name: str, arguments: dict) -> str:
    fn = REGISTRY.get(name)
    if fn is None:
        return f"ERROR: unknown tool '{name}'"
    try:
        return str(fn(**(arguments or {})))
    except Exception as exc:  # noqa: BLE001 - report tool errors back to the model
        return f"ERROR calling {name}: {exc}"
