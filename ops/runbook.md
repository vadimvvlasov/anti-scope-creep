# Runbook

What to check, where, and what to do when Anti-Scope Creep misbehaves. Each scenario goes
symptom → where to look → commands → action. Commands are read-only unless marked.

Since phase 4 the backend sends traces, metrics and logs to Grafana Cloud (the dashboard
"Anti-Scope Creep service health" and two alert rules: [`ops/grafana/README.md`](grafana/README.md)).
The signals below are what you can check without it.

## System map

| Component | Where it runs | Logs and state | Who has access |
|---|---|---|---|
| Frontend | Cloudflare Worker `anti-scope-creep` (prod), `anti-scope-creep-dev` (dev) | `npx wrangler tail <worker>` | owner (Cloudflare login) |
| Backend | Home server, compose projects `asc-prod` and `asc-dev` (`compose.server.yaml`): service `backend` and its Tailscale sidecar `tailscale`, public through Funnel; `asc-pull.timer` pulls new images every 5 minutes ([`docs/self-host.md`](../docs/self-host.md)) | `docker compose ... logs backend`, `journalctl -u asc-pull.service`, `GET /health`, `/health/ready`, `/version` | owner (SSH to the server); CI only moves image tags in ghcr |
| Database | Neon Postgres, branches `production` and `dev` | Neon console: branch status, connections, operations | owner |
| LLM | Groq `openai/gpt-oss-120b` (dev and prod) | backend logs: `Groq <model> attempt N failed: HTTP <status>` | backend via `GROQ_API_KEY` |
| CI/CD | GitHub Actions: `ci.yml`, `deploy-dev.yml`, `promote-prod.yml`, `deploy.yml` | `gh run list`, `gh run view <id> --log-failed` | anyone with repo access; prod deploy needs an environment approval |

URLs are in the README (Deploy and CI/CD). Backends: `https://asc-prod.tailfeb101.ts.net` (prod),
`https://asc-dev.tailfeb101.ts.net` (dev); the `BACKEND_URL` variable of each GitHub Environment.
Until November 2026 the backend ran on AWS Lightsail; the diagnosis logs from that time refer to it.

## First five minutes

