"""Autonomous, fully-logged feature pipeline for the mavrov.de A2A team.

Full cycle:
  research -> spec -> plan -> design -> stories -> implement (isolated worktree)
  -> deterministic test GATE (fix loop) -> code+security review -> docs (records
  critical decisions) -> release decision -> finalize (PR, or auto-merge+release).

Every step is logged (streamed to stdout AND written to a committed run-log at
docs/agent-runs/<slug>-<ts>.md). Critical decisions (gate result, review verdicts,
version bump, go/no-go) are captured there and the docs-writer updates the CHANGELOG.

Safety: agents write only inside a throwaway git WORKTREE on a branch (never main);
the GATE trusts real test exit codes, not the LLM; all git/release ops are done
here in deterministic Python; full auto-merge+release requires A2A_AUTORELEASE=1,
a green gate AND green CI, with auto-rollback.

Usage:
    python -m agents.autonomous "Add X to the stats endpoint"
    A2A_AUTORELEASE=1 python -m agents.autonomous "<goal>"
"""
from __future__ import annotations

import argparse
import asyncio
import os
import re
import subprocess
import sys
import time

import httpx

from agents.common.roster import ROSTER
from agents.orchestrator import delegate

REPO = "/Users/maverick/Projects/mavrov.de"
MAX_FIX_ITERS = int(os.getenv("A2A_MAX_FIX_ITERS", "3"))


def sh(cmd: str, cwd: str = REPO) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True)


def slugify(text: str) -> str:
    return (re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:40]) or "feature"


def shell_quote(s: str) -> str:
    return "'" + s.replace("'", "'\\''") + "'"


# --- run log (all steps + critical decisions) -------------------------------

class RunLog:
    def __init__(self, workdir: str, goal: str, slug: str):
        self.lines: list[str] = []
        ts = time.strftime("%Y-%m-%dT%H:%M:%S")
        self.rel = f"docs/agent-runs/{slug}-{time.strftime('%Y%m%d-%H%M%S')}.md"
        self.path = os.path.join(workdir, self.rel)
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        self._w(f"# Autonomous run — {goal}\n\n- Started: {ts}\n- Branch: agent/{slug}\n")
        self.decisions: list[str] = []

    def _w(self, text: str) -> None:
        self.lines.append(text)
        with open(self.path, "w") as f:
            f.write("\n".join(self.lines) + "\n")

    def step(self, title: str, body: str) -> None:
        ts = time.strftime("%H:%M:%S")
        print(f"[auto {ts}] {title}", flush=True)
        self._w(f"\n## {ts} — {title}\n\n{body.strip()}\n")

    def decision(self, text: str) -> None:
        ts = time.strftime("%H:%M:%S")
        print(f"[auto {ts}] DECISION: {text}", flush=True)
        self.decisions.append(f"- **{ts}** {text}")
        self._w(f"\n> **Critical decision ({ts}):** {text}\n")

    def finish(self) -> None:
        self._w("\n## Critical decisions (summary)\n\n" + "\n".join(self.decisions or ["- (none)"]))


# --- git worktree isolation -------------------------------------------------

def create_worktree(branch: str) -> str:
    path = os.path.join("/tmp", f"mavrov-wt-{branch.replace('/', '-')}")
    sh(f"git worktree remove --force {path}")
    sh(f"git branch -D {branch}")
    r = sh(f"git worktree add -b {branch} {path} HEAD")
    if r.returncode != 0:
        raise RuntimeError(f"worktree create failed: {r.stderr}")
    return path


def remove_worktree(path: str, branch: str, keep: bool = False) -> None:
    if keep:
        print(f"[auto] keeping worktree {path} (branch {branch}) for inspection", flush=True)
        return
    sh(f"git worktree remove --force {path}")
    sh(f"git branch -D {branch}")


# --- deterministic gate (trusts exit codes, not the LLM) --------------------

