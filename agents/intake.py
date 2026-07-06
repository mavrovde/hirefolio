"""Feature-spec intake — the team watches specs/inbox/ and implements what it finds.

Drop a Markdown spec in `specs/inbox/`, then:

    python -m agents.intake                 # process every pending spec (opens a PR each)
    python -m agents.intake --auto-release  # fully autonomous (merge+release)
    python -m agents.intake --once          # only the first pending spec

Each processed spec runs the full autonomous pipeline (research → ... → PR) and is
then moved to `specs/done/` with a result footer appended. `--watch N` polls the
inbox every N seconds so you can just keep dropping specs.
"""
from __future__ import annotations

import argparse
import asyncio
import os
import time

from agents import autonomous

REPO = autonomous.REPO
INBOX = os.path.join(REPO, "specs", "inbox")
DONE = os.path.join(REPO, "specs", "done")
IGNORE = {"README.md", "TEMPLATE.md", ".gitkeep"}


def pending_specs() -> list[str]:
    """Markdown specs waiting in specs/inbox/ (sorted, oldest first)."""
    if not os.path.isdir(INBOX):
        return []
    files = [f for f in os.listdir(INBOX)
             if f.endswith(".md") and f not in IGNORE and not f.startswith(".")]
    return sorted(files, key=lambda f: os.path.getmtime(os.path.join(INBOX, f)))


def _slug_from_filename(name: str) -> str:
    return autonomous.slugify(os.path.splitext(name)[0])


async def process_spec(name: str, auto_release: bool) -> dict:
    path = os.path.join(INBOX, name)
    spec_text = open(path).read()
    slug = _slug_from_filename(name)
    goal = (f"Implement the feature specified below (from specs/inbox/{name}). "
            f"Follow the spec exactly; keep the change minimal and consistent.\n\n{spec_text}")
    print(f"\n=== intake: {name} -> branch agent/{slug} ===", flush=True)
    result = await autonomous.run(goal, auto_release=auto_release, slug=slug)

    # Move to done/ with a result footer so it isn't reprocessed.
    os.makedirs(DONE, exist_ok=True)
    footer = (f"\n\n---\n## Intake result ({time.strftime('%Y-%m-%d %H:%M')})\n"
              f"- branch: `{result.get('branch')}`\n"
              f"- gate green: {result.get('gate_green')}\n"
              f"- outcome: {result.get('finalized')}\n"
              f"- run log: `{result.get('runlog')}`\n")
    with open(os.path.join(DONE, name), "w") as f:
        f.write(spec_text + footer)
    os.remove(path)
    print(f"=== intake: {name} done -> {result.get('finalized')} ===", flush=True)
    return result


async def _run(args) -> None:
    while True:
        specs = pending_specs()
        if not specs:
            if not args.watch:
                print("No pending specs in specs/inbox/.")
                return
            await asyncio.sleep(args.watch)
            continue
        for name in (specs[:1] if args.once else specs):
            try:
                await process_spec(name, args.auto_release)
            except Exception as exc:  # noqa: BLE001 - keep going to the next spec
                print(f"[intake] {name} failed: {exc}", flush=True)
        if not args.watch:
            return


def main() -> None:
    ap = argparse.ArgumentParser(description="Feature-spec intake for the A2A team")
    ap.add_argument("--auto-release", action="store_true",
                    help="auto-merge+release instead of opening a PR")
    ap.add_argument("--once", action="store_true", help="process only the first pending spec")
    ap.add_argument("--watch", type=int, metavar="SECONDS", default=0,
                    help="keep polling the inbox every SECONDS")
    args = ap.parse_args()
    args.auto_release = args.auto_release or os.getenv("A2A_AUTORELEASE") == "1"
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()
