# CD automation onto the 1Panel host — options & trade-offs

> Investigation for **[#156](https://github.com/mavrovde/mavrov.de/issues/156)** (closes **[#112](https://github.com/mavrovde/mavrov.de/issues/112)**, milestone *CI/CD, tooling & docs*).
> Status: **design/decision doc** — no prod access was opened and nothing on the host was touched.

## The gap

`.github/workflows/deploy.yml` builds → runs the Docker E2E → **publishes** `sha-<gitsha>` images to
ghcr — and **stops**. There is no step that rolls those images onto the live `mavrov.de` host; the
owner pulls & redeploys by hand in **1Panel**'s Docker-Compose UI. So a "green" pipeline means the
images are **published**, not **live**.

A second, concrete drift to fix along the way: prod pulls
`${IMAGE_REPO:-maverickde/mavrov.de}-*:${IMAGE_TAG:-1.8.2}` (`docker-compose.prod.yml`), while CI
publishes `ghcr.io/mavrovde/mavrov.de-*:sha-<gitsha>` — a **different registry/repo and a static
tag**. Any automation must reconcile the image coordinates so the host pulls the exact validated
images.

## Decision matrix

| Option | Trigger | Inbound access | Control (tag-pin · health-gate · rollback) | Panel-native | Effort | Verdict |
|---|---|---|---|---|---|---|
| **1. SSH rollout job** (Actions → host) | event | yes — SSH | ●●● | no | medium | ◆ **Recommended** |
| **2. 1Panel API trigger** (signed HTTP) | event | yes — HTTPS | ●●○ | yes | medium | Alternative |
| **3. 1Panel scheduled task** (cron pull) | poll | none | ●○○ | yes | low | Fallback |
| **4. Webhook receiver** (host service) | event | yes — HTTPS | ●●○ | no | high | Alternative |
| **5. Watchtower** (registry watcher) | poll | none | ●○○ | no | low | Rejected as primary |

---

## 1. SSH-based rollout job — ◆ Recommended

After publish, a `deploy` job (`needs:` the publish jobs) connects to the host, writes the validated
`IMAGE_TAG` into the Compose project's `.env` that 1Panel manages, then `docker compose pull && up -d`,
health-checks, and rolls the tag back on failure. 1Panel keeps owning the Compose file; CI just
triggers the update.

**Pro**
- True **merge → live**, tied to the exact E2E-validated commit.
- Pins the precise `sha-<gitsha>` images — no drift.
- **Health-gated + automatic rollback** baked into one script.
- Panel-agnostic and well-understood; nothing new to learn.

**Contra**
- Needs inbound SSH to the host.
- GitHub runner egress IPs are broad/dynamic → pair with a **self-hosted runner** or a
  **Tailscale / Cloudflare tunnel**.
- Or harden: dedicated non-root user, **forced-command** key, IP allowlist, fail2ban.

*access: SSH (hardened) · rollback: scripted · effort: medium*

---

## 2. 1Panel API trigger — Alternative

CI calls 1Panel's own REST API to recreate the Compose project — no raw shell. Enabled under
*Panel Settings → API Interface* (API key + IP allowlist); each request is signed with a timestamped
MD5 token.

**Pro**
- Panel-native — 1Panel stays the source of truth, with an audit trail.
- No shell access; API-key + IP-allowlist auth.
- Reuses the operator's existing management surface.

**Contra**
- Couples to the 1Panel API surface — must confirm the compose `operate: up` endpoint actually
  **pulls**.
- Same broad-runner-IP vs allowlist problem as SSH.
- The API key is a **full-panel** credential — scope & rotate carefully.
- Still must land the new `IMAGE_TAG` on the host; needs NTP time-sync.

**Confirmed request signing:**

```bash
# Token = md5('1panel' + API-Key + unix-seconds)
TS=$(date +%s)
TOKEN=$(printf '1panel%s%s' "$KEY" "$TS" | md5sum | cut -d' ' -f1)
curl -X POST "https://host:port/api/v2/containers/compose/operate" \
  -H "1Panel-Token: $TOKEN" -H "1Panel-Timestamp: $TS" \
  -d '{"name":"mavrov","operation":"up"}'
```
Headers `1Panel-Token` + `1Panel-Timestamp`; wrong/expired → `401 "API interface key error"`.
Docs: <https://docs.1panel.pro/dev_manual/api_manual/>.

*access: HTTPS + signed key · rollback: manual · effort: medium*

---

## 3. 1Panel scheduled task (cron pull) — Fallback

A 1Panel "Scheduled Task" runs a shell script on the host every N minutes:
`docker compose pull && up -d`. No CI change, no inbound access at all.

**Pro**
- **Zero inbound access** — nothing to open or harden.
- Simplest possible; uses 1Panel's own cron UI.
- Great interim step while the real pipeline is built.

**Contra**
- Polling — a lag between merge and live.
- Must diff image digests or it redeploys on every tick.
- Not tied to a specific validated commit; no health-gate / rollback.

*access: none · rollback: none · effort: low*

---

## 4. Webhook receiver on the host — Alternative

A tiny endpoint on the host that CI calls after publish; it runs the Compose update. Event-driven
without granting full SSH.

**Pro**
- Event-driven, no raw shell exposure.
- Can encode exactly the pull → up → health-check → rollback flow.

**Contra**
- Another service to **build, secure, and keep running**.
- Needs its own auth (shared secret / HMAC) and inbound HTTPS.
- More moving parts than the SSH job for the same outcome.

*access: HTTPS + HMAC · rollback: scripted · effort: high*

---

## 5. Watchtower — Rejected as primary

A container that watches the registry and auto-updates running services when a new image appears.

**Pro**
- Trivial to set up; zero CI change.
- Fully hands-off once running.

**Contra**
- No ordering control across services.
- **No health-gate, no rollback** — a bad image just goes live.
- Risky for a multi-service stack that runs DB migrations on startup.
- Auto-updates can surprise you at any hour.

*access: none · rollback: none · effort: low*

---

## Recommendation

**Ship the SSH rollout job; keep the cron pull as the zero-inbound fallback.** It's the only option
that pins the exact validated images **and** health-gates with rollback — the two things that make
"merge → live" safe on a stack that runs Alembic migrations on startup.

1. **Reconcile image coordinates first** — point Compose at the same registry/repo CI publishes to and
   make `IMAGE_TAG` the deploy input (not a static `:1.8.2`).
2. **Add a gated `deploy` job** — `needs:` the publish jobs, inside the existing `concurrency` group
   (#147) so rollouts serialize; runs only on the intended trigger.
3. **Pull & recreate, then verify** — `pull → up -d` (never touches volumes — rule 9), wait on
   `/api/app/health` (#124) + the public root, roll the tag back on failure.
4. **Harden the path** — non-root deploy user, forced-command key, self-hosted runner or tunnel;
   secrets in GitHub, never the repo.
5. **Make "is it live?" answerable** — surface rollout status / a `/deploy-status` check (#120) and
   update the rule-8 doctrine so "confirmed" means *rolled out & healthy*.

## Shared prerequisites — true for every option

- **Image-coordinate drift** — the host must pull the same registry/repo/tag CI validated (today it
  defaults to a static `:1.8.2` on the wrong registry).
- **Never destroy volumes** — rollout does `up -d` only. No `down -v`, no `volume rm` (rule 9).
- **Migrations run on start** — `docker-entrypoint.sh` runs `alembic upgrade head`; the rollout must
  be safe on the live DB, not just a fresh install.
- **Serialize deploys** — reuse the `concurrency` guard (#147) so two rollouts never race on the
  shared registry tags.

## Links

- Issue #156 (this plan) · gap #112 · related #120 (`/deploy-status`), #147 (concurrency), #124 (`/health`)
- [1Panel API manual](https://docs.1panel.pro/dev_manual/api_manual/)