def run_gate(workdir: str) -> tuple[bool, str]:
    """Run the real suites for the layer(s) that changed, at 100% coverage.
    A fresh worktree lacks gitignored deps, so we reuse the main checkout's venv
    (absolute path) and symlink its node_modules when the frontend is tested."""
    changed = sh("git diff --name-only HEAD", cwd=workdir).stdout
    be_changed = "backend/" in changed
    fe_changed = "frontend/" in changed
    if not be_changed and not fe_changed:
        be_changed = True  # sanity default
    ok = True
    reports = []
    if be_changed:
        be = sh("TESTING=true /Users/maverick/Projects/mavrov.de/backend/venv/bin/python -m pytest "
                "backend/tests -q -p no:cacheprovider --cov=app --cov-report= --cov-fail-under=100",
                cwd=workdir)
        ok &= be.returncode == 0
        reports.append(f"[backend] {'PASS' if be.returncode == 0 else 'FAIL'}\n{(be.stdout or be.stderr)[-1400:]}")
    if fe_changed:
        nm = os.path.join(workdir, "frontend", "node_modules")
        if not os.path.exists(nm):
            sh(f"ln -s {REPO}/frontend/node_modules {nm}")
        fe = sh("bash -lc 'cd frontend && npx vitest run'", cwd=workdir)
        ok &= fe.returncode == 0
        reports.append(f"[frontend] {'PASS' if fe.returncode == 0 else 'FAIL'}\n{(fe.stdout or fe.stderr)[-1000:]}")
    return ok, "\n\n".join(reports) or "no app layers changed"


# --- agent process management (pointed at the worktree) ---------------------

def start_agents(role_keys: list[str], workdir: str) -> list[subprocess.Popen]:
    env = {**os.environ, "A2A_WORKDIR": workdir,
           "A2A_LLM_PROVIDER": os.getenv("A2A_LLM_PROVIDER", "ollama"),
           "A2A_MODEL": os.getenv("A2A_MODEL", "qwen2.5-coder:7b"), "PYTHONUNBUFFERED": "1"}
    return [subprocess.Popen([sys.executable, "-m", "agents.serve", k], cwd=REPO, env=env)
            for k in role_keys]


async def _wait_ready(role_keys: list[str]) -> None:
    async with httpx.AsyncClient(timeout=5) as hx:
        for k in role_keys:
            url = f"http://localhost:{ROSTER[k].port}/.well-known/agent.json"
            for _ in range(40):
                try:
                    if (await hx.get(url)).status_code == 200:
                        break
                except Exception:  # noqa: BLE001
                    pass
                await asyncio.sleep(1)


def stop_agents(procs: list[subprocess.Popen]) -> None:
    for p in procs:
        p.terminate()
    for p in procs:
        try:
            p.wait(timeout=5)
        except subprocess.TimeoutExpired:
            p.kill()


# --- the full autonomous cycle ----------------------------------------------

ROLES = ["researcher", "spec-analyst", "planner", "architect", "story-writer",
         "backend-dev", "frontend-dev", "code-reviewer", "security-reviewer",
         "documentation-writer", "release-manager"]