1. Is it up?

   ```bash
   B=https://asc-prod.tailfeb101.ts.net
   curl -s $B/health         # {"status":"ok"}: the process serves requests, no database touched
   curl -s $B/health/ready   # {"status":"ok"}: the database answers
   curl -s $B/version        # {"version":"sha-<7 hex>"}: the image that runs
   ```

   If nothing answers, the server or its connection may be down: on the server, try
   `curl -s http://127.0.0.1:8000/health` (8001 for dev), and see
   [Backend down or not ready](#backend-down-or-not-ready).
2. Is it the version you expect? Compare `/version` with the last successful promote:
   `gh run list --workflow promote-prod.yml --status success --limit 1`. The frontend footer
   shows its own build tag from the same commit.
3. What changed? `gh run list --limit 10` (deploys, promotes),
   `journalctl -u asc-pull.service --since -2h` on the server (which tag started when) and
   `git log --oneline -10 origin/main`.
4. Read the backend log around the time of the problem (next section).

## Logs

Backend: on the server, over SSH (the owner's access; the on-call agent has none by design).
A shell function saves typing the compose file and the env file each time:

```bash
cd /home/asc/anti-scope-creep
asc() { sudo -u asc docker compose -f compose.server.yaml --env-file "/home/asc/env/$1.env" "${@:2}"; }

asc prod logs --since 1h backend | grep -v 'GET /health'   # the backend's JSON log
asc prod ps                                                # state, health, uptime
asc prod logs --since 1h tailscale                         # the sidecar: Funnel, certificates
journalctl -u asc-pull.service --since -2h --no-pager      # pulls and restarts
```

The container's own health check calls `/health/ready` every 10 seconds, hence the
`grep -v`. Docker keeps up to 30 MB of log per container (3 files of 10 MB), so older
lines are gone; the same logs are in Loki when telemetry export is on.

Lines worth searching for: `Analysis failed for contract`, `Groq <model> attempt`,
`Dropped a <category> finding`, `HTTP 429`.

What the logs never contain, by design (`docs/ai-data-policy.md`): contract text,
prompts, model responses, quotes, API keys. If you see any of these, treat it as a data
incident: stop, note the log stream and time, and fix the logging before anything else.

## Scenarios

### Analyses fail or stay "analyzing"

- **Symptom:** a contract turns `failed`, or stays `analyzing` until the UI says
  `Analysis is taking longer than expected`.
- **How it works:** an analysis runs in a background task of the same container. One that
  is still `analyzing` after `ANALYSIS_STALE_AFTER_SECONDS` (600) is marked `failed` on the
  next request of its owner (the stale rule), and the user can press Retry.
- **Look:** backend log for `Analysis failed for contract <id>` and the exception right
  after it; `Groq ... attempt N failed` lines before it.
- **Causes and actions:**
  - Groq `429` after 5 attempts: the per-minute (8,000 tokens) or daily (200,000 tokens)
    quota is used up. The client already backs off and honors `retry-after`. Per-minute:
    retry later. Daily: the 200,000-token limit is a rolling bucket, not a reset at a fixed
    hour: it refills about 139 tokens a minute (about 8,300 an hour), so after a heavy run
    (an eval on the same organization counts too) analysis can get `429` for about an hour.
    Wait, or move prod to a paid tier (planned after the Project 1 submission).
  - `HTTP 400 ... Failed to validate JSON`: the model returned output that does not match
    the strict schema. Not retried by the client; Retry Analysis sends the same text again
    and can succeed (generation is not deterministic).
  - `output was cut at max_completion_tokens`: the answer did not fit
    even after the retry with a doubled budget. Report it with the contract size, never
    its content.
  - A container restart (deploy, crash) during an analysis: the task is lost, the stale
    rule turns it `failed` after 600 s. `asc prod ps` shows how long the container has been
    up, and `journalctl -u asc-pull.service` when a new image started.

### Backend down or not ready

- **`/health` fails from outside, but works on the server** (`curl -s http://127.0.0.1:8000/health`):
  the path through Tailscale is broken. `asc prod exec tailscale tailscale status` and
  `asc prod exec tailscale tailscale funnel status`; `asc prod logs tailscale`. A node that has
  just been created drops some TLS handshakes for a few minutes; that passes on its own.
- **`/health` fails on the server too:** the container does not serve. `asc prod ps`:
  `starting` means a restart is in progress, wait; `restarting` or `unhealthy` means the
  process crashes or cannot reach the database, read `asc prod logs backend` from its start.
  A pull that is still running shows in `systemctl status asc-pull.service`.
- **Nothing answers, not even SSH:** the server is off or offline (power, home internet).
  There is no second host; the backend is down until it is back. The frontend still loads
  and shows network errors.
- **`/health` ok, `/health/ready` fails:** the database does not answer. Neon console:
  is the branch active, compute suspended (it wakes on the next query), any incident on
  Neon's status page? Check that `DATABASE_URL` in the server's env file of that environment
  points to the right branch.

### The API answers 500 (`INTERNAL_ERROR`)

The alert "Backend internal errors (5xx)" fired: `api_errors_total{code="INTERNAL_ERROR"}` grew. The
agent is already working on it (next section); this is what a person checks meanwhile.

- **Which route and which image.** The alert carries `deployment_environment` and `service_version`
  (`sha-<short sha>`, the commit that is running). The dashboard panel "Traces with errors" lists the
  failing requests with their route; open one in Tempo.
- **What failed.** The server span has an `exception` event with the type and the traceback frames (no
  message: it may hold contract text, `docs/architecture.md`, section 6). `routers/...` and `app/...` frames are
  ours, anything under `site-packages` is a library called from them.
- **Is it new?** `git log` between the previous and the running `service_version`: a 500 on a fresh deploy
  is the diff until proven otherwise. A person can roll back prod with the steps below while the agent's fix
  waits for review.
- **A title or an input in another alphabet or with unusual characters** is the first guess for a 500 on a
  route that works for ASCII (the drill of 2026-10-21 was exactly that:
  [`diagnosis/2026-10-21-oncall-drill.md`](diagnosis/2026-10-21-oncall-drill.md)).

### The on-call agent opened a pull request or an issue

The agent (`.github/workflows/on-call.yml`) answers an alert with one of two things, both labelled
`oncall`; a person decides, the agent cannot merge or deploy.

- **An issue labelled `needs-human-review`:** the agent could not settle it (`needs_human`), or it judged
  the alert a false positive (`false_positive`), or it ended without a verdict (`No finish call in N
  turns`). Read the summary, then the run log of the `Investigate` step: it lists every tool call by turn.
- **A pull request `On-call: <alert>`:** a verified fix. The whole backend suite passed with it, and it
  touches only `backend/app/`, `backend/tests/` and `frontend/src/`. Review it like any other pull request:
  1. Read the diff and the summary. Does the change follow `docs/spec.md`, not only the tests it wrote?
  2. GitHub holds the CI run of a pull request opened by a bot (`action_required`): open the pull request and
     choose **Approve and run workflows**. The CI run that the agent starts itself by hand on its branch does
     not count as the checks of the pull request (the pull request stays blocked until the held run passes).
  3. When the seven checks are green, merge. The fix branch starts from the deployed commit, not from `main`;
     if `main` has moved on, GitHub shows a conflict to resolve in the pull request.
  4. Promote to prod by hand when the fix is needed there; the agent never deploys.
- **The run itself failed** (red `On-call agent` run): read the failed step. The step "Pick the commit to
  investigate" fails by design when `ref` is not a commit that is already in `main`.
- The agent may be wrong. It is not deterministic: the same alert can end as a fix, as an issue, or without
  a verdict.

### Frontend does not load or shows errors

- `npx wrangler tail anti-scope-creep` while reproducing; deep links rely on the Worker's
  SPA fallback (`frontend/wrangler.jsonc`, `not_found_handling`).
- Browser errors about CORS: `CORS_ORIGINS` of the backend must contain the Worker URL.

### A deploy or promote failed

- `gh run view <id> --log-failed` shows the failed step.
- **`promote-prod.yml`, job `resolve`:** it validates before anyone approves. Leave
  `image_tag` empty to promote the last successful dev deploy; a typed tag must match
  `sha-<7 hex>`, be on `main` and exist in ghcr. A failure here changed nothing in prod.
- **`deploy.yml`, "Check the settings":** the `BACKEND_URL` variable of the environment is
  empty or not `https://<host>`.
- **`deploy.yml`, "Wait for the server to run the image":** the tag moved, but in 10 minutes
  `GET /version` did not report the new image. On the server: `systemctl status asc-pull.timer
  asc-pull.service` (is the timer running, did the last run fail?) and
  `journalctl -u asc-pull.service -n 50` (pull error, or `not healthy after 180s`: then
  `asc dev logs backend`). Compose does not roll back: a new container that never becomes
  healthy stays in place of the old one, so that environment is down until you fix it or move
  the tag back. Rerun the workflow once the server is fixed: moving the tag again is harmless.
- **`deploy.yml` smoke test:** `scripts/smoke.py` waits for `/health/ready`, checks
  `/version` and runs register, upload, poll and delete. A smoke failure after the server
  switched means the new version is live but broken: roll back.

### Roll back prod

Promote the previous good image (it is still in ghcr; no rebuild, no code change):

```bash
gh run list --workflow promote-prod.yml --status success --limit 5   # pick the previous tag
gh workflow run promote-prod.yml -f image_tag=sha-<7 hex>             # changes prod; needs approval
```

The server runs it within about 5 minutes; the workflow waits for that and runs the smoke
test. Then check `/version`.

Migrations are not rolled back automatically, and the promote runs `alembic upgrade head`
from the older image first: if the bad release contained a migration, that step fails
(the database is at a revision the older image does not know), and nothing changes in
prod. Then move the tag by hand, which skips migrations. The older image then runs on the
newer schema, which works because migrations must stay backward-compatible
([`docs/deploy.md`](../docs/deploy.md), "Promote to prod"; [`docs/self-host.md`](../docs/self-host.md),
section 7):

```bash
docker buildx imagetools create \
  -t ghcr.io/vadimvvlasov/anti-scope-creep-backend:prod \
  ghcr.io/vadimvvlasov/anti-scope-creep-backend:sha-<7 hex>       # changes prod
```

If ghcr itself is the problem, pin the image on the server instead: `IMAGE_TAG=sha-<7 hex>`
in the prod env file, then `sudo systemctl start asc-pull.service`.

## After an incident

Write a diagnosis log in [`diagnosis/`](diagnosis/) using the structure of the existing
ones: symptom, timeline, hypotheses, commands and evidence, root cause, fix, prevention,
and what the investigating agent could and could not access.
