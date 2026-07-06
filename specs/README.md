# Feature specs → autonomous implementation

Drop a Markdown feature spec into **`specs/inbox/`**, then let the A2A team pick it up
and implement it end-to-end (research → spec analysis → plan → implement → test gate →
review → docs → PR).

## How to use

1. Copy `TEMPLATE.md`, fill it in, and save it as `specs/inbox/<short-name>.md`
   (the file name becomes the branch, e.g. `add-uptime-field.md` → `agent/add-uptime-field`).
   See `EXAMPLE.md` for a filled-in example.
2. Make sure a brain is configured (recommended: Claude — it clears the gate reliably):
   ```bash
   export A2A_LLM_PROVIDER=anthropic A2A_MODEL=claude-sonnet-4-6
   export ANTHROPIC_API_KEY="$(security find-generic-password -s anthropic-api-key -w)"
   # (or Ollama: A2A_LLM_PROVIDER=ollama A2A_MODEL=qwen2.5-coder:7b — free, weaker)
   ```
   Also ensure the dev DB is up (`docker compose up -d db`) for the backend test gate.
3. Run the intake:
   ```bash
   python -m agents.intake                 # process all pending specs -> opens a PR each
   python -m agents.intake --once          # just the first pending spec
   python -m agents.intake --watch 60      # keep polling the inbox every 60s
   python -m agents.intake --auto-release  # fully autonomous (merge + release, gated)
   ```

## What happens

- Each spec runs the full autonomous pipeline in an **isolated git worktree/branch**.
- A **deterministic test gate** (backend+frontend, ≥95% coverage) must pass; code +
  security review must approve for auto-release. Otherwise it opens a **PR for you**.
- The spec is moved to **`specs/done/`** with a result footer (branch, gate, outcome,
  run-log). If CI can't be made green on an auto-release, the team **escalates via a
  GitHub issue** — it never silently rolls back.

## Writing a good spec

Be concrete and testable. Say exactly what the feature does, the API/UI contract
(paths, request/response shapes), and acceptance criteria. The clearer the spec, the
cleaner the implementation and its tests.