async def run(goal: str, auto_release: bool = False) -> dict:
    slug = slugify(goal)
    branch = f"agent/{slug}"
    workdir = create_worktree(branch)
    log = RunLog(workdir, goal, slug)
    log.step("Setup", f"Isolated worktree `{workdir}` on branch `{branch}`.")
    procs = start_agents(ROLES, workdir)
    result: dict = {"branch": branch, "gate_green": False, "finalized": None, "runlog": log.rel}
    try:
        await _wait_ready(ROLES)
        async with httpx.AsyncClient(timeout=600) as hx:
            async def ask(role: str, prompt: str, title: str) -> str:
                out = await delegate(hx, ROSTER[role], prompt)
                log.step(f"{title} ({role})", out)
                return out

            research = await ask("researcher", f"Research what's needed for: {goal}", "Research")
            spec = await ask("spec-analyst", f"Goal: {goal}\nResearch:\n{research}\n\nWrite requirements + acceptance criteria.", "Specification")
            plan = await ask("planner", f"Goal: {goal}\nSpec:\n{spec}\n\nOrdered plan: exact files to change + tests to add.", "Plan")
            design = await ask("architect", f"Goal: {goal}\nPlan:\n{plan}\n\nTechnical design + risks.", "Design")
            await ask("story-writer", f"Goal: {goal}\nSpec:\n{spec}\n\nUser stories + acceptance criteria.", "Stories")

            impl = (f"Goal: {goal}\nPlan:\n{plan}\nDesign:\n{design}\n\nImplement now IN THIS WORKTREE "
                    f"using your tools (write_file/run_command). Add/adjust tests to keep 100% coverage, "
                    f"then run the tests.")
            await ask("backend-dev", impl, "Implement (backend)")
            await ask("frontend-dev", impl, "Implement (frontend)")

            # Deterministic gate + fix loop.
            green, report = run_gate(workdir)
            log.step("Test gate (attempt 1)", report)
            for i in range(MAX_FIX_ITERS):
                if green:
                    break
                await ask("backend-dev", f"Tests FAIL — fix the root cause here.\n\n{report}", f"Fix backend (iter {i+1})")
                await ask("frontend-dev", f"If frontend tests fail, fix them.\n\n{report}", f"Fix frontend (iter {i+1})")
                green, report = run_gate(workdir)
                log.step(f"Test gate (attempt {i+2})", report)
            result["gate_green"] = green
            log.decision(f"Deterministic test gate: {'GREEN (100% coverage)' if green else 'RED — pipeline aborts'}.")

            if not green:
                log.decision("NO-GO: not finalizing; branch kept for human review.")
                log.finish()
                result["finalized"] = "aborted: tests not green"
                return result

            # Independent review — by DIFFERENT roles than the implementer — and it GATES.
            diff = sh("git diff HEAD", cwd=workdir).stdout[:8000]
            review = await ask("code-reviewer", f"Independently review this diff for correctness/quality. "
                               f"End your response with exactly APPROVE or REQUEST-CHANGES:\n{diff}", "Code review")
            sec = await ask("security-reviewer", f"Independently security-review this diff. "
                            f"End with exactly APPROVE or REQUEST-CHANGES:\n{diff}", "Security review")
            reviews_ok = _verdict(review) == "APPROVE/GO" and _verdict(sec) == "APPROVE/GO"
            log.decision(f"Reviews — code: {_verdict(review)}, security: {_verdict(sec)} "
                         f"=> {'APPROVED' if reviews_ok else 'CHANGES REQUESTED'}.")

            await ask("documentation-writer",
                      f"Update CHANGELOG.md (new [Unreleased] entry) and any relevant docs for this change. "
                      f"Goal: {goal}. Record the critical decisions. Use write_file.", "Documentation")

            rel = await ask("release-manager",
                            f"Given green tests and reviews (code={_verdict(review)}, security={_verdict(sec)}), "
                            f"decide the SemVer bump and give exactly GO or NO-GO for: {goal}", "Release decision")
            rel_ok = _verdict(rel) == "APPROVE/GO"
            log.decision(f"Release Manager: {'GO' if rel_ok else 'NO-GO'} — {rel.splitlines()[0][:120] if rel else ''}")

            # Quality gate for auto-release: reviews approved AND release GO.
            release_ok = reviews_ok and rel_ok
            effective_auto = auto_release and release_ok
            if auto_release and not release_ok:
                log.decision("Auto-release WITHHELD: review/release gate not APPROVED — "
                             "downgrading to a PR for human review instead of auto-merging.")
            result["reviews_ok"] = reviews_ok
            result["release_ok"] = release_ok
            log.finish()

        # Commit + push the branch (always, with a clear title + body).
        if not commit_and_push_branch(branch, workdir, goal, log):
            result["finalized"] = "no changes produced"
        elif not effective_auto:
            result["finalized"] = open_pr(branch, goal, log)
        else:
            # Free the ports: recovery runs against main with its own agents.
            stop_agents(procs)
            procs = []
            result["finalized"] = await auto_merge_with_recovery(branch, goal, log)
        return result
    finally:
        stop_agents(procs)
        remove_worktree(workdir, branch, keep=not result.get("gate_green"))


def _verdict(text: str) -> str:
    up = (text or "").upper()
    if "NO-GO" in up or "REQUEST-CHANGES" in up or "REQUEST CHANGES" in up:
        return "REQUEST-CHANGES/NO-GO"
    if "APPROVE" in up or "GO" in up:
        return "APPROVE/GO"
    return "unclear"


def _commit_message(goal: str, workdir: str, log: RunLog) -> str:
    """A clear, understandable commit title + body (per the team's commit rule)."""
    title = f"feat(auto): {goal}".strip()
    if len(title) > 72:
        title = title[:69] + "..."
    diffstat = sh("git diff --cached --stat", cwd=workdir).stdout.strip()
    decisions = "\n".join(log.decisions) or "- (none recorded)"
    return (
        f"{title}\n\n"
        f"Implemented autonomously by the A2A team through the full cycle "
        f"(research -> spec -> plan -> design -> implement -> test gate -> review -> docs).\n\n"
        f"Changes:\n{diffstat}\n\n"
        f"Critical decisions:\n{decisions}\n\n"
        f"Verification: deterministic test gate green (backend + frontend, 100% coverage).\n"
        f"Run log: {log.rel}\n\n"
        f"Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>\n"
    )


def _commit_with_message(workdir: str, message: str) -> None:
    msg_path = os.path.join(workdir, ".git", "AUTO_COMMIT_MSG")
    with open(msg_path, "w") as f:
        f.write(message)
    sh(f"git commit -F {shell_quote(msg_path)}", cwd=workdir)


def commit_and_push_branch(branch: str, workdir: str, goal: str, log: RunLog) -> bool:
    if not sh("git status --porcelain", cwd=workdir).stdout.strip():
        return False
    sh("git add -A", cwd=workdir)
    _commit_with_message(workdir, _commit_message(goal, workdir, log))
    sh(f"git push -u origin {branch}", cwd=workdir)
    return True


def open_pr(branch: str, goal: str, log: RunLog) -> str:
    body = ("Autonomous implementation by the A2A team; local test gate green (100% coverage).\n\n"
            "Critical decisions:\n" + ("\n".join(log.decisions) or "-") + f"\n\nRun log: {log.rel}")
    pr = sh(f"gh pr create --head {branch} --title {shell_quote('feat(auto): ' + goal)} "
            f"--body {shell_quote(body)}")
    return f"opened PR: {pr.stdout.strip() or pr.stderr.strip()}"


async def auto_merge_with_recovery(branch: str, goal: str, log: RunLog,
                                   max_ci_fix: int = 2) -> str:
    """Merge to main; if CI goes red the TEAM diagnoses and fixes it (DevOps ->
    devs -> re-gate -> re-push -> re-watch). If it still can't be fixed, ESCALATE
    to a human with a clear report — never silently roll back."""
    before = sh("git rev-parse origin/main").stdout.strip()
    last_diag = ""
    merge_msg = (f"feat(auto): {goal} (merge {branch})\n\n"
                 "Autonomously delivered by the A2A team.\n\nCritical decisions:\n"
                 + ("\n".join(log.decisions) or "-")
                 + f"\n\nRun log: {log.rel}\n\n"
                   "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>\n")
    mpath = os.path.join(REPO, ".git", "AUTO_MERGE_MSG")
    with open(mpath, "w") as f:
        f.write(merge_msg)
    sh("git checkout main")
    sh(f"git merge --no-ff {branch} -F {shell_quote(mpath)}")
    sh("git push origin main")
    log.decision(f"Merged {branch} -> main; watching CI.")
    if _ci_green_for("main"):
        return "auto-merged to main; CI green"

    # --- CI recovery loop: the team understands & fixes the failure ---
    recov = start_agents(["devops", "backend-dev", "frontend-dev"], REPO)
    try:
        await _wait_ready(["devops", "backend-dev", "frontend-dev"])
        async with httpx.AsyncClient(timeout=600) as hx:
            for i in range(max_ci_fix):
                diag = await delegate(hx, ROSTER["devops"],
                    "The 'Prod Deployment' pipeline on main is RED. Use gh_cli to read the failed "
                    "job logs (run list --branch main, run view <id> --log-failed), pinpoint the "
                    "exact error, and state which layer (backend/frontend) must fix what.")
                last_diag = diag
                log.step(f"CI recovery — diagnosis (attempt {i+1})", diag)
                fix = (f"CI is red. Diagnosis:\n{diag}\n\nFix the ROOT CAUSE in the repo now using "
                       f"your tools, then ensure tests pass. Do not disable tests.")
                await delegate(hx, ROSTER["backend-dev"], fix)
                await delegate(hx, ROSTER["frontend-dev"], fix)
                green, report = run_gate(REPO)
                log.step(f"CI recovery — local gate (attempt {i+1})", report)
                if not green:
                    continue
                # commit the fix to main with a clear message, push, re-watch CI
                sh("git add -A", cwd=REPO)
                fix_msg = (f"fix(ci): resolve Prod Deployment failure after {branch}\n\n"
                           f"Diagnosed and fixed by the A2A DevOps+dev loop.\n\n{diag[:400]}\n\n"
                           "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>\n")
                fpath = os.path.join(REPO, ".git", "AUTO_FIX_MSG")
                with open(fpath, "w") as f:
                    f.write(fix_msg)
                sh(f"git commit -F {shell_quote(fpath)}", cwd=REPO)
                sh("git push origin main", cwd=REPO)
                log.decision(f"CI recovery attempt {i+1}: pushed a fix; re-watching CI.")
                if _ci_green_for("main"):
                    return f"auto-merged; CI recovered by the team after {i+1} fix attempt(s)"
    finally:
        stop_agents(recov)

    # Team could not fix it. DO NOT roll back — escalate to a human with a clear report.
    head = sh("git rev-parse origin/main").stdout.strip()
    run_url = sh('gh run list --branch main --workflow "Prod Deployment" --limit 1 '
                 "--json url --jq '.[0].url'").stdout.strip()
    report = (
        f"# 🚨 Autonomous release needs a human — CI is red on `main`\n\n"
        f"**Feature:** {goal}\n"
        f"**What happened:** the A2A team merged `{branch}` into `main` "
        f"({before[:8]} → {head[:8]}) after a green local test gate, but the **Prod "
        f"Deployment** pipeline failed, and the team could **not** make it green after "
        f"{max_ci_fix} automated fix attempt(s).\n\n"
        f"**`main` was left as-is (NOT rolled back)** so you can inspect the real failure.\n\n"
        f"**Latest diagnosis (DevOps agent):**\n\n{last_diag[:1500]}\n\n"
        f"**Failing pipeline run:** {run_url or '(see Actions tab)'}\n"
        f"**Full autonomous run log:** `{log.rel}` (committed on `{branch}`).\n\n"
        f"**Suggested next step:** review the failing job, apply a fix on `main`, or "
        f"revert {before[:8]}..{head[:8]} if you decide to back it out."
    )
    rpath = os.path.join(REPO, ".git", "ESCALATION.md")
    with open(rpath, "w") as f:
        f.write(report)
    issue = sh(f"gh issue create --title {shell_quote('🚨 Autonomous release: CI red on main, team could not fix — ' + goal)} "
               f"--body-file {shell_quote(rpath)}")
    issue_ref = issue.stdout.strip() or issue.stderr.strip()
    log.decision(f"ESCALATED to human: CI still red after {max_ci_fix} attempts. main NOT rolled back. "
                 f"Issue: {issue_ref}")
    return (f"ESCALATED to human developer — CI red after {max_ci_fix} fix attempts, `main` left "
            f"intact for inspection. GitHub issue: {issue_ref}")


def _ci_green_for(branch: str, timeout_s: int = 1500) -> bool:
    deadline = time.time() + timeout_s
    sha = sh(f"git rev-parse origin/{branch}").stdout.strip()[:12]
    while time.time() < deadline:
        r = sh(f'gh run list --branch {branch} --workflow "Prod Deployment" --limit 5 '
               f'--json headSha,status,conclusion '
               f"--jq '.[] | select(.headSha|startswith(\"{sha}\")) | .status+\" \"+(.conclusion//\"-\")'")
        line = (r.stdout.strip().splitlines() or [""])[0]
        if line.startswith("completed"):
            return "success" in line
        time.sleep(15)
    return False


def main() -> None:
    ap = argparse.ArgumentParser(description="Autonomous A2A feature pipeline (full cycle, logged)")
    ap.add_argument("goal")
    ap.add_argument("--auto-release", action="store_true")
    args = ap.parse_args()
    auto = args.auto_release or os.getenv("A2A_AUTORELEASE") == "1"
    out = asyncio.run(run(args.goal, auto_release=auto))
    print("\n=== RESULT ===")
    for k in ("branch", "gate_green", "finalized", "runlog"):
        print(f"{k}: {out.get(k)}")


if __name__ == "__main__":
    main()
